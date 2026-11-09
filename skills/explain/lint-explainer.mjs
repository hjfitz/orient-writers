#!/usr/bin/env node
// Lint an explainer before it lands in the vault.
//
// Errors (exit 1) are things orient would render wrongly or `wp` would misread: a bad typed block, a
// missing or late BLUF, a `thesis:` that differs from the BLUF, an evidence ref with no row, a code
// anchor that is not `path@sha`. Warnings are the house style: sentences over 22 words, hedging,
// passive voice, a claim with no basis tag, a missing section, a page over its length cap.
//
// Usage:  node lint-explainer.mjs <file.md> [--mode system|event|overview|architecture|blocks] [--quiet]
//         (blocks: only validate typed blocks and flag mermaid, for a doc that keeps its own shape, e.g. design.md)
//         (mode defaults from the path: overview.md / architecture.md, else system under /explainers/, else event)
// overview and architecture are the two Waypoint docs that share the explainer design language: a BLUF,
// an orient-flow, an evidence block. The doc is anchored to a commit, so an unmarked claim reads as
// confirmed at that anchor; only ASSESSED and UNKNOWN are tagged, and no claim-tag warning is raised.
// Exit:   0 clean or warnings only · 1 errors · 2 could not read the file
//
// Dependency-free and standalone so a skill can call it without orient's toolchain. It mirrors
// orient's src/render/md/explainer-blocks.ts rather than importing it (that file is TypeScript behind
// a bundler); the two change together, so a new block field goes in both. The preset and diagram rules
// live in diagram-rules.mjs beside this file, which the diagram audit (audit-diagrams.mjs) shares.

import { readFileSync } from 'node:fs'
import { checkFlow, checkMermaid, checkSequence, NODE_KINDS } from './diagram-rules.mjs'

const args = process.argv.slice(2)
const modeAt = args.indexOf('--mode')
const modeArg = modeAt >= 0 ? args[modeAt + 1] : null
const file = args.find((a) => !a.startsWith('--') && a !== modeArg)
const quiet = args.includes('--quiet')
if (!file) {
  console.error('usage: lint-explainer.mjs <file.md> [--mode system|event|overview|architecture|blocks] [--quiet]')
  process.exit(2)
}
let text
try {
  text = readFileSync(file, 'utf8')
} catch (e) {
  console.error(`cannot read ${file}: ${e.message}`)
  process.exit(2)
}
const base = file.split('/').pop()
const mode =
  modeArg ??
  (base === 'overview.md' ? 'overview' : base === 'architecture.md' ? 'architecture' : file.includes('/explainers/') ? 'system' : 'event')
const ANCHORED = mode === 'system' || mode === 'overview' || mode === 'architecture'
// A Waypoint doc anchors to a commit; a Systems or Customers doc has no repo, so it carries a verified date only.
const NEEDS_SHA = ANCHORED && file.includes('/Engineering/')

const CONFIDENCES = new Set(['high', 'moderate', 'low'])
const EVIDENCE_KINDS = new Set(['code', 'pr', 'ticket', 'log', 'doc', 'url'])
const TONES = new Set(['alert', 'accent'])
const STEP_KINDS = new Set(['call', 'return', 'async'])
const CODE_REF = /^(.+?)@([0-9a-fA-F]{7,40})(?::(L\d+(?:-L?\d+)?))?$/
const CLAIM_TAG = /^\*\*(CONFIRMED|ASSESSED|UNKNOWN)\*\*/
const CAPS = { system: 1300, event: 600, overview: 700, architecture: 2600, blocks: Infinity }
const MAX_WORDS = 22
const HEDGES =
  /\b(probably|perhaps|maybe|might|somewhat|basically|essentially|arguably|seems? to|appears? to|kind of|sort of|quite|rather|fairly|very|really|just|simply|clearly|obviously)\b/i
const PASSIVE =
  /\b(is|are|was|were|be|been|being)\s+(?!not\b)(\w+ed|made|done|run|sent|set|shown|known|given|kept|held|built|written|taken|found|seen)\b/i

const findings = []
const add = (line, level, message) => findings.push({ line, level, message })

const lines = text.split('\n')

