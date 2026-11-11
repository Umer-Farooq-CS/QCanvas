import type { Metadata } from 'next'

export const metadata: Metadata = {
  title: 'About',
  description:
    'QCanvas is built at FAST University as part of the Open Quantum Workbench initiative. Meet the team and supervisors.',
  alternates: { canonical: 'https://www.qcanvas.codes/about' },
}

export default function Layout({ children }: { children: React.ReactNode }) {
  return children
}
