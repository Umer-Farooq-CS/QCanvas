import type { Metadata, Viewport } from 'next'
import { Inter, JetBrains_Mono, Instrument_Sans } from 'next/font/google'
import Script from 'next/script'
import { Toaster } from 'react-hot-toast'
import './globals.css'
import ThemeWatcher from '@/components/ThemeWatcher'

const inter = Inter({
  subsets: ['latin'],
  variable: '--font-inter',
  display: 'swap',
})

const jetbrainsMono = JetBrains_Mono({
  subsets: ['latin'],
  variable: '--font-jetbrains-mono',
  display: 'swap',
})

// Display face for headings on site pages (font-display / font-headline).
const instrumentSans = Instrument_Sans({
  subsets: ['latin'],
  variable: '--font-display',
  display: 'swap',
})

export const metadata: Metadata = {
  title: {
    default: 'QCanvas: The Quantum Unified Simulator',
    template: '%s · QCanvas',
  },
  description:
    'QCanvas is a Quantum Unified Simulator for Cirq, Qiskit, and PennyLane. Convert circuits via RAG architecture with real-time OpenQASM 3.0 simulation support.',
  keywords: [
    'quantum computing',
    'quantum circuit simulator',
    'QCanvas',
    'Qiskit',
    'Cirq',
    'PennyLane',
    'OpenQASM 3.0',
    'quantum framework conversion',
    'multi-agent RAG',
    'quantum code editor',
    'quantum unified simulator',
    'Google Quantum AI',
    'IBM Quantum',
    'cross-framework simulation',
  ],
  authors: [{ name: 'QCanvas Team' }],
  metadataBase: new URL('https://www.qcanvas.codes'),
  alternates: {
    canonical: 'https://www.qcanvas.codes/',
  },
  robots: {
    index: true,
    follow: true,
    googleBot: { index: true, follow: true },
  },
  openGraph: {
    type: 'website',
    url: 'https://www.qcanvas.codes/',
    title: 'QCanvas: The Quantum Unified Simulator',
    description:
      'Convert quantum circuits between Cirq, Qiskit, and PennyLane with real-time OpenQASM 3.0 simulation. Powered by a multi-agent RAG architecture.',
    siteName: 'QCanvas',
    images: [
      {
        url: 'https://www.qcanvas.codes/og-image.png',
        width: 1200,
        height: 630,
        alt: 'QCanvas — Quantum Unified Simulator',
      },
    ],
  },
  twitter: {
    card: 'summary_large_image',
    title: 'QCanvas: The Quantum Unified Simulator',
    description:
      'Convert quantum circuits between Cirq, Qiskit, and PennyLane with real-time OpenQASM 3.0 simulation.',
    images: ['https://www.qcanvas.codes/og-image.png'],
  },
  icons: {
    icon: '/favicon.svg?v=2',
    shortcut: '/favicon.svg?v=2',
    apple: '/favicon.svg?v=2',
  },
}

export const viewport: Viewport = {
  width: 'device-width',
  initialScale: 1,
  themeColor: [
    { media: '(prefers-color-scheme: dark)', color: '#0e1014' },
    { media: '(prefers-color-scheme: light)', color: '#f6f7f9' },
  ],
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  const jsonLd = {
    '@context': 'https://schema.org',
    '@type': 'SoftwareApplication',
    name: 'QCanvas',
    applicationCategory: 'ScientificSoftware',
    operatingSystem: 'Web',
    url: 'https://www.qcanvas.codes/',
    description:
      'QCanvas is a Quantum Unified Simulator that enables cross-framework quantum circuit translation and simulation between Cirq, Qiskit, and PennyLane using OpenQASM 3.0 as the universal intermediate format, powered by a multi-agent RAG architecture.',
    offers: {
      '@type': 'Offer',
      price: '0',
      priceCurrency: 'USD',
    },
    author: {
      '@type': 'Organization',
      name: 'QCanvas Team',
      url: 'https://www.qcanvas.codes/',
    },
    featureList: [
      'Quantum circuit conversion between Cirq, Qiskit, and PennyLane',
      'Real-time OpenQASM 3.0 simulation',
      'Multi-agent RAG architecture for AI-assisted circuit generation',
      'Web-based quantum circuit IDE',
      'Cross-framework quantum circuit validation',
    ],
  }

  return (
    <html lang="en" className="dark" suppressHydrationWarning>
      <head>
        {/* Apply the saved theme before first paint so light-theme users
            don't see a dark flash. Mirrors ThemeWatcher's logic. */}
        <script
          dangerouslySetInnerHTML={{
            __html:
              "try{var t=localStorage.getItem('qcanvas-theme')==='light'?'light':'dark';var c=document.documentElement.classList;c.remove('light','dark');c.add(t);}catch(e){}",
          }}
        />
        {/* Google tag (gtag.js) */}
        <Script
          src="https://www.googletagmanager.com/gtag/js?id=G-M23EZDEG9W"
          strategy="afterInteractive"
        />
        <Script id="google-analytics" strategy="afterInteractive">
          {`
            window.dataLayer = window.dataLayer || [];
            function gtag(){dataLayer.push(arguments);}
            gtag('js', new Date());
            gtag('config', 'G-M23EZDEG9W');
          `}
        </Script>
        <script
          type="application/ld+json"
          dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }}
        />
      </head>
      <body className={`${inter.variable} ${jetbrainsMono.variable} ${instrumentSans.variable} font-sans antialiased`}>
        {/* Theme watcher mounts on client to sync html class based on store/localStorage */}
        <ThemeWatcher />
        <div className="app-layout">
          {children}
        </div>
        <Toaster
          position="top-right"
          gutter={8}
          toastOptions={{
            duration: 3000,
            className: 'toast-custom',
          }}
        />
      </body>
    </html>
  )
}
