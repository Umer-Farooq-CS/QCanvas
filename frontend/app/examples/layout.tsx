import type { Metadata } from 'next'

export const metadata: Metadata = {
  title: 'Examples',
  description:
    'Runnable quantum circuit examples in Cirq, Qiskit and PennyLane: Bell states, teleportation, Grover’s search and more.',
  alternates: { canonical: 'https://www.qcanvas.codes/examples' },
}

export default function Layout({ children }: { children: React.ReactNode }) {
  return children
}
