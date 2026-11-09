// The diagram rules the explain lint and the diagram audit share. Dependency-free, like the lint.
//
// FLOW_PRESETS, SEQUENCE_PRESETS, NODE_KINDS and ICON_KEYS mirror orient's
// src/render/md/diagram-presets.ts. This file cannot import TypeScript, so the two change together;
// orient's tests/unit/diagram-presets.test.ts fails when they differ.

export const NODE_KINDS = ['service', 'topic', 'store', 'step', 'external', 'person']
export const ICON_KEYS = [
  'compute',
  'storage',
  'pubsub',
  'run',
  'memorystore',
  'gke',
  'sql',
  'bigquery',
  'functions',
  'secret',
  'scheduler',
]

export const FLOW_PRESETS = {
  'c4-context': { version: 1, kinds: ['person', 'service', 'external'], maxNodes: 10, groups: 'none', numberEdges: false },
  'c4-container': { version: 1, kinds: ['person', 'service', 'topic', 'store', 'external'], maxNodes: 20, groups: 'optional', numberEdges: false },
  'c4-component': { version: 1, kinds: ['step', 'service', 'topic', 'store', 'external'], maxNodes: 20, groups: 'required', numberEdges: false },
  'data-flow': { version: 1, kinds: ['step', 'service', 'topic', 'store', 'external'], maxNodes: 12, groups: 'optional', numberEdges: true },
}
export const SEQUENCE_PRESETS = {
  'c4-dynamic': { version: 1, maxActors: 6, maxSteps: 20 },
}
export const UNSET_MAX_NODES = 20
export const UNSET_MAX_STEPS = 20

const nonEmpty = (v) => typeof v === 'string' && v.trim() !== ''
const isC4 = (preset) => typeof preset === 'string' && preset.startsWith('c4-')
const arrow = (e) => `${e.from}->${e.to}`
const some = (list) => list.slice(0, 3).join(', ') + (list.length > 3 ? ', ...' : '')

/** The preset an unmarked flow looks like, so the lint can name it and the audit can count it. */
export function inferFlowPreset(data) {
  const nodes = data.nodes ?? []
  const groups = data.groups ?? []
  if (groups.length > 0) {
    return nodes.some((n) => n.group && (n.kind ?? 'step') === 'step') ? 'c4-component' : 'c4-container'
  }
  if (nodes.some((n) => n.kind === 'person')) return 'c4-context'
  if (nodes.some((n) => n.kind === 'topic' || n.kind === 'store')) return 'c4-container'
  return 'data-flow'
}

/** Findings for one orient-flow block: { level: 'error' | 'warn', message }. */
export function checkFlow(data, { anchored = false } = {}) {
  const out = []
  const err = (message) => out.push({ level: 'error', message })
  const warn = (message) => out.push({ level: 'warn', message })
  const nodes = Array.isArray(data.nodes) ? data.nodes : []
  const edges = Array.isArray(data.edges) ? data.edges : []
  const groups = Array.isArray(data.groups) ? data.groups : []

  let preset = null
  if (data.preset != null) {
    if (FLOW_PRESETS[data.preset]) preset = data.preset
    else {
      const seq = SEQUENCE_PRESETS[data.preset] ? ' (a sequence preset)' : ''
      err(`orient-flow: unknown preset "${data.preset}"${seq}; flow presets are ${Object.keys(FLOW_PRESETS).join(', ')}`)
    }
  }

  const groupIds = new Set()
  for (const [i, g] of groups.entries()) {
    if (!nonEmpty(g.id) || !nonEmpty(g.label)) err(`orient-flow: groups.${i} needs an id and a label`)
    if (groupIds.has(g.id)) err(`orient-flow: duplicate group id "${g.id}"`)
    groupIds.add(g.id)
    if (g.icon != null && !ICON_KEYS.includes(g.icon)) err(`orient-flow: groups.${i}.icon "${g.icon}" is not one of ${ICON_KEYS.join(', ')}`)
  }
  for (const [i, n] of nodes.entries()) {
    if (n.group != null && !groupIds.has(n.group)) err(`orient-flow: nodes.${i}.group names unknown group "${n.group}"`)
    if (n.icon != null && !ICON_KEYS.includes(n.icon)) err(`orient-flow: nodes.${i}.icon "${n.icon}" is not one of ${ICON_KEYS.join(', ')}`)
    if (n.unconfirmed != null && typeof n.unconfirmed !== 'boolean') err(`orient-flow: nodes.${i}.unconfirmed must be true or false`)
  }
  for (const [i, e] of edges.entries()) {
    if (e.unconfirmed != null && typeof e.unconfirmed !== 'boolean') err(`orient-flow: edges.${i}.unconfirmed must be true or false`)
  }

  const def = preset ? FLOW_PRESETS[preset] : null
  if (data.preset == null) {
    const guess = inferFlowPreset(data)
    warn(`orient-flow: no preset; this looks like "${guess}" (add "preset": "${guess}", or pick the one that fits)`)
  }

  const cap = def ? def.maxNodes : UNSET_MAX_NODES
  if (nodes.length > cap) warn(`orient-flow: ${nodes.length} nodes (cap ${cap}${preset ? ` for ${preset}` : ''}): split it by level or by flow`)

  if (def) {
    const off = nodes.filter((n) => !def.kinds.includes(n.kind ?? 'step')).map((n) => `${n.id} (${n.kind ?? 'step'})`)
    if (off.length > 0) warn(`orient-flow: ${preset} does not draw ${some(off)}; use ${def.kinds.join(', ')}`)
    if (def.groups === 'required' && groups.length === 0) warn(`orient-flow: ${preset} draws the container as a group; add "groups" and set each component's "group"`)
    if (def.groups === 'none' && groups.length > 0) warn(`orient-flow: ${preset} shows no boundaries; use c4-container to draw groups`)
  }
  const used = new Set(nodes.map((n) => n.group).filter(Boolean))
  const empty = groups.filter((g) => !used.has(g.id)).map((g) => g.id)
  if (empty.length > 0) warn(`orient-flow: group ${some(empty)} has no nodes, so it is not drawn`)

  const unlabelled = edges.filter((e) => !nonEmpty(e.label)).map(arrow)
  if (unlabelled.length > 0) warn(`orient-flow: ${unlabelled.length} edge(s) with no label (${some(unlabelled)}): say what moves, not "uses"`)

  if (isC4(preset)) {
    const bareDashed = edges.filter((e) => e.style === 'dashed' && !e.unconfirmed).map(arrow)
    if (bareDashed.length > 0) warn(`orient-flow: dashed means "not confirmed" in ${preset}; set "unconfirmed": true on ${some(bareDashed)} or draw it solid`)
    const outside = nodes.filter((n) => n.group && n.kind === 'external').map((n) => n.id)
    if (outside.length > 0) warn(`orient-flow: external ${some(outside)} sits inside a group; draw external things outside the boundaries`)
  }
  if (preset === 'c4-context' || preset === 'c4-container') {
    const bare = nodes.filter((n) => !nonEmpty(n.sub)).map((n) => n.id)
    if (bare.length > 0) warn(`orient-flow: ${bare.length} box(es) with no "sub" description (${some(bare)}): every C4 box has a name, a type and a description`)
  }

  const unconfirmed = nodes.filter((n) => n.unconfirmed).length + edges.filter((e) => e.unconfirmed).length
  if (anchored && unconfirmed > 0) warn(`orient-flow: ${unconfirmed} unconfirmed item(s) in an anchored doc: confirm them against the code, or leave them out`)
  return out
}

