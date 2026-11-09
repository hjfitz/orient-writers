#!/usr/bin/env node
// Count every diagram block under one or more folders and say what the diagram rules make of them.
// Read-only: it never writes a file, so it is safe to point at the vault (Waypoint docs carry
// verified_sha anchors, and editing one changes its staleness).
//
// Usage:  node audit-diagrams.mjs <dir|file>... [--verbose] [--json]
//
// Reports, for orient-flow, orient-sequence and mermaid blocks: how many there are, how many carry
// lint errors or warnings under diagram-rules.mjs, which would be drawn differently now that kind
// decides a box's shape (store, topic, external), and which mermaid blocks a native preset covers.

import { readdirSync, readFileSync, statSync } from 'node:fs'
import { join } from 'node:path'
import { checkFlow, checkMermaid, checkSequence, inferFlowPreset } from './diagram-rules.mjs'

const args = process.argv.slice(2)
const verbose = args.includes('--verbose')
const asJson = args.includes('--json')
const roots = args.filter((a) => !a.startsWith('--'))
if (roots.length === 0) {
  console.error('usage: audit-diagrams.mjs <dir|file>... [--verbose] [--json]')
  process.exit(2)
}

const SKIP = new Set(['.git', 'node_modules', '.next', '.next-prod', '.knowledge', '.obsidian', '.trash'])
function* walk(path) {
  const st = statSync(path)
  if (st.isFile()) {
    if (/\.(md|mdx)$/.test(path)) yield path
    return
  }
  for (const name of readdirSync(path)) {
    if (!SKIP.has(name)) yield* walk(join(path, name))
  }
}

const rows = []
for (const root of roots) {
  for (const file of walk(root)) {
    const lines = readFileSync(file, 'utf8').split('\n')
    let fence = null
    for (let i = 0; i < lines.length; i++) {
      if (fence === null) {
        const open = /^```(orient-flow|orient-sequence|mermaid)\s*$/.exec(lines[i])
        if (open) fence = { lang: open[1], line: i + 1, body: [] }
      } else if (/^```\s*$/.test(lines[i])) {
        rows.push(assess(file, fence))
        fence = null
      } else fence.body.push(lines[i])
    }
  }
}

function assess(file, { lang, line, body }) {
  const text = body.join('\n')
  const row = { file, line, lang, errors: [], warnings: [], differs: [], migrate: null }
  if (lang === 'mermaid') {
    const m = checkMermaid(text)
    row.mermaid = m.type
    if (m.target) row.migrate = m.preset ? `orient-flow/${m.preset}` : m.target
    return row
  }
  let data
  try {
    data = JSON.parse(text)
  } catch {
    row.errors.push('invalid JSON')
    return row
  }
  if (data.v !== 1) row.errors.push('v must be 1')
  const anchored = file.includes('/Engineering/')
  const found = lang === 'orient-flow' ? checkFlow(data, { anchored }) : checkSequence(data, { anchored })
  for (const f of found) (f.level === 'error' ? row.errors : row.warnings).push(f.message)
  if (lang === 'orient-flow') {
    row.inferred = data.preset ?? inferFlowPreset(data)
    const kinds = new Set((data.nodes ?? []).map((n) => n.kind))
    if (kinds.has('store')) row.differs.push('store is now a cylinder')
    if (kinds.has('topic')) row.differs.push('topic is now a pill')
    if (kinds.has('external')) row.differs.push('external is solid on a darker fill, not dashed')
  }
  return row
}

const byLang = (lang) => rows.filter((r) => r.lang === lang)
const summary = {}
for (const lang of ['orient-flow', 'orient-sequence', 'mermaid']) {
  const list = byLang(lang)
  summary[lang] = {
    blocks: list.length,
    files: new Set(list.map((r) => r.file)).size,
    withErrors: list.filter((r) => r.errors.length > 0).length,
    withWarnings: list.filter((r) => r.warnings.length > 0).length,
    drawnDifferently: list.filter((r) => r.differs.length > 0).length,
    migrationCandidates: list.filter((r) => r.migrate).length,
  }
}

if (asJson) {
  console.log(JSON.stringify({ summary, rows }, null, 2))
  process.exit(0)
}
console.log('block'.padEnd(17) + 'blocks files errors warnings differ migrate')
for (const [lang, s] of Object.entries(summary)) {
  console.log(
    `${lang.padEnd(17)}${String(s.blocks).padEnd(7)}${String(s.files).padEnd(6)}${String(s.withErrors).padEnd(7)}${String(s.withWarnings).padEnd(9)}${String(s.drawnDifferently).padEnd(7)}${s.migrationCandidates}`,
  )
}
const tally = new Map()
for (const r of rows) for (const w of r.warnings) {
  const rule = w.replace(/^orient-(flow|sequence): /, '').replace(/\([^)]*\)/g, '').replace(/".*?"/g, '"_"').replace(/\d+/g, 'N').replace(/\s+/g, ' ').trim().slice(0, 90)
  tally.set(rule, (tally.get(rule) ?? 0) + 1)
}
console.log('\nwarnings by rule:')
for (const [rule, n] of [...tally].sort((a, b) => b[1] - a[1])) console.log(`  ${String(n).padStart(3)}  ${rule}`)
const inferred = new Map()
for (const r of byLang('orient-flow')) inferred.set(r.inferred, (inferred.get(r.inferred) ?? 0) + 1)
console.log(`\nflow presets (set or inferred): ${[...inferred].map(([k, v]) => `${k} ${v}`).join(', ')}`)
const mer = new Map()
for (const r of byLang('mermaid')) mer.set(r.mermaid, (mer.get(r.mermaid) ?? 0) + 1)
console.log(`mermaid types: ${[...mer].map(([k, v]) => `${k} ${v}`).join(', ') || 'none'}`)
if (verbose) {
  for (const r of rows) {
    const bits = [...r.errors.map((e) => `ERROR ${e}`), ...r.warnings.map((w) => `warn ${w}`), ...r.differs.map((d) => `differs: ${d}`)]
    if (r.migrate) bits.push(`migrate -> ${r.migrate}`)
    if (bits.length > 0) console.log(`\n${r.file}:${r.line} ${r.lang}\n  ${bits.join('\n  ')}`)
  }
}
