'use client'

import { memo, useEffect, useMemo, useState } from 'react'
import { Canvas, useThree } from '@react-three/fiber'
import { Line, OrbitControls, RoundedBox, Text } from '@react-three/drei'
import { RotateCcw } from 'lucide-react'
import { describeOp, layoutCircuit, type GateFamily, type LayoutOp, type RawGate } from '@/lib/circuitLayout'

/**
 * 3D circuit view. Uses the same column layout as the 2D diagram, renders only
 * when something changes (frameloop="demand") and caps the pixel ratio, so an
 * idle diagram costs nothing and large circuits stay smooth.
 */

interface CircuitVisualization3DProps {
  gates: RawGate[]
  qubits: number
  className?: string
  busy?: boolean
}

const COL = 1.35
const ROW = 1.25
const MAX_OPS_3D = 400

const FAMILY: Record<GateFamily, string> = {
  clifford: '#6366f1',
  rotation: '#06b6d4',
  multi: '#8b5cf6',
  measure: '#64748b',
}

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

/** The 3D text font has no †, √ or ⟩ glyphs; spell them out. */
const glyphSafe = (s: string) => s.replace('√X', 'SX').replace(/†/g, 'dg').replace(/⟩/g, '>')

const y = (q: number) => -q * ROW
const x = (col: number) => col * COL

function Connector({ px, from, to, color }: { px: number; from: number; to: number; color: string }) {
  const len = Math.abs(y(from) - y(to))
  return (
    <mesh position={[px, (y(from) + y(to)) / 2, 0]}>
      <cylinderGeometry args={[0.035, 0.035, len, 8]} />
      <meshStandardMaterial color={color} />
    </mesh>
  )
}

function Dot({ px, q, color }: { px: number; q: number; color: string }) {
  return (
    <mesh position={[px, y(q), 0]}>
      <sphereGeometry args={[0.15, 16, 12]} />
      <meshStandardMaterial color={color} roughness={0.35} />
    </mesh>
  )
}

function Block({ px, py, h = 0.82, w = 0.82, color, label, sub, lift }: {
  px: number; py: number; h?: number; w?: number; color: string; label: string; sub?: string; lift: boolean
}) {
  return (
    <group position={[px, py, lift ? 0.18 : 0]}>
      <RoundedBox args={[w, h, 0.32]} radius={0.08} smoothness={2}>
        <meshStandardMaterial color={color} roughness={0.45} metalness={0.05} emissive={color} emissiveIntensity={lift ? 0.35 : 0.08} />
      </RoundedBox>
      <Text position={[0, sub ? 0.09 : 0, 0.17]} fontSize={label.length > 3 ? 0.2 : 0.3} color="#ffffff" anchorX="center" anchorY="middle">
        {glyphSafe(label)}
      </Text>
      {sub && (
        <Text position={[0, -0.2, 0.17]} fontSize={0.17} color="#ffffff" fillOpacity={0.85} anchorX="center" anchorY="middle">
          {sub}
        </Text>
      )}
    </group>
  )
}

