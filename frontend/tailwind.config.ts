import type { Config } from 'tailwindcss'

const config: Config = {
  content: [
    './pages/**/*.{js,ts,jsx,tsx,mdx}',
    './components/**/*.{js,ts,jsx,tsx,mdx}',
    './app/**/*.{js,ts,jsx,tsx,mdx}',
    './lib/**/*.{js,ts,jsx,tsx,mdx}',
    './types/**/*.{js,ts,jsx,tsx,mdx}',
  ],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        border: 'hsl(var(--border))',
        input: 'hsl(var(--input))',
        ring: 'hsl(var(--ring))',
        background: 'hsl(var(--background))',
        foreground: 'hsl(var(--foreground))',
        primary: {
          DEFAULT: 'hsl(var(--primary))',
          foreground: 'hsl(var(--primary-foreground))',
        },
        secondary: {
          DEFAULT: 'hsl(var(--secondary))',
          foreground: 'hsl(var(--secondary-foreground))',
        },
        destructive: {
          DEFAULT: 'hsl(var(--destructive))',
          foreground: 'hsl(var(--destructive-foreground))',
        },
        muted: {
          DEFAULT: 'hsl(var(--muted))',
          foreground: 'hsl(var(--muted-foreground))',
        },
        accent: {
          DEFAULT: 'hsl(var(--accent))',
          foreground: 'hsl(var(--accent-foreground))',
        },
        popover: {
          DEFAULT: 'hsl(var(--popover))',
          foreground: 'hsl(var(--popover-foreground))',
        },
        card: {
          DEFAULT: 'hsl(var(--card))',
          foreground: 'hsl(var(--card-foreground))',
        },
        quantum: {
          blue: {
            start: '#1e3c72',
            end: '#2a5298',
            light: '#60a5fa',
            dark: '#1e1b4b'
          },
          purple: {
            start: '#667eea',
            end: '#764ba2',
            light: '#8b5cf6',
            dark: '#581c87'
          },
          teal: {
            start: '#00d2ff',
            end: '#3a7bd5',
            light: '#06b6d4',
            dark: '#164e63'
          },
          green: {
            start: '#10b981',
            end: '#059669',
            light: '#34d399',
            dark: '#065f46'
          },
          red: {
            start: '#ef4444',
            end: '#dc2626',
            light: '#f87171',
            dark: '#991b1b'
          },
          yellow: {
            start: '#f59e0b',
            end: '#d97706',
            light: '#fbbf24',
            dark: '#92400e'
          }
        },
        editor: {
          bg: '#131313',
          sidebar: '#1b1b1c',
          border: 'rgba(139, 144, 160, 0.18)',
          text: 'var(--editor-text)',
          accent: '#5850ec', // brand indigo (keep in sync with --editor-accent)
          panelLowest: '#0e0e0e',
          panelHigh: '#2a2a2a',
          panelHighest: '#353535',
          'bg-light': '#f7f9fc',
          'border-light': 'rgba(65, 71, 85, 0.22)'
        },
        // Site tokens: theme-aware via CSS variables in app/globals.css.
        // The IDE can adopt these later (see design-audit/AUDIT.md §4.0).
        qc: {
          bg: 'rgb(var(--qc-bg) / <alpha-value>)',
          surface: 'rgb(var(--qc-surface) / <alpha-value>)',
          'surface-2': 'rgb(var(--qc-surface-2) / <alpha-value>)',
          'surface-3': 'rgb(var(--qc-surface-3) / <alpha-value>)',
          line: 'rgb(var(--qc-line) / <alpha-value>)',
          'line-strong': 'rgb(var(--qc-line-strong) / <alpha-value>)',
          fg: 'rgb(var(--qc-fg) / <alpha-value>)',
          muted: 'rgb(var(--qc-fg-muted) / <alpha-value>)',
          subtle: 'rgb(var(--qc-fg-subtle) / <alpha-value>)',
          accent: 'rgb(var(--qc-accent) / <alpha-value>)',
          'accent-solid': 'rgb(var(--qc-accent-solid) / <alpha-value>)',
          'on-accent': 'rgb(var(--qc-on-accent) / <alpha-value>)',
          success: 'rgb(var(--qc-success) / <alpha-value>)',
          warning: 'rgb(var(--qc-warning) / <alpha-value>)',
          danger: 'rgb(var(--qc-danger) / <alpha-value>)',
          qiskit: 'rgb(var(--qc-qiskit) / <alpha-value>)',
          cirq: 'rgb(var(--qc-cirq) / <alpha-value>)',
          pennylane: 'rgb(var(--qc-pennylane) / <alpha-value>)',
          code: 'rgb(var(--qc-code-bg) / <alpha-value>)',
        },
        framework: {
          qiskit: '#a7c8ff',
          cirq: '#46eaed',
          pennylane: '#ffabf3',
        },
        ethereal: {
          background: '#0b1323',
          primary: '#c3f5ff',
          'primary-container': '#00e5ff',
          'on-primary': '#00363d',
          surface: '#0b1323',
          'surface-variant': '#2d3546',
          'on-surface': '#dbe2f8',
          'on-surface-variant': '#bac9cc',
          'surface-container': '#18202f',
          'surface-container-low': '#131c2b',
          'surface-container-high': '#222a3a',
          'surface-container-highest': '#2d3546',
          'surface-container-lowest': '#060e1d',
          outline: '#849396',
          'outline-variant': '#3b494c',
        },
      },
      fontFamily: {
        headline: ['var(--font-display)', 'Instrument Sans', 'system-ui', 'sans-serif'],
        display: ['var(--font-display)', 'Instrument Sans', 'system-ui', 'sans-serif'],
        sans: ['var(--font-inter)', 'Inter', 'system-ui', 'sans-serif'],
        mono: ['var(--font-jetbrains-mono)', 'JetBrains Mono', 'Fira Code', 'Monaco', 'Consolas', 'monospace'],
      },
      // Site type scale (display sizes; body uses Tailwind defaults)
      fontSize: {
        'display-1': ['clamp(2.25rem, 1.7rem + 2.2vw, 3.25rem)', { lineHeight: '1.06', letterSpacing: '-0.025em' }],
        'display-2': ['clamp(1.75rem, 1.4rem + 1.5vw, 2.5rem)', { lineHeight: '1.1', letterSpacing: '-0.02em' }],
        'title': ['1.25rem', { lineHeight: '1.35', letterSpacing: '-0.01em' }],
      },
      animation: {
        'pulse-glow': 'pulse-glow 2s infinite',
        'slide-in': 'slide-in 0.2s ease-out',
        'fade-in': 'fade-in 0.3s ease-out',
        'slide-up': 'slide-up 0.3s ease-out',
        'bounce-in': 'bounce-in 0.5s ease-out',
        'scale-in': 'scale-in 0.2s ease-out',
      },
      keyframes: {
        'pulse-glow': {
          '0%, 100%': { boxShadow: '0 0 5px rgba(79, 70, 229, 0.5)' },
          '50%': { boxShadow: '0 0 20px rgba(79, 70, 229, 0.8)' },
        },
        'slide-in': {
          '0%': { transform: 'translateX(-100%)' },
          '100%': { transform: 'translateX(0)' },
        },
        'fade-in': {
          '0%': { opacity: '0', transform: 'translateY(-10px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
        'slide-up': {
          '0%': { opacity: '0', transform: 'translateY(10px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
        'bounce-in': {
          '0%': { opacity: '0', transform: 'scale(0.3)' },
          '50%': { opacity: '1', transform: 'scale(1.05)' },
          '70%': { transform: 'scale(0.9)' },
          '100%': { opacity: '1', transform: 'scale(1)' },
        },
        'scale-in': {
          '0%': { opacity: '0', transform: 'scale(0.95)' },
          '100%': { opacity: '1', transform: 'scale(1)' },
        },
      },
      borderRadius: {
        lg: 'var(--radius)',
        md: 'calc(var(--radius) - 2px)',
        sm: 'calc(var(--radius) - 4px)',
      },
      backdropBlur: {
        xs: '2px',
      },
      boxShadow: {
        'qc': 'var(--qc-shadow)',
        'quantum': '0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06)',
        'quantum-lg': '0 10px 15px -3px rgba(0, 0, 0, 0.1), 0 4px 6px -2px rgba(0, 0, 0, 0.05)',
        'quantum-xl': '0 20px 25px -5px rgba(0, 0, 0, 0.1), 0 10px 10px -5px rgba(0, 0, 0, 0.04)',
        'glow': '0 0 20px rgba(79, 70, 229, 0.3)',
        'glow-lg': '0 0 40px rgba(79, 70, 229, 0.4)',
      },
      backgroundImage: {
        'quantum-gradient': 'linear-gradient(135deg, #1e3c72 0%, #2a5298 100%)',
        'quantum-gradient-purple': 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
        'quantum-gradient-teal': 'linear-gradient(135deg, #00d2ff 0%, #3a7bd5 100%)',
        'quantum-gradient-green': 'linear-gradient(135deg, #10b981 0%, #059669 100%)',
        'glass': 'linear-gradient(135deg, rgba(255, 255, 255, 0.1) 0%, rgba(255, 255, 255, 0.05) 100%)',
        'glass-dark': 'linear-gradient(135deg, rgba(0, 0, 0, 0.3) 0%, rgba(0, 0, 0, 0.1) 100%)',
      },
      transitionProperty: {
        'all': 'all',
        'colors': 'color, background-color, border-color, text-decoration-color, fill, stroke',
        'opacity': 'opacity',
        'shadow': 'box-shadow',
        'transform': 'transform',
      },
      transitionTimingFunction: {
        'bounce': 'cubic-bezier(0.68, -0.55, 0.265, 1.55)',
        'smooth': 'cubic-bezier(0.4, 0, 0.2, 1)',
        'out-quick': 'cubic-bezier(0.2, 0.8, 0.2, 1)',
      },
      transitionDuration: {
        '2000': '2000ms',
        '1500': '1500ms',
      },
    },
  },
  plugins: [],
}

export default config
