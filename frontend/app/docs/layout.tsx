import type { Metadata } from 'next'

export const metadata: Metadata = {
  title: 'Documentation',
  description:
    'How to write Cirq, Qiskit and PennyLane code in QCanvas, compile it to OpenQASM 3.0 and read simulation results.',
  alternates: { canonical: 'https://www.qcanvas.codes/docs' },
}

export default function Layout({ children }: { children: React.ReactNode }) {
  return children
}