const Op3D = memo(function Op3D({ op, hovered, onHover }: {
  op: LayoutOp; hovered: boolean; onHover: (id: number | null) => void
}) {
  const px = x(op.column)
  const color = FAMILY[op.family]
  const lo = op.qubits[0]
  const hi = op.qubits[op.qubits.length - 1]
  const handlers = {
    onPointerOver: (e: { stopPropagation: () => void }) => { e.stopPropagation(); onHover(op.id) },
    onPointerOut: () => onHover(null),
  }

  switch (op.kind) {
    case 'barrier':
      return (
        <mesh position={[px, (y(lo) + y(hi)) / 2, 0]} {...handlers}>
          <boxGeometry args={[0.06, Math.abs(y(hi) - y(lo)) + ROW * 0.8, 0.6]} />
          <meshStandardMaterial color="#94a3b8" transparent opacity={0.25} />
        </mesh>
      )
    case 'measure':
      return <group {...handlers}><Block px={px} py={y(op.targets[0])} color={color} label="M" lift={hovered} /></group>
    case 'reset':
      return <group {...handlers}><Block px={px} py={y(op.targets[0])} color={color} label="|0⟩" lift={hovered} /></group>
    case 'swap':
      return (
        <group {...handlers}>
          <Connector px={px} from={lo} to={hi} color={color} />
          {op.controls.map((q) => <Dot key={q} px={px} q={q} color={color} />)}
          {op.targets.map((q) => (
            <group key={q} position={[px, y(q), 0]} rotation={[0, 0, Math.PI / 4]}>
              <mesh><boxGeometry args={[0.5, 0.07, 0.07]} /><meshStandardMaterial color={color} /></mesh>
              <mesh><boxGeometry args={[0.07, 0.5, 0.07]} /><meshStandardMaterial color={color} /></mesh>
            </group>
          ))}
        </group>
      )
    case 'controlled': {
      const t = op.targets[0]
      const symbolic = !op.angleLabel && (op.base === 'x' || op.base === 'z')
      return (
        <group {...handlers}>
          <Connector px={px} from={lo} to={hi} color={color} />
          {op.controls.map((q) => <Dot key={q} px={px} q={q} color={color} />)}
          {symbolic && op.base === 'x' && (
            <group position={[px, y(t), 0]}>
              <mesh>
                <torusGeometry args={[0.3, 0.045, 10, 40]} />
                <meshStandardMaterial color={color} emissive={color} emissiveIntensity={hovered ? 0.5 : 0.1} />
              </mesh>
              <mesh><boxGeometry args={[0.6, 0.05, 0.05]} /><meshStandardMaterial color={color} /></mesh>
              <mesh><boxGeometry args={[0.05, 0.6, 0.05]} /><meshStandardMaterial color={color} /></mesh>
            </group>
          )}
          {symbolic && op.base === 'z' && <Dot px={px} q={t} color={color} />}
          {!symbolic && <Block px={px} py={y(t)} color={color} label={op.label} sub={op.angleLabel} lift={hovered} />}
        </group>
      )
    }
    case 'multi':
      return (
        <group {...handlers}>
          <Block
            px={px} py={(y(lo) + y(hi)) / 2} h={Math.abs(y(hi) - y(lo)) + 0.82}
            color={color} label={op.label} sub={op.angleLabel} lift={hovered}
          />
        </group>
      )
    default:
      return (
        <group {...handlers}>
          <Block px={px} py={y(op.targets[0])} color={color} label={op.label} sub={op.angleLabel} lift={hovered} />
        </group>
      )
  }
})

