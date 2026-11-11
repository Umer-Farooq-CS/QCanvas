import type { Metadata } from 'next'

export const metadata: Metadata = {
  title: 'Achievements',
  robots: { index: false, follow: false },
}

export default function Layout({ children }: { children: React.ReactNode }) {
  return children
}
