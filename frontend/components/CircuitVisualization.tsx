'use client'

import { memo, useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react'
import { Expand, Minimize2, Minus, Plus, Scan } from 'lucide-react'
import { describeOp, layoutCircuit, type CircuitLayout, type GateFamily, type LayoutOp, type RawGate } from '@/lib/circuitLayout'

/**
 * 2D circuit diagram.
 *
 * Declarative SVG: the layout is computed once per gate list (lib/circuitLayout)
 * and each operation is a memoised glyph, so hovering or selecting re-renders
 * one or two glyphs instead of tearing down and redrawing the whole drawing.
 */

interface CircuitVisualizationProps {
  gates: RawGate[]
  qubits: number
  className?: string
  /** A newer parse is in flight; the current drawing stays until it lands. */
  busy?: boolean
  /** Called with the pixel height the drawing needs at 100% (header included). */
  onContentHeight?: (px: number) => void
}

// Geometry (SVG user units, scaled as a whole by the zoom level).
const BOX = 34
const GAP = 20
const LEFT = 84 // room for "q0" and the |0> initial state
const TOP = 46 // room for the time axis
const BOTTOM = 18
const RIGHT = 56 // room for the classical-wire stub after measurements

interface FamilyColors { fill: string; stroke: string; text: string }
interface Palette {
  bg: string
  wire: string
  label: string
  muted: string
  hover: string
  select: string
  /** Initial-state labels (|0>). */
  init: string
  clifford: FamilyColors
  rotation: FamilyColors
  entangle: FamilyColors
  measure: FamilyColors
  other: FamilyColors
}

const DARK: Palette = {
  bg: '#131313',
  wire: '#3d4250',
  label: '#8b93a7',
  muted: '#6b7280',
  hover: '#a5b4fc',
  select: '#22d3ee',
  init: '#60a5fa',
  clifford: { fill: '#262a4a', stroke: '#6366f1', text: '#c7d2fe' },
  rotation: { fill: '#16343b', stroke: '#06b6d4', text: '#a5f3fc' },
  entangle: { fill: '#3b1a33', stroke: '#ec4899', text: '#fbcfe8' },
  measure: { fill: '#352812', stroke: '#f59e0b', text: '#fde68a' },
  other: { fill: '#272b33', stroke: '#94a3b8', text: '#e2e8f0' },
}

const LIGHT: Palette = {
  bg: '#ffffff',
  wire: '#cbd5e1',
  label: '#64748b',
  muted: '#94a3b8',
  hover: '#4f46e5',
  select: '#0891b2',
  init: '#2563eb',
  clifford: { fill: '#eef2ff', stroke: '#6366f1', text: '#3730a3' },
  rotation: { fill: '#ecfeff', stroke: '#0891b2', text: '#155e75' },
  entangle: { fill: '#fdf2f8', stroke: '#db2777', text: '#9d174d' },
  measure: { fill: '#fffbeb', stroke: '#d97706', text: '#92400e' },
  other: { fill: '#f8fafc', stroke: '#64748b', text: '#334155' },
}

const LEGEND: Array<{ family: GateFamily; label: string }> = [
  { family: 'clifford', label: 'Single-qubit' },
  { family: 'rotation', label: 'Rotation' },
  { family: 'entangle', label: 'Entangling' },
  { family: 'measure', label: 'Measure' },
]

const HEADER_PX = 32

const SANS = "Inter, ui-sans-serif, system-ui, -apple-system, 'Segoe UI', sans-serif"
const MONO = "'JetBrains Mono', ui-monospace, SFMono-Regular, Menlo, Consolas, monospace"

function useIsDark() {
  const [dark, setDark] = useState(true)
  useEffect(() => {
    const check = () => setDark(!document.documentElement.classList.contains('light'))
    check()
    const obs = new MutationObserver(check)
    obs.observe(document.documentElement, { attributes: true, attributeFilter: ['class'] })
    return () => obs.disconnect()
  }, [])
  return dark
}

/** Box width an op needs: wide enough for its label and angle. */
function opWidth(op: LayoutOp): number {
  if (op.kind === 'barrier') return 10
  if (op.kind === 'swap' || op.kind === 'measure' || op.kind === 'reset') return BOX
  if (op.kind === 'controlled' && op.base === 'x' && !op.angleLabel) return 26
  const label = op.label.length * 8.5 + 12
  const angle = op.angleLabel ? op.angleLabel.length * 6.2 + 12 : 0
  return Math.max(BOX, label, angle)
}

/** Vertical distance between wires: tighter when there are many qubits. */
const rowPitch = (n: number) => (n <= 4 ? 52 : n <= 8 ? 44 : 40)
const rowAt = (q: number, row: number) => TOP + q * row

interface GlyphProps {
  row: number
  op: LayoutOp
  x: number
  w: number
  p: Palette
  state: 'idle' | 'hover' | 'selected'
}

function GateBox({ cx, cy, w, h, label, angle, c, ring }: {
  cx: number; cy: number; w: number; h: number; label: string; angle?: string; c: FamilyColors; ring?: string
}) {
  return (
    <g>
      <rect
        x={cx - w / 2} y={cy - h / 2} width={w} height={h} rx={7}
        fill={c.fill} stroke={ring ?? c.stroke} strokeWidth={ring ? 2 : 1.25}
      />
      <text
        x={cx} y={angle ? cy - 3 : cy + 0.5}
        textAnchor="middle" dominantBaseline="middle"
        fontFamily={SANS} fontSize={label.length > 3 ? 11 : 13} fontWeight={600} fill={c.text}
      >
        {label}
      </text>
      {angle && (
        <text
          x={cx} y={cy + 9.5} textAnchor="middle" dominantBaseline="middle"
          fontFamily={MONO} fontSize={9} fill={c.text} opacity={0.8}
        >
          {angle}
        </text>
      )}
    </g>
  )
}

const OpGlyph = memo(function OpGlyph({ row, op, x, w, p, state }: GlyphProps) {
  const rowY = (q: number) => rowAt(q, row)
  const c = p[op.family]
  const ring = state === 'selected' ? p.select : state === 'hover' ? p.hover : undefined
  const lo = op.qubits[0]
  const hi = op.qubits[op.qubits.length - 1]
  const line = ring ?? c.stroke

  switch (op.kind) {
    case 'barrier': {
      const y1 = rowY(lo) - row / 2 + 6
      const y2 = rowY(hi) + row / 2 - 6
      return (
        <g>
          <rect x={x - 5} y={y1} width={10} height={y2 - y1} rx={3} fill={p.muted} opacity={0.12} />
          <line x1={x} x2={x} y1={y1} y2={y2} stroke={ring ?? p.muted} strokeWidth={1.25} strokeDasharray="4 3" />
        </g>
      )
    }

    case 'measure': {
      const cy = rowY(op.targets[0])
      return (
        <g>
          <rect x={x - BOX / 2} y={cy - BOX / 2} width={BOX} height={BOX} rx={7}
            fill={c.fill} stroke={ring ?? c.stroke} strokeWidth={ring ? 2 : 1.25} />
          <path d={`M ${x - 10} ${cy + 6} A 10 10 0 0 1 ${x + 10} ${cy + 6}`} fill="none" stroke={c.text} strokeWidth={1.5} />
          <line x1={x} y1={cy + 6} x2={x + 7} y2={cy - 6} stroke={c.text} strokeWidth={1.5} strokeLinecap="round" />
          <circle cx={x} cy={cy + 6} r={1.6} fill={c.text} />
        </g>
      )
    }

    case 'reset': {
      const cy = rowY(op.targets[0])
      return <GateBox cx={x} cy={cy} w={BOX} h={BOX} label="|0⟩" c={c} ring={ring} />
    }

    case 'swap': {
      const [a, b] = op.targets
      const cross = (q: number) => {
        const cy = rowY(q)
        return (
          <g key={q} stroke={line} strokeWidth={2} strokeLinecap="round">
            <line x1={x - 6} y1={cy - 6} x2={x + 6} y2={cy + 6} />
            <line x1={x - 6} y1={cy + 6} x2={x + 6} y2={cy - 6} />
          </g>
        )
      }
      return (
        <g>
          <line x1={x} x2={x} y1={rowY(lo)} y2={rowY(hi)} stroke={line} strokeWidth={1.75} />
          {op.controls.map((q) => <circle key={q} cx={x} cy={rowY(q)} r={5} fill={line} />)}
          {cross(a)}
          {cross(b)}
        </g>
      )
    }

    case 'controlled': {
      const t = op.targets[0]
      const ty = rowY(t)
      // Only X gets the textbook (+) target; every other controlled gate (CZ
      // included) shows a labelled box so source and target are unambiguous.
      const symbolic = !op.angleLabel && op.base === 'x'
      return (
        <g>
          <line x1={x} x2={x} y1={rowY(lo)} y2={rowY(hi)} stroke={line} strokeWidth={1.75} />
          {op.controls.map((q) => <circle key={q} cx={x} cy={rowY(q)} r={5} fill={line} />)}
          {symbolic && op.base === 'x' && (
            <g>
              <circle cx={x} cy={ty} r={12} fill={p.bg} stroke={line} strokeWidth={1.75} />
              <line x1={x - 12} x2={x + 12} y1={ty} y2={ty} stroke={line} strokeWidth={1.75} />
              <line x1={x} x2={x} y1={ty - 12} y2={ty + 12} stroke={line} strokeWidth={1.75} />
            </g>
          )}
          {!symbolic && (
            <GateBox cx={x} cy={ty} w={w} h={BOX} label={op.label} angle={op.angleLabel} c={c} ring={ring} />
          )}
        </g>
      )
    }

    case 'multi': {
      const y1 = rowY(lo) - BOX / 2
      const y2 = rowY(hi) + BOX / 2
      return (
        <g>
          <rect x={x - w / 2} y={y1} width={w} height={y2 - y1} rx={7}
            fill={c.fill} stroke={ring ?? c.stroke} strokeWidth={ring ? 2 : 1.25} />
          {op.targets.map((q, i) => (
            <text key={q} x={x - w / 2 + 5} y={rowY(q) + 0.5} dominantBaseline="middle"
              fontFamily={MONO} fontSize={8} fill={c.text} opacity={0.6}>{i}</text>
          ))}
          <text x={x} y={(y1 + y2) / 2 - (op.angleLabel ? 4 : 0)} textAnchor="middle" dominantBaseline="middle"
            fontFamily={SANS} fontSize={12} fontWeight={600} fill={c.text}>{op.label}</text>
          {op.angleLabel && (
            <text x={x} y={(y1 + y2) / 2 + 9} textAnchor="middle" dominantBaseline="middle"
              fontFamily={MONO} fontSize={9} fill={c.text} opacity={0.8}>{op.angleLabel}</text>
          )}
        </g>
      )
    }

    default:
      return <GateBox cx={x} cy={rowY(op.targets[0])} w={w} h={BOX} label={op.label} angle={op.angleLabel} c={c} ring={ring} />
  }
})

/** Vertical extent of an op, for hit areas and tooltip anchoring. */
function opSpan(op: LayoutOp, row: number) {
  return { top: rowAt(op.qubits[0], row) - BOX / 2, bottom: rowAt(op.qubits[op.qubits.length - 1], row) + BOX / 2 }
}

/** Column positions and per-qubit wire info for a laid-out circuit. */
function computeGeometry(layout: CircuitLayout) {
  const widths = new Array<number>(layout.columns).fill(BOX)
  const opW = new Map<number, number>()
  for (const op of layout.ops) {
    const w = opWidth(op)
    opW.set(op.id, w)
    widths[op.column] = Math.max(widths[op.column], w)
  }
  const centers: number[] = []
  let x = LEFT + 14
  for (const w of widths) {
    centers.push(x + w / 2)
    x += w + GAP
  }
  // A qubit whose last operation is a measurement continues as a classical
  // (double) wire from the meter onwards.
  const last = new Array<LayoutOp | undefined>(layout.qubits)
  for (const op of layout.ops) {
    if (op.kind === 'barrier') continue
    for (const q of op.qubits) {
      const prev = last[q]
      if (!prev || prev.column <= op.column) last[q] = op
    }
  }
  const measuredAt = last.map((op) => (op && op.kind === 'measure' ? centers[op.column] : undefined))
  const families = new Set(layout.ops.map((o) => o.family))
  return {
    centers, widths, opW, measuredAt, families,
    width: Math.max(x + RIGHT - GAP, 240),
    height: TOP + (layout.qubits - 1) * rowPitch(layout.qubits) + BOTTOM + BOX / 2,
  }
}

type Geometry = ReturnType<typeof computeGeometry>

/** Bands, wires and gates: the drawing shared by the IDE view and StaticCircuit. */
function CircuitBody({ layout, geo, p, dark, row, drawW, stateOf, dimFrom, showAxis = true }: {
  layout: CircuitLayout
  geo: Geometry
  p: Palette
  dark: boolean
  row: number
  drawW: number
  stateOf?: (id: number) => GlyphProps['state']
  /** Ops in this column or later are drawn faded (for stepping through). */
  dimFrom?: number
  showAxis?: boolean
}) {
  const rowY = (q: number) => rowAt(q, row)
  return (
    <>
      {showAxis && (
        <text x={10} y={14} dominantBaseline="middle" fontFamily={SANS} fontSize={9} fill={p.label} opacity={0.8}>
          time →
        </text>
      )}
      {geo.centers.map((cx, i) => (
        <g key={i}>
          {i % 2 === 0 && (
            <rect
              x={cx - geo.widths[i] / 2 - GAP / 2}
              y={TOP - row / 2 + 6}
              width={geo.widths[i] + GAP}
              height={geo.height - TOP + row / 2 - 10}
              rx={4}
              fill={p.label}
              opacity={dark ? 0.05 : 0.06}
            />
          )}
          {showAxis && (
            <text x={cx} y={14} textAnchor="middle" dominantBaseline="middle" fontFamily={MONO} fontSize={9} fill={p.label} opacity={0.8}>
              {i + 1}
            </text>
          )}
        </g>
      ))}

      {/* Wires: quantum (single line) until a final measurement, then classical (double line). */}
      {Array.from({ length: layout.qubits }, (_, q) => {
        const y = rowY(q)
        const m = geo.measuredAt[q]
        const end = drawW - 8
        return (
          <g key={q}>
            <line x1={LEFT} x2={m ?? end} y1={y} y2={y} stroke={p.wire} strokeWidth={1.25} />
            {m !== undefined && (
              <g stroke={p.measure.stroke} strokeWidth={1} opacity={0.55}>
                <line x1={m + BOX / 2} x2={end} y1={y - 1.75} y2={y - 1.75} />
                <line x1={m + BOX / 2} x2={end} y1={y + 1.75} y2={y + 1.75} />
              </g>
            )}
            <text x={10} y={y} dominantBaseline="middle" fontFamily={MONO} fontSize={12} fill={p.label}>
              q<tspan fontSize={9} dy={3}>{q}</tspan>
            </text>
            <text x={LEFT - 6} y={y} textAnchor="end" dominantBaseline="middle" fontFamily={MONO} fontSize={12} fontWeight={600} fill={p.init}>
              |0⟩
            </text>
          </g>
        )
      })}

      {layout.ops.map((op) => (
        <g
          key={op.id}
          className="qc-viz-op"
          style={{
            transform: `translateX(${geo.centers[op.column]}px)`,
            opacity: dimFrom !== undefined && op.column >= dimFrom ? 0.16 : 1,
          }}
        >
          <OpGlyph
            row={row}
            op={op}
            x={0}
            w={geo.opW.get(op.id) ?? BOX}
            p={p}
            state={stateOf ? stateOf(op.id) : 'idle'}
          />
        </g>
      ))}
    </>
  )
}

/**
 * Non-interactive diagram that scales to its container's width: for the
 * marketing site (hero strip, showcase, learning-path thumbnails). Same
 * renderer and colours as the IDE view.
 */
export function StaticCircuit({
  gates,
  qubits = 0,
  className = '',
  step,
  showAxis = true,
  label,
}: {
  gates: RawGate[]
  qubits?: number
  className?: string
  /** Show moments before this one in full and fade the rest. */
  step?: number
  showAxis?: boolean
  label?: string
}) {
  const dark = useIsDark()
  const p = dark ? DARK : LIGHT
  const layout = useMemo(() => layoutCircuit(gates, qubits), [gates, qubits])
  const geo = useMemo(() => computeGeometry(layout), [layout])
  const row = rowPitch(layout.qubits)
  return (
    <svg
      viewBox={`0 0 ${geo.width} ${geo.height}`}
      className={`block h-auto w-full select-none ${className}`}
      role="img"
      aria-label={label ?? `Circuit diagram: ${layout.qubits} qubits, ${layout.ops.length} operations`}
    >
      <CircuitBody
        layout={layout}
        geo={geo}
        p={p}
        dark={dark}
        row={row}
        drawW={geo.width}
        dimFrom={step}
        showAxis={showAxis}
      />
    </svg>
  )
}

export default function CircuitVisualization({ gates, qubits, className = '', busy = false, onContentHeight }: CircuitVisualizationProps) {
  const dark = useIsDark()
  const p = dark ? DARK : LIGHT
  const svgRef = useRef<SVGSVGElement>(null)
  const scrollRef = useRef<HTMLDivElement>(null)
  const [hovered, setHovered] = useState<number | null>(null)
  const [selected, setSelected] = useState<number | null>(null)
  const [zoom, setZoom] = useState<number | null>(null) // null = auto (fit height)
  const [box, setBox] = useState({ w: 0, h: 0 })

  const layout = useMemo(() => layoutCircuit(gates, qubits), [gates, qubits])
  const hasOps = layout.ops.length > 0
  const row = rowPitch(layout.qubits)
  const rowY = (q: number) => rowAt(q, row)
  const [expanded, setExpanded] = useState(false)

  // Column geometry: each column is as wide as its widest op.
  const geo = useMemo(() => computeGeometry(layout), [layout])

  useEffect(() => {
    if (onContentHeight && geo.height > 0) onContentHeight(Math.ceil(geo.height + HEADER_PX + 8))
  }, [geo.height, onContentHeight])

  // Track the visible area to auto-fit.
  useLayoutEffect(() => {
    const el = scrollRef.current
    if (!el) return
    const ro = new ResizeObserver(([entry]) => {
      const r = entry.contentRect
      setBox((b) => (b.w === r.width && b.h === r.height ? b : { w: r.width, h: r.height }))
    })
    ro.observe(el)
    return () => ro.disconnect()
    // Re-attach when the drawing first appears (the empty state has no scroller).
  }, [hasOps])

  // Docked: fit the height but never below 80% (scroll instead of shrinking
  // into unreadable text). Expanded: fit the whole circuit, up to 160%.
  const autoScale = box.h <= 0
    ? 1
    : expanded
      ? Math.min(1.6, Math.max(0.5, Math.min((box.h - 8) / geo.height, (box.w - 8) / geo.width)))
      : Math.min(1.25, Math.max(0.8, (box.h - 4) / geo.height))
  const scale = zoom ?? autoScale

  const setZoomClamped = useCallback((z: number) => setZoom(Math.min(2.5, Math.max(0.25, Math.round(z * 100) / 100))), [])
  const fitAll = useCallback(() => {
    if (!box.w || !box.h) return
    setZoomClamped(Math.min(1.25, (box.w - 4) / geo.width, (box.h - 4) / geo.height))
  }, [box, geo, setZoomClamped])

  // Ctrl/⌘ + wheel zooms; plain wheel scrolls as usual.
  useEffect(() => {
    const el = scrollRef.current
    if (!el) return
    const onWheel = (e: WheelEvent) => {
      if (!e.ctrlKey && !e.metaKey) return
      e.preventDefault()
      setZoom((z) => {
        const cur = z ?? autoScale
        return Math.min(2.5, Math.max(0.25, cur * (e.deltaY < 0 ? 1.1 : 1 / 1.1)))
      })
    }
    el.addEventListener('wheel', onWheel, { passive: false })
    return () => el.removeEventListener('wheel', onWheel)
  }, [autoScale, hasOps])

  // Selection refers to op ids; drop it when the circuit changes underneath.
  useEffect(() => {
    setSelected((s) => (s !== null && s < layout.ops.length ? s : null))
    setHovered(null)
  }, [layout])

  useEffect(() => {
    if (selected === null && !expanded) return
    const onKey = (e: KeyboardEvent) => {
      if (e.key !== 'Escape') return
      if (selected !== null) setSelected(null)
      else setExpanded(false)
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [selected, expanded])

  // Re-fit when switching between docked and expanded.
  useEffect(() => setZoom(null), [expanded])

  // Export: the toolbar dispatches this event.
  useEffect(() => {
    const onDownload = () => {
      const svg = svgRef.current
      if (!svg) return
      const clone = svg.cloneNode(true) as SVGSVGElement
      clone.setAttribute('xmlns', 'http://www.w3.org/2000/svg')
      clone.setAttribute('viewBox', `0 0 ${geo.width} ${geo.height}`)
      clone.setAttribute('width', String(Math.ceil(geo.width * 2)))
      clone.setAttribute('height', String(Math.ceil(geo.height * 2)))
      const bg = document.createElementNS('http://www.w3.org/2000/svg', 'rect')
      bg.setAttribute('width', '100%')
      bg.setAttribute('height', '100%')
      bg.setAttribute('fill', p.bg)
      clone.insertBefore(bg, clone.firstChild)
      clone.querySelectorAll('[data-hit]').forEach((n) => n.remove())
      const blob = new Blob([new XMLSerializer().serializeToString(clone)], { type: 'image/svg+xml;charset=utf-8' })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = 'circuit-diagram.svg'
      document.body.appendChild(a)
      a.click()
      a.remove()
      URL.revokeObjectURL(url)
    }
    window.addEventListener('download-circuit-svg', onDownload)
    return () => window.removeEventListener('download-circuit-svg', onDownload)
  }, [geo, p.bg])

  const opById = (id: number | null) => (id === null ? undefined : layout.ops.find((o) => o.id === id))
  const hoverOp = opById(hovered)
  const selOp = opById(selected)

  if (layout.ops.length === 0) {
    return (
      <div className={`flex h-full flex-col items-center justify-center gap-1 text-center ${className}`}>
        <p className="text-sm text-editor-text">{busy ? 'Reading your circuit…' : 'No gates to draw yet'}</p>
        {!busy && (
          <p className="text-xs text-editor-text opacity-60">
            Add a gate such as <code className="font-mono">qc.h(0)</code> and the diagram updates as you type.
          </p>
        )}
      </div>
    )
  }

  // The drawing keeps its natural width and is centred in the panel; wider
  // circuits scroll horizontally from the left.
  const drawW = geo.width
  const W = drawW * scale
  const H = geo.height * scale
  const ctrlBtn =
    'grid h-6 w-6 place-items-center rounded text-editor-text opacity-70 transition hover:bg-editor-border/70 hover:opacity-100 focus-visible:outline focus-visible:outline-1 focus-visible:outline-indigo-400'

  return (
    <>
    {expanded && (
      <div className="fixed inset-0 z-[60] bg-black/50 backdrop-blur-[2px]" onClick={() => setExpanded(false)} aria-hidden="true" />
    )}
    <div
      className={
        expanded
          ? 'fixed inset-6 z-[61] flex min-h-0 flex-col overflow-hidden rounded-xl border border-editor-border bg-editor-bg shadow-2xl'
          : `relative flex h-full min-h-0 flex-col ${className}`
      }
      role={expanded ? 'dialog' : undefined}
      aria-modal={expanded || undefined}
      aria-label={expanded ? 'Circuit diagram, expanded' : undefined}
    >
      {/* Summary + zoom */}
      <div className="flex h-8 shrink-0 items-center gap-3 px-3 text-[11px] text-editor-text">
        <span className="font-medium">Circuit</span>
        <span className="tabular-nums opacity-60">
          {layout.qubits} qubit{layout.qubits === 1 ? '' : 's'} · {layout.ops.length} op{layout.ops.length === 1 ? '' : 's'} · depth {layout.columns}
        </span>
        {busy && (
          <span className="flex items-center gap-1.5 opacity-60" aria-live="polite">
            <span className="h-2.5 w-2.5 animate-spin rounded-full border border-indigo-400 border-t-transparent" />
            Updating
          </span>
        )}
        <ul className="ml-auto hidden items-center gap-3 opacity-80 xl:flex" aria-label="Colour key">
          {LEGEND.filter((l) => geo.families.has(l.family)).map((l) => (
            <li key={l.family} className="flex items-center gap-1.5">
              <span className="h-2 w-2 rounded-sm" style={{ background: p[l.family].stroke }} aria-hidden="true" />
              {l.label}
            </li>
          ))}
        </ul>
        <div className="ml-auto flex items-center gap-0.5 xl:ml-3">
          <button type="button" className={ctrlBtn} onClick={() => setZoomClamped(scale / 1.2)} title="Zoom out" aria-label="Zoom out">
            <Minus className="h-3.5 w-3.5" />
          </button>
          <button
            type="button"
            onClick={() => setZoom(null)}
            className="min-w-[3rem] rounded px-1 py-0.5 text-center tabular-nums opacity-70 transition hover:bg-editor-border/70 hover:opacity-100"
            title="Reset to auto size"
          >
            {Math.round(scale * 100)}%
          </button>
          <button type="button" className={ctrlBtn} onClick={() => setZoomClamped(scale * 1.2)} title="Zoom in" aria-label="Zoom in">
            <Plus className="h-3.5 w-3.5" />
          </button>
          <button type="button" className={ctrlBtn} onClick={fitAll} title="Fit whole circuit" aria-label="Fit whole circuit">
            <Scan className="h-3.5 w-3.5" />
          </button>
          <button
            type="button"
            onClick={() => setExpanded((e) => !e)}
            className="ml-1 flex h-6 items-center gap-1 rounded border border-editor-border px-2 text-editor-text opacity-80 transition hover:bg-editor-border/70 hover:opacity-100 focus-visible:outline focus-visible:outline-1 focus-visible:outline-indigo-400"
            title={expanded ? 'Back to the editor (Esc)' : 'Open a large view of the circuit'}
            aria-pressed={expanded}
          >
            {expanded ? <Minimize2 className="h-3.5 w-3.5" /> : <Expand className="h-3.5 w-3.5" />}
            <span>{expanded ? 'Close' : 'Expand'}</span>
          </button>
        </div>
      </div>

      <div ref={scrollRef} className="relative flex min-h-0 flex-1 overflow-auto" onClick={() => setSelected(null)}>
        {/* m-auto centres when it fits and collapses to 0 (scrollable) when it does not. */}
        <div className="relative m-auto shrink-0" style={{ width: W, height: H }}>
          <svg
            ref={svgRef}
            width={W}
            height={H}
            viewBox={`0 0 ${drawW} ${geo.height}`}
            role="img"
            aria-label={`Circuit diagram: ${layout.qubits} qubits, ${layout.ops.length} operations, depth ${layout.columns}`}
            className="block select-none"
            onMouseLeave={() => setHovered(null)}
          >
            <CircuitBody
              layout={layout}
              geo={geo}
              p={p}
              dark={dark}
              row={row}
              drawW={drawW}
              stateOf={(id) => (selected === id ? 'selected' : hovered === id ? 'hover' : 'idle')}
            />

            {/* Hit areas on top so thin lines and dots are easy to point at. */}
            {layout.ops.map((op) => {
              const { top, bottom } = opSpan(op, row)
              const w = Math.max(geo.opW.get(op.id) ?? BOX, 24)
              return (
                <rect
                  key={op.id}
                  data-hit=""
                  x={geo.centers[op.column] - w / 2 - 2}
                  y={top - 2}
                  width={w + 4}
                  height={bottom - top + 4}
                  fill="transparent"
                  className="cursor-pointer"
                  onMouseEnter={() => setHovered(op.id)}
                  onClick={(e) => {
                    e.stopPropagation()
                    setSelected((s) => (s === op.id ? null : op.id))
                  }}
                />
              )
            })}
          </svg>

          {hoverOp && hoverOp.id !== selected && (() => {
            const span = opSpan(hoverOp, row)
            // Above the gate when there is room, otherwise below it.
            const above = span.top * scale > 30
            return (
              <div
                className={`pointer-events-none absolute z-10 -translate-x-1/2 whitespace-nowrap rounded-md border border-editor-border bg-editor-sidebar px-2 py-1 text-[11px] text-editor-text shadow-lg ${above ? '-translate-y-full' : ''}`}
                style={{
                  left: Math.max(geo.centers[hoverOp.column] * scale, 90),
                  top: above ? span.top * scale - 6 : span.bottom * scale + 6,
                }}
              >
                {describeOp(hoverOp)}
              </div>
            )
          })()}
        </div>
      </div>

      {selOp && (
        <div
          className="absolute bottom-2 right-2 z-20 w-60 rounded-lg border border-editor-border bg-editor-sidebar p-3 text-xs text-editor-text shadow-xl"
          onClick={(e) => e.stopPropagation()}
        >
          <div className="mb-1.5 flex items-center justify-between">
            <span className="font-semibold">{selOp.sourceType.toUpperCase()}</span>
            <button type="button" onClick={() => setSelected(null)} className="opacity-60 hover:opacity-100" aria-label="Close details">
              Esc
            </button>
          </div>
          <p className="leading-relaxed opacity-80">{describeOp(selOp)}</p>
          {selOp.angle !== undefined && (
            <p className="mt-1.5 font-mono tabular-nums opacity-80">
              θ = {selOp.angleLabel} = {selOp.angle.toFixed(4)} rad ({((selOp.angle * 180) / Math.PI).toFixed(1)}°)
            </p>
          )}
          <p className="mt-1.5 opacity-50">Moment {selOp.column + 1} of {layout.columns}</p>
        </div>
      )}
    </div>
    </>
  )
}