/** Findings for one orient-sequence block. */
export function checkSequence(data, { anchored = false } = {}) {
  const out = []
  const err = (message) => out.push({ level: 'error', message })
  const warn = (message) => out.push({ level: 'warn', message })
  const actors = Array.isArray(data.actors) ? data.actors : []
  const steps = Array.isArray(data.steps) ? data.steps : []

  let preset = null
  if (data.preset != null) {
    if (SEQUENCE_PRESETS[data.preset]) preset = data.preset
    else {
      const flow = FLOW_PRESETS[data.preset] ? ' (a flow preset)' : ''
      err(`orient-sequence: unknown preset "${data.preset}"${flow}; sequence presets are ${Object.keys(SEQUENCE_PRESETS).join(', ')}`)
    }
  }
  for (const [i, a] of actors.entries()) {
    if (a.kind != null && !NODE_KINDS.includes(a.kind)) err(`orient-sequence: actors.${i}.kind "${a.kind}" is not one of ${NODE_KINDS.join(', ')}`)
  }
  for (const [i, x] of [...actors, ...steps].entries()) {
    if (x.unconfirmed != null && typeof x.unconfirmed !== 'boolean') err(`orient-sequence: entry ${i} has a non-boolean unconfirmed`)
  }

  const def = preset ? SEQUENCE_PRESETS[preset] : null
  const maxSteps = def ? def.maxSteps : UNSET_MAX_STEPS
  if (steps.length > maxSteps) warn(`orient-sequence: ${steps.length} steps (cap ${maxSteps}${preset ? ` for ${preset}` : ''}): split it, or use a table`)
  if (def && actors.length > def.maxActors) warn(`orient-sequence: ${actors.length} actors (cap ${def.maxActors} for ${preset})`)
  if (def) {
    const bare = actors.filter((a) => a.kind == null).map((a) => a.id)
    if (bare.length > 0) warn(`orient-sequence: ${preset} wants a "kind" on each actor (${some(bare)}), so its box matches the flow diagrams`)
  }
  const unconfirmed = [...actors, ...steps].filter((x) => x.unconfirmed).length
  if (anchored && unconfirmed > 0) warn(`orient-sequence: ${unconfirmed} unconfirmed item(s) in an anchored doc: confirm them against the code, or leave them out`)
  return out
}

/** What a mermaid block is and whether orient draws it natively. */
export function checkMermaid(code) {
  const first = code
    .split('\n')
    .map((l) => l.trim())
    .find((l) => l !== '' && !l.startsWith('%%') && l !== '---') ?? ''
  const type = (/^[A-Za-z-]+/.exec(first) ?? [''])[0]
  if (type === 'sequenceDiagram') {
    return { type, target: 'orient-sequence', hint: 'redraw it as orient-sequence' }
  }
  if (type === 'graph' || type === 'flowchart') {
    const grouped = /^\s*subgraph\b/m.test(code)
    const preset = grouped ? 'c4-container' : 'data-flow'
    return { type, target: 'orient-flow', preset, hint: `redraw it as orient-flow, preset ${preset}` }
  }
  return { type: type || 'unknown', target: null, hint: `no native preset for a ${type || 'unknown'} diagram; keep it, and expect it to look different` }
}