/** Frames the circuit whenever its size changes (or the view is reset). */
function CameraRig({ width, height, nonce }: { width: number; height: number; nonce: number }) {
  const { camera, controls, size, invalidate } = useThree()
  useEffect(() => {
    const cx = width / 2
    const cy = -height / 2
    const fov = ('fov' in camera ? (camera as { fov: number }).fov : 45) * (Math.PI / 180)
    const aspect = size.width / Math.max(size.height, 1)
    const fitH = (height + 2.2) / 2 / Math.tan(fov / 2)
    const fitW = (width + 2.6) / 2 / Math.tan(fov / 2) / aspect
    const dist = Math.min(Math.max(fitH, fitW, 4), 60)
    camera.position.set(cx - dist * 0.18, cy + dist * 0.22, dist)
    camera.lookAt(cx, cy, 0)
    const c = controls as unknown as { target?: { set: (a: number, b: number, c: number) => void }; update?: () => void } | null
    c?.target?.set(cx, cy, 0)
    c?.update?.()
    invalidate()
    // size is deliberately not a dependency: resizing the panel should not
    // throw away the user's orbit.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [width, height, nonce, camera, controls, invalidate])
  return null
}

export default function CircuitVisualization3D({ gates, qubits, className = '', busy = false }: CircuitVisualization3DProps) {
  const dark = useIsDark()
  const [hovered, setHovered] = useState<number | null>(null)
  const [nonce, setNonce] = useState(0)
  const layout = useMemo(() => layoutCircuit(gates, qubits), [gates, qubits])
  const ops = layout.ops.length > MAX_OPS_3D ? layout.ops.slice(0, MAX_OPS_3D) : layout.ops
  const truncated = layout.ops.length - ops.length
  const columns = ops.reduce((m, o) => Math.max(m, o.column + 1), 1)
  const width = (columns - 1) * COL
  const height = (layout.qubits - 1) * ROW
  const hoverOp = hovered === null ? undefined : ops.find((o) => o.id === hovered)

  useEffect(() => setHovered(null), [layout])

  if (layout.ops.length === 0) {
    return (
      <div className={`flex h-full items-center justify-center text-sm text-editor-text ${className}`}>
        {busy ? 'Reading your circuit…' : 'No gates to draw yet'}
      </div>
    )
  }

  const bg = dark ? '#131313' : '#ffffff'
  const wire = dark ? '#4b5263' : '#94a3b8'
  const labelColor = dark ? '#8b93a7' : '#64748b'

  return (
    <div className={`relative flex h-full min-h-0 flex-col ${className}`}>
      <div className="flex h-8 shrink-0 items-center gap-3 px-3 text-[11px] text-editor-text">
        <span className="font-medium">Circuit · 3D</span>
        <span className="tabular-nums opacity-60">
          {layout.qubits} qubits · {layout.ops.length} ops · depth {layout.columns}
        </span>
        {busy && (
          <span className="flex items-center gap-1.5 opacity-60" aria-live="polite">
            <span className="h-2.5 w-2.5 animate-spin rounded-full border border-indigo-400 border-t-transparent" />
            Updating
          </span>
        )}
        <span className="ml-auto hidden opacity-50 lg:inline">Drag to orbit · scroll to zoom · right-drag to pan</span>
        <button
          type="button"
          onClick={() => setNonce((n) => n + 1)}
          className="flex items-center gap-1 rounded px-1.5 py-0.5 opacity-70 transition hover:bg-editor-border/70 hover:opacity-100"
          title="Reset camera"
        >
          <RotateCcw className="h-3 w-3" /> Reset view
        </button>
      </div>

      <div className="relative min-h-0 flex-1">
        <Canvas
          frameloop="demand"
          dpr={[1, 2]}
          gl={{ antialias: true, powerPreference: 'high-performance' }}
          camera={{ fov: 45, near: 0.1, far: 500, position: [0, 0, 12] }}
          onPointerMissed={() => setHovered(null)}
        >
          <color attach="background" args={[bg]} />
          <ambientLight intensity={dark ? 0.75 : 0.95} />
          <directionalLight position={[6, 10, 12]} intensity={1.1} />
          <directionalLight position={[-8, -4, 6]} intensity={0.35} />

          {Array.from({ length: layout.qubits }, (_, q) => (
            <group key={q}>
              <Line points={[[-1, y(q), 0], [width + 1, y(q), 0]]} color={wire} lineWidth={1.5} />
              <Text position={[-1.45, y(q), 0]} fontSize={0.3} color={labelColor} anchorX="center" anchorY="middle">
                {`q${q}`}
              </Text>
            </group>
          ))}

          {ops.map((op) => (
            <Op3D key={op.id} op={op} hovered={hovered === op.id} onHover={setHovered} />
          ))}

          <OrbitControls makeDefault enableDamping={false} maxDistance={80} minDistance={2} />
          <CameraRig width={width} height={height} nonce={nonce} />
        </Canvas>

        {hoverOp && (
          <div className="pointer-events-none absolute left-3 top-2 rounded-md border border-editor-border bg-editor-sidebar px-2 py-1 text-[11px] text-editor-text shadow-lg">
            {describeOp(hoverOp)}
          </div>
        )}
        {truncated > 0 && (
          <div className="pointer-events-none absolute bottom-2 left-3 text-[11px] text-editor-text opacity-70">
            Showing the first {MAX_OPS_3D} operations in 3D. Switch to 2D for all {layout.ops.length}.
          </div>
        )}
      </div>
    </div>
  )
}