// frontmatter
let bodyStart = 0
const fm = {}
if (lines[0] === '---') {
  const end = lines.indexOf('---', 1)
  if (end > 0) {
    bodyStart = end + 1
    // YAML dumpers fold a long scalar over indented continuation lines; join them before unquoting.
    let key = null
    for (const l of lines.slice(1, end)) {
      const m = /^([A-Za-z_]+):\s*(.*)$/.exec(l)
      if (m) {
        key = m[1]
        fm[key] = m[2].trim()
      } else if (key && /^\s+\S/.test(l) && !/^\s+- /.test(l)) {
        fm[key] += ` ${l.trim()}`
      }
    }
    for (const k of Object.keys(fm)) fm[k] = fm[k].replace(/^(['"])(.*)\1$/, '$2').replace(/''/g, "'")
  }
}
if (mode !== 'blocks' && !fm.thesis) add(1, 'error', 'frontmatter has no thesis: (wp indexes it; it must equal the BLUF)')
if (ANCHORED) {
  for (const key of NEEDS_SHA ? ['verified', 'verified_sha'] : ['verified']) {
    if (!(key in fm)) add(1, 'error', `${mode} doc needs ${key}:`)
  }
  if (NEEDS_SHA && !lines.slice(0, bodyStart).some((l) => l.startsWith('verified_paths:'))) {
    add(1, 'error', `${mode} doc needs verified_paths:`)
  }
}

// fenced blocks
const blocks = []
let fence = null
const proseLines = []
for (let i = bodyStart; i < lines.length; i++) {
  const l = lines[i]
  if (fence === null) {
    const open = /^```(\S*)\s*$/.exec(l)
    if (open) fence = { lang: open[1], start: i + 1, body: [] }
    else proseLines.push({ n: i + 1, text: l })
  } else if (/^```\s*$/.test(l)) {
    blocks.push({ ...fence, end: i + 1 })
    fence = null
  } else {
    fence.body.push(l)
  }
}
if (fence) add(fence.start, 'error', 'unclosed code fence')

const isId = (v) => Number.isInteger(v) && v > 0
const nonEmpty = (v) => typeof v === 'string' && v.trim() !== ''
const parsed = {}

for (const b of blocks.filter((x) => x.lang.startsWith('orient-'))) {
  const kind = b.lang
  let data
  try {
    data = JSON.parse(b.body.join('\n'))
  } catch {
    add(b.start, 'error', `${kind}: invalid JSON`)
    continue
  }
  if (data.v !== 1) add(b.start, 'error', `${kind}: v must be 1`)
  ;(parsed[kind] ??= []).push({ data, block: b })

  if (kind === 'orient-bluf') {
    if (!nonEmpty(data.bluf)) add(b.start, 'error', 'orient-bluf: bluf is required')
    if (!CONFIDENCES.has(data.confidence)) add(b.start, 'error', 'orient-bluf: confidence must be high, moderate or low')
    if (!nonEmpty(data.action)) add(b.start, 'error', 'orient-bluf: action is required ("none" is a valid action)')
  } else if (kind === 'orient-evidence') {
    const ids = new Set()
    if (!Array.isArray(data.items) || data.items.length === 0) add(b.start, 'error', 'orient-evidence: items must be a non-empty array')
    for (const [i, item] of (data.items ?? []).entries()) {
      if (!isId(item.id)) add(b.start, 'error', `orient-evidence: items.${i}.id must be a positive integer`)
      else if (ids.has(item.id)) add(b.start, 'error', `orient-evidence: duplicate id ${item.id}`)
      else ids.add(item.id)
      if (!EVIDENCE_KINDS.has(item.kind)) add(b.start, 'error', `orient-evidence: items.${i}.kind "${item.kind}" is not one of ${[...EVIDENCE_KINDS].join(', ')}`)
      if (!nonEmpty(item.ref)) add(b.start, 'error', `orient-evidence: items.${i}.ref is required`)
      else if (item.kind === 'code' && !CODE_REF.test(item.ref.trim())) {
        add(b.start, 'error', `orient-evidence: code ref "${item.ref}" must be path@sha or path@sha:L10-30`)
      }
    }
  } else if (kind === 'orient-flow') {
    const ids = new Set()
    if (!Array.isArray(data.nodes) || data.nodes.length < 1 || data.nodes.length > 40) add(b.start, 'error', 'orient-flow: nodes must have 1 to 40 entries')
    for (const [i, n] of (data.nodes ?? []).entries()) {
      if (!nonEmpty(n.id) || !nonEmpty(n.label)) add(b.start, 'error', `orient-flow: nodes.${i} needs an id and a label`)
      if (ids.has(n.id)) add(b.start, 'error', `orient-flow: duplicate node id "${n.id}"`)
      ids.add(n.id)
      if (n.kind !== undefined && !NODE_KINDS.includes(n.kind)) add(b.start, 'error', `orient-flow: nodes.${i}.kind "${n.kind}" is not one of ${NODE_KINDS.join(', ')}`)
      if (n.tone != null && !TONES.has(n.tone)) add(b.start, 'error', `orient-flow: nodes.${i}.tone must be alert or accent`)
    }
    for (const [i, e] of (data.edges ?? []).entries()) {
      for (const end of ['from', 'to']) if (!ids.has(e[end])) add(b.start, 'error', `orient-flow: edges.${i}.${end} names unknown node "${e[end]}"`)
    }
    for (const f of checkFlow(data, { anchored: ANCHORED })) add(b.start, f.level, f.message)
  } else if (kind === 'orient-sequence') {
    const ids = new Set()
    if (!Array.isArray(data.actors) || data.actors.length < 2 || data.actors.length > 8) add(b.start, 'error', 'orient-sequence: actors must have 2 to 8 entries')
    for (const a of data.actors ?? []) ids.add(a.id)
    for (const [i, s] of (data.steps ?? []).entries()) {
      for (const end of ['from', 'to']) if (!ids.has(s[end])) add(b.start, 'error', `orient-sequence: steps.${i}.${end} names unknown actor "${s[end]}"`)
      if (!nonEmpty(s.label)) add(b.start, 'error', `orient-sequence: steps.${i}.label is required`)
      if (s.kind !== undefined && !STEP_KINDS.has(s.kind)) add(b.start, 'error', `orient-sequence: steps.${i}.kind must be call, return or async`)
    }
    for (const f of checkSequence(data, { anchored: ANCHORED })) add(b.start, f.level, f.message)
  } else {
    add(b.start, 'warn', `${kind}: unknown orient block kind (orient will show it as source)`)
  }
}

// BLUF: exactly one, before the first section, and equal to thesis
const bluf = parsed['orient-bluf'] ?? []
if (mode !== 'blocks' && bluf.length === 0) add(1, 'error', 'no orient-bluf block: every explainer opens with its bottom line')
if (bluf.length > 1) add(bluf[1].block.start, 'error', 'more than one orient-bluf block')
const firstH2 = proseLines.find((l) => /^## /.test(l.text))?.n ?? Infinity
if (bluf[0] && bluf[0].block.start > firstH2) add(bluf[0].block.start, 'error', 'the BLUF must come before the first ## section')
const norm = (s) => String(s ?? '').replace(/\s+/g, ' ').trim()
if (bluf[0] && fm.thesis && norm(bluf[0].data.bluf) !== norm(fm.thesis)) {
  add(1, 'error', 'thesis: must equal the BLUF text (wp and the Explainers view read thesis)')
}
if (bluf[0]?.data.confidence && norm(fm.confidence) !== norm(bluf[0].data.confidence)) {
  add(1, 'error', `confidence: must equal the BLUF confidence (${bluf[0].data.confidence}); the Explainers table sorts on it`)
}

// evidence refs
const evidence = parsed['orient-evidence']?.[0]
const evidenceIds = new Set((evidence?.data.items ?? []).map((i) => i.id))
const cited = new Set()
const proseText = proseLines.map((l) => l.text).join('\n')
for (const l of proseLines) {
  for (const m of l.text.matchAll(/\[(\d{1,2})\]/g)) {
    const id = Number(m[1])
    cited.add(id)
    if (evidence && !evidenceIds.has(id)) add(l.n, 'error', `[${id}] cites an evidence row that does not exist`)
  }
}
for (const kind of ['orient-flow', 'orient-sequence']) {
  for (const { data, block } of parsed[kind] ?? []) {
    for (const item of [...(data.nodes ?? []), ...(data.steps ?? [])]) {
      for (const id of item.ev ?? []) {
        cited.add(id)
        if (!evidence) add(block.start, 'error', `${kind} cites evidence [${id}] but the page has no orient-evidence block`)
        else if (!evidenceIds.has(id)) add(block.start, 'error', `${kind} cites evidence [${id}] that does not exist`)
      }
    }
  }
}
if (!evidence && /\[(\d{1,2})\]/.test(proseText)) {
  add(1, 'warn', 'prose has [n] refs but the page has no orient-evidence block, so they will not link')
}
for (const id of evidenceIds) if (!cited.has(id)) add(evidence.block.start, 'warn', `evidence [${id}] is never cited`)

// sections
const headings = proseLines.filter((l) => /^## /.test(l.text)).map((l) => l.text.slice(3).trim().toLowerCase())
const EXPECTED = {
  system: ['mechanism', 'boundaries', 'constraints', 'evidence'],
  event: ['situation', 'assessment', 'evidence'],
  overview: ['responsibility', 'why it exists separately', 'neighbours', 'where the reference lives', "what deliberately isn't here", 'evidence'],
  architecture: ['guardrails', 'evidence'],
}
// A Systems or Customers doc keeps its own sections; only the evidence block is shared.
const expected = !NEEDS_SHA && ANCHORED && mode !== 'system' ? ['evidence'] : EXPECTED[mode]
for (const want of mode === 'blocks' ? [] : expected) {
  if (!headings.some((h) => h.startsWith(want))) add(1, 'warn', `no "## ${want[0].toUpperCase()}${want.slice(1)}" section`)
}

// diagrams: orient draws the structure itself, so mermaid and a flow-less overview or architecture are findings
for (const b of blocks.filter((x) => x.lang === 'mermaid')) {
  const m = checkMermaid(b.body.join('\n'))
  add(b.start, 'warn', `mermaid ${m.type}: ${m.hint}${m.target ? ' so it matches the rest of the page' : ''}`)
}
if ((mode === 'overview' || mode === 'architecture') && NEEDS_SHA && !(parsed['orient-flow'] ?? []).length) {
  add(1, 'warn', `${mode} has no orient-flow: draw the ${mode === 'overview' ? "service's neighbours" : 'structure'}`)
}

// prose style
const NOT_CLAIMS = /^(evidence|related|open items|bluf)/
let section = ''
let words = 0
for (const { n, text: raw } of proseLines) {
  if (/^#{1,6} /.test(raw)) {
    section = raw.replace(/^#+ /, '').trim().toLowerCase()
    continue
  }
  const line = raw.trim()
  if (line === '' || line.startsWith('>') || line.startsWith('[[') || /^\*\*TL;DR/.test(line)) continue
  if (line.startsWith('|')) continue

  const isItem = /^(- |\* |\d+\. )/.test(raw)
  const isTopLevel = !/^\s/.test(raw)
  const body = line.replace(/^(- |\* |\d+\. )/, '')
  const claimable = section !== '' && !NOT_CLAIMS.test(section) && (isItem ? isTopLevel : true)
  if (claimable && !CLAIM_TAG.test(body) && mode !== 'overview' && mode !== 'architecture' && mode !== 'blocks') {
    add(n, 'warn', 'claim has no basis tag: start it with **CONFIRMED**, **ASSESSED** or **UNKNOWN**')
  }

  const plain = body
    .replace(/`[^`]*`/g, 'code')
    .replace(/\[\[[^\]]*\]\]/g, 'link')
    .replace(/\[(\d{1,2})\]/g, '')
    .replace(/\*\*(CONFIRMED|ASSESSED|UNKNOWN)\*\*/g, '')
    .replace(/[*_]/g, '')
  words += plain.split(/\s+/).filter(Boolean).length
  if (mode === 'architecture' || mode === 'blocks') continue
  for (const sentence of plain.split(/(?<=[.!?])\s+/)) {
    const count = sentence.split(/\s+/).filter(Boolean).length
    if (count > MAX_WORDS) add(n, 'warn', `${count}-word sentence (max ${MAX_WORDS}): "${sentence.slice(0, 60)}…"`)
  }
  if (mode === 'architecture' || mode === 'blocks') continue
  const hedge = HEDGES.exec(plain)
  if (hedge) add(n, 'warn', `hedge word "${hedge[0]}": state it or mark it ASSESSED`)
  const passive = PASSIVE.exec(plain)
  if (passive) add(n, 'warn', `passive voice "${passive[0]}": name the actor`)
}
if (words > CAPS[mode]) add(1, 'warn', `${words} words (cap ${CAPS[mode]} for a ${mode} explainer): cut, or split into two`)

findings.sort((a, b) => a.line - b.line)
const errors = findings.filter((f) => f.level === 'error')
for (const f of findings) {
  if (quiet && f.level !== 'error') continue
  console.log(`${file}:${f.line} ${f.level} ${f.message}`)
}
if (!quiet) console.log(`${errors.length} error(s), ${findings.length - errors.length} warning(s), ${words} words, mode ${mode}`)
process.exit(errors.length > 0 ? 1 : 0)
