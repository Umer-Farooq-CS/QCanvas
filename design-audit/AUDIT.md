# QCanvas design audit: live site, Nov 2026

Audited https://qcanvas.codes (frontend) and https://api.qcanvas.codes (API) at 1440×900, 700×900 (IDE only) and 390×844, in dark and light themes. I used the public demo account (`demo@qcanvas.dev`) read-only, except for running the default Bell-state example once.

Screenshots are in `design-audit/` as `live-<page>-<viewport>.png`. They are git-ignored: re-run the audit or ask the design agent for the set.

Severity:
- **P0**: broken, or will embarrass us at the workshop.
- **P1**: clearly hurts credibility, usability or accessibility.
- **P2**: polish.

---

## 1. Live-site bugs (functional)

| # | Sev | Page | Finding | Evidence | Recommended fix |
|---|---|---|---|---|---|
| B1 | P0 | /app | **The OpenQASM tab shows `0`** after running the default Cirq Bell state. Conversion succeeds (`POST /api/converter/convert` 200), but the panel renders a bare `0`. | `live-app-desktop-dark-openqasm.png` | `ResultsPane.tsx:712` uses `compiledQasm && …`, which renders a numeric `0`. Use `typeof compiledQasm === 'string' && compiledQasm.length > 0`. Coerce `conversionResult.data.qasm_code` to a string in `components/ide/useExecutionActions.ts:257`, and check what the API actually returns. |
| B2 | P0 | /app | **Uncaught Monaco error on every QASM view:** `qasm: with groups, all characters should be matched in consecutive groups`. OpenQASM highlighting dies. | console log captured while running | `components/EditorPane.tsx:633-634`: `/(OPENQASM)(\s+)(\d+(\.\d+)?)(\s*;)/` has a nested capture group. Change it to `/(OPENQASM)(\s+)(\d+(?:\.\d+)?)(\s*;)/` with 4 actions: `["keyword","","number","delimiter"]`. |
| B3 | P0 | /app (demo) | **Every workshop attendee shares one writable demo account.** It already holds 5 copies of `bell_state_cirq.py` and a junk file `borr openhimer.py`, and one user can rename or delete files for everyone. | `live-app-desktop-dark-file.png` | Before Friday, either make demo sessions sandboxed or read-only (server side), or reset the demo workspace and ask attendees to sign up. At minimum, clean the demo workspace on Thursday night. |
| B4 | P1 | /app, /achievements | **Mojibake in seeded content:** `# Expected: 50% \|00???, 50% \|11???` in the demo file, and `Reach Level 5 ??? Quantum Novice` in achievements. `⟩` and `—` were stored as `???`. | `live-app-desktop-dark-run.png`, `live-achievements-desktop.png` | Re-seed the demo files and achievement descriptions with UTF-8 (check DB client encoding and seed scripts). |
| B5 | P1 | /profile, /achievements | **Deep links bounce:** a signed-in user loading `/profile` directly goes `/profile → /login → /app` and never reaches the profile. | navigation trace | `useRequireAuth` redirects before the persisted auth store hydrates, and /login drops the original target. Wait for hydration, then redirect to `/login?next=/profile` and honour `next` (the new `getNextPath` helper does this for login). |
| B6 | P1 | /app Stats | **"Fidelity 100.0%" is a hardcoded fallback** (`ResultsPane.tsx:188-191`). Showing a made-up metric to students is a credibility risk. | `live-app-desktop-dark-stats.png` | Show "—" or hide the card when the backend doesn't return `fidelity`. |
| B7 | P1 | all | **The page scroll container is `<body>`, not the window** (`html, body {height:100%; overflow-y:auto}` in globals.css). `window.scrollY` is always 0, so the Navbar "scrolled" style, the docs sub-nav offset and the landing scroll listener never fire. It also breaks mobile URL-bar collapse and fullPage capture. | `scrollHeight` = viewport height on every page | Remove `height:100%`/`overflow-y:auto` from html/body and use `overflow-x: clip` on body. **Done in this branch.** |
| B8 | P1 | all | **No per-page `<title>`.** Every route is "QCanvas: The Quantum Unified Simulator", so tabs are indistinguishable at the workshop. | page titles | Add `metadata` in route `layout.tsx` files, or `document.title` for client pages. **Done for the marketing, auth and profile routes in this branch.** |
| B9 | P1 | / | `og-image.png` is **6.15 MB** (2816×1536). Link unfurls (WhatsApp, Slack, LinkedIn) are slow or fail. It is also generated art with an image-generator sparkle watermark in the bottom-right corner. | `curl` size, the image itself | Replace it with a 1200×630 typographic card under 100 KB. **Done in this branch:** a new 1200×630 image (wordmark, headline, the Bell-state QASM and its counts). |
| B10 | P2 | /about, footer | Community links point to accounts that don't exist (`discord.gg/qcanvas`, `twitter.com/qcanvas_dev`, `linkedin.com/company/qcanvas`). The home footer shows them as disabled "Coming soon" `href="#"` links. | `live-about-desktop.png` | Hide them until they exist. **Done in this branch.** Their source is `lib/config.ts socialLinks`. |
| B11 | P2 | /about | The co-supervisor (Dr. Muhammad Nouman Noor) is listed with **Abdullah Mehmood's email** (`lib/config.ts` `supervisors[1].email`). | `lib/config.ts` | Fix the email in config. Not done here because `lib/**` is off-limits for this branch. |
| B12 | P2 | /login | Chrome warns "Input elements should have autocomplete attributes" on the password field. | console | Add `autoComplete="current-password"`, `"email"` and `"new-password"`. **Done in this branch.** |
| B13 | P2 | layout | No pre-paint theme script. Light-theme users get a dark flash on every page load, because SSR renders `class="dark"` and ThemeWatcher switches after hydration. | reload in light theme | Add an inline `<script>` in `<head>` that sets the class from `localStorage['qcanvas-theme']`. **Done in this branch.** |
| B14 | P2 | /app | Monaco loads from `cdn.jsdelivr.net`. If the campus network filters or slows that CDN, the editor never appears. | network log | Self-host Monaco (`@monaco-editor/react` `loader.config({ paths: { vs: '/monaco/vs' } })`), or at least test on the workshop Wi-Fi. |

No failed network requests (4xx/5xx) and no console errors on any public page. API calls on /app returned 200.

## 2. Design findings (prioritised)

| # | Sev | Page | Finding | Screenshot | Recommended fix |
|---|---|---|---|---|---|
| D1 | P1 | /, /docs, /examples, /login, /signup | **Generic "AI landing page" look:** gradient text (purple → cyan → pink → orange) in almost every heading, three large blurred orbs (`blur-[100px]`, 500px), a dot grid, floating Atom, Sparkles and Cpu icons with infinite `float`, `animate-ping` dots and a bouncing chevron. | `live-home-desktop.png` | Use one solid text colour for headings and one accent (blue) for actions and links. Remove the orbs, floating icons, pings and bounce. |
| D2 | P1 | / | **Hollow or fake copy:** "Next-Generation Quantum Development" badge, "Join thousands of researchers…" (fake social proof), "Community Sharing … public circuit galleries" (doesn't exist), "multi-agent RAG support" on the simulator card, "Six powerful tools — one unified platform", and a hidden SEO `<h1>` calling it an "Open-Source Quantum Circuit Simulator" even though `LICENSE` is the proprietary Open Quantum Workbench licence. The two "features" sections repeat each other: 12 cards for 4 real capabilities. | `live-home-desktop.png` | Rewrite around what the product actually does: write Cirq/Qiskit/PennyLane, see the OpenQASM 3.0, run it, read the histogram. Show a real code → QASM → counts example instead of cards. |
| D3 | P1 | /about | **Fabricated testimonial** ("QCanvas has changed how students visualize…") under a "25+" stat. "Join operators already exploring the quantum landscape". | `live-about-desktop.png` | Remove the quote. Keep the honest facts: FAST University, the Open Quantum Workbench initiative, the supervisors and the team. |
| D4 | P1 | layout | JSON-LD has a fabricated `aggregateRating` (5 stars from 1 rating). This can get the site penalised in search. | `app/layout.tsx` | Remove it. **Done in this branch.** |
| D5 | P1 | / , /about, /examples | **Content hidden until scroll:** cards start at `opacity:0` and depend on CSS animation or an IntersectionObserver (`reveal-on-scroll`). Readers without JS, crawlers, print and slow laptops see blank sections, and with reduced motion they never appear. | `live-about-desktop.png` (blank middle), `live-examples-desktop.png` | Render content visible by default. If you animate, animate only transform and opacity from a visible state, and skip it under `prefers-reduced-motion`. |
| D6 | P1 | all marketing | **Rainbow card system:** each card has its own accent (indigo, violet, cyan, emerald, amber, pink) on gradient `border-image` tops, plus hover glows. No hierarchy; it reads as templated. | `live-home-desktop.png` | Use neutral surfaces with 1px borders. Keep colour for the three framework identities (Qiskit, Cirq, PennyLane) only. |
| D7 | P1 | light theme | Low contrast: `.light .text-gray-400 → #94a3b8` (2.6:1 on white), the badge pills and "Explore Features" chip on the light home page are almost invisible, and `.light .text-gray-300 → #cbd5e1` (1.5:1) is declared before a later override. | `live-home-desktop-light.png` | Use semantic tokens (`--qc-fg-muted` #4b5262 is 7.8:1, `--qc-fg-subtle` #646b7a is 5.0:1) rather than overriding gray utilities. |
| D8 | P1 | / | **Footer grid broken:** `md:col-span-2` plus 3 columns in `grid-cols-4` pushes "Framework Docs" onto its own row. | `live-home-desktop.png` (bottom) | Rebuild the footer as a simple 3-column row. **Done.** |
| D9 | P2 | /login, /signup | The logo has infinite `animate-pulse`, the "QCanvas" wordmark pulses, and so does an underline bar. The glass card has an indigo glow shadow. Demo credentials appear twice. | `live-login-desktop.png` | Use a static logo and a plain card. Make the demo button primary-adjacent and show the credentials once. |
| D10 | P2 | /examples | The hero takes 450px for an icon disc, "Quantum Examples" with a gradient word, and a 2-line subtitle. The filters sit in a glass card and the grid is hidden until scrolled. | `live-examples-desktop.png` | Use a compact header (title, one line, count) with the filters directly under it. |
| D11 | P2 | /docs | Same hero decoration as home (orbs, floating icons, pings). On mobile the sub-nav buttons run off-screen without a scroll affordance. | `live-docs-mobile.png` | Use a compact page header and make the sub-nav horizontally scrollable with a fade mask. |
| D12 | P2 | / | `/` is a `"use client"` page (8.3 kB, 197 kB first-load JS) that imports 20 icon components, including animated SVGs. It also re-renders on every scroll event (`setScrollY` was never used). | build output | Make it a Server Component with small client islands (Navbar, "Open example" buttons). **Done.** |
| D13 | P2 | all | Global `section { transition: all .8s }` animates every layout change on every page, including the IDE. `.hover-lift` uses `transition: all .4s` and a −6px lift. | globals.css | Remove both, and transition only `transform`, `opacity` and `color`, at 150–200ms. **Done.** |
| D14 | P2 | all | No `prefers-reduced-motion` handling anywhere. | globals.css | Add a global reduced-motion block. **Done.** |
| D15 | P2 | /about | "Democratizing the Quantum Horizon" headline. The page mixes slate and indigo palettes, uses uppercase tracked micro-labels everywhere, `rounded-3xl` bento cards and `backdrop-blur-xl` chips. | `live-about-desktop.png` | Use plain, factual sections: what it is, who built it, supervisors, source code. |
| D16 | P2 | /achievements, /profile | Rarity colours (blue, purple, green, gray) on borders and progress bars, plus XP chips on every card corner. Gradient avatar and banner. Achievement icons render as generic blobs. | `live-achievements-desktop.png`, `live-profile-desktop.png` | Neutral cards, a single accent for progress, and rarity as a small text label. |

## 3. What this branch changes (non-IDE)

- **Tokens:** `--qc-*` CSS variables for dark and light (bg, surface 1–3, line, fg, fg-muted, fg-subtle, accent, accent-solid, success, warning, danger), exposed in Tailwind as `qc-*` colours, plus `font-display` (Instrument Sans) and a small type scale. Existing IDE token names and values are untouched.
- **Global hygiene:** the window scrolls instead of `<body>` (B7), a reduced-motion block, no global `section` transition, a pre-paint theme script (B13), and no fake `aggregateRating`.
- **Landing page:** Server Component; real product copy; a code → OpenQASM → histogram demonstration in static markup; one accent; no orbs, floating icons or gradient text.
- **Navbar:** solid surface, active state, accessible mobile menu, no wordmark gradient.
- **Docs, Examples, About:** quiet page headers, no decorative motion, content visible without scroll triggers, no fake links or testimonial.
- **Auth pages:** a calm card on a plain background, no pulsing logo, and autocomplete attributes. The session logic (`getNextPath`, `canAccessApp`, the `qcanvas-auth-message` toast, `hasValidAuth`) is unchanged.
- **Profile, achievements and gamification toasts:** neutral surfaces, no infinite pulses or bounces, and no emoji.
- **Shared site components** (new, in `components/site/`):
  - `SiteFooter`
  - `AuthShell` (frame for the auth pages)
  - `CodeSample` (build-time syntax highlighting, no client JS)
  - `OpenExampleButton` (the only client island on `/` besides the Navbar)
- **Global primitives** for any page to use:
  - `qc-btn`, `qc-btn-primary`, `qc-btn-secondary`, `qc-btn-quiet`
  - `qc-input`, `qc-select`, `qc-card`, `qc-link`, `qc-eyebrow`
  - `qc-code`, `qc-logo`, `qc-fade-in`, `qc-pop-in`
- **New pages and assets:** a custom 404 page, and an OG image (71 KB).

### First-load JS (production build, before → after)

| Route | Before | After |
|---|---|---|
| `/` | 197 kB (8.34 kB page) | **117 kB** (2 kB page) |
| `/about` | 200 kB | 122 kB |
| `/login` | 181 kB | 118 kB |
| `/signup` | 190 kB | 118 kB |
| `/docs` | 200 kB | 187 kB |
| `/examples` | 196 kB | 187 kB |
| `/profile` | 198 kB | 191 kB |
| `/achievements` | 192 kB | 185 kB |
| `/app` (not edited) | 551 kB | 544 kB |
| shared by all | 87.5 kB | 87.5 kB |

### Token reference (`app/globals.css`)

| Token | Dark | Light | Use |
|---|---|---|---|
| `--qc-bg` | `#0e1014` | `#f6f7f9` | page background |
| `--qc-surface` | `#15171c` | `#ffffff` | cards, panels |
| `--qc-surface-2` | `#1b1e24` | `#f0f2f5` | raised, hover |
| `--qc-surface-3` | `#23272e` | `#e7eaef` | tracks, active tab |
| `--qc-line` | `#2a2f38` | `#e1e4ea` | borders |
| `--qc-line-strong` | `#3a404c` | `#cdd2da` | input borders, hover borders |
| `--qc-fg` | `#e6e8ec` (15.5:1) | `#11141a` (17:1) | primary text |
| `--qc-fg-muted` | `#a1a8b5` (8.0:1) | `#4b5262` (7.6:1) | body and secondary text |
| `--qc-fg-subtle` | `#8a92a1` (5.9:1) | `#646b7a` (5.0:1) | captions, meta |
| `--qc-accent` | `#6ea8ff` (7.9:1) | `#1f5fd1` (5.4:1) | links, focus, data |
| `--qc-accent-solid` | `#2563eb` | `#2563eb` | primary button fill (white text 5.2:1) |
| `--qc-success` / `warning` / `danger` | `#3ecf8e` / `#f0b429` / `#f26d6d` | `#15803d` / `#a16207` / `#c82828` | status |
| `--qc-qiskit` / `cirq` / `pennylane` | `#a7c8ff` / `#46eaed` / `#ffabf3` | `#2563eb` / `#0b7d85` / `#b832a6` | framework identity (same as Monaco tokens) |

Motion: UI transitions run 150–220ms on `--qc-ease-out` (`cubic-bezier(.2,.8,.2,1)`), animating transform, opacity and colour only. `prefers-reduced-motion` collapses all transitions and animations except spinners.

---

## 4. IDE visual issues

For the IDE agent. **Not changed in this branch.** Line numbers are from commit `27bf2ae`.

Proposed values align the IDE with the new `--qc-*` tokens so marketing and IDE read as one product. The dark proposals keep the IDE's neutral character, nudged slightly cool to match the site. The light proposals fix contrast.

### 4.0 Token retune (tailwind.config.ts `editor.*`, `framework.*`)

| Token | Current | Proposed (dark) | Proposed (light, via CSS var) | Note |
|---|---|---|---|---|
| `editor.bg` | `#131313` (static hex) | `var(--editor-surface)` with dark `#121418` | `#ffffff` | Making it a CSS var removes the need for `.light .bg-editor-bg !important` (globals.css:486). |
| `editor.sidebar` | `#1b1b1c` | `var(--editor-surface-low)` with dark `#16191e` | `#f6f7f9` | Replaces globals.css:490. |
| `editor.panelLowest` | `#0e0e0e` | dark `#0e1014` (= `--qc-bg`) | `#eef0f3` | |
| `editor.panelHigh` | `#2a2a2a` | dark `#23272e` | `#e7eaef` | |
| `editor.panelHighest` | `#353535` | dark `#2c313a` | `#dde1e7` | |
| `editor.border` | `rgba(139,144,160,.18)` | `#2a2f38` (solid, = `--qc-line`) | `#e1e4ea` | Solid borders avoid the double-alpha muddiness where panels overlap. |
| `editor.accent` | `#3291ff` | `#2563eb` for fills (white text 5.2:1) and `#6ea8ff` for text and icons | `#1f5fd1` | `#3291ff` with white text is only 3.4:1. |
| `framework.cirq` | `#46eaed` static | keep dark `#46eaed` | `#0b7d85` | Light `#0f9ea8` is 3.2:1 on white, which fails AA for text. |
| `framework.qiskit` / `pennylane` | static hex | keep dark | `#2563eb` / `#b832a6` | Point the Tailwind tokens at the existing `--framework-*` vars (globals.css:35-37, 68-70) so light mode actually switches. |
| `quantum.blue.light` | `#60a5fa` | `#6ea8ff` (= `--qc-accent`) | `#1f5fd1` | |

### 4.1 MenuBar (`components/ide/MenuBar.tsx`)

| Line | Element | Current | Proposed |
|---|---|---|---|
| :294 | bar | `h-12 bg-editor-sidebar`, no border | `h-11 bg-editor-sidebar border-b border-editor-border` |
| :315 | wordmark | `quantum-gradient bg-clip-text` (purple → cyan gradient text) | `text-[15px] font-semibold text-[var(--qc-fg)] tracking-tight` (solid) |
| :320 | menu group | always renders 7 items, no overflow handling, clips "Help" at 390px | `hidden md:flex` for File…Help; below `md` show a single `Menu` icon button that opens the same items in one dropdown |
| :325 | item open state | `bg-editor-bg/10 text-white` (invisible) | `bg-editor-panelHigh text-[var(--qc-fg)]` |
| :325 | item idle | `text-editor-text hover:bg-editor-panelHigh/10` | `text-[var(--qc-fg-muted)] hover:bg-editor-panelHigh hover:text-[var(--qc-fg)]`, `transition-colors duration-150` |
| :337 | dropdown | always `left-0` (Help menu runs off-screen) | `right-0` for the last two menus; `shadow-[0_8px_24px_rgba(0,0,0,.35)] rounded-lg py-1` |
| :346 | dropdown row hover | `hover:border hover:rounded-md` (1px layout shift) | `hover:bg-editor-panelHigh` (no border change) |
| :355 | shortcut hint | `text-black dark:text-gray-400` | `font-mono text-[11px] text-[var(--qc-fg-subtle)]` |
| :370 | Templates | `hover:bg-editor-bg/10` | `hover:bg-editor-panelHigh` |
| :512, :612 | modal close | `✕` glyph | lucide `X` (`w-4 h-4`) in a 32px icon button with `aria-label="Close"` |
| live, right side | "Circuit Code" pill | wraps onto 2 lines at 700px | `whitespace-nowrap` and `hidden lg:inline-flex` |

### 4.2 ActivityBar (`components/ide/ActivityBar.tsx`)

| Line | Element | Current | Proposed |
|---|---|---|---|
| :37 | bar | `w-12 bg-editor-sidebar` | add `border-r border-editor-border` |
| :54 | active | `bg-gray-600/20 text-white shadow-[0_0_18px_rgba(70,234,237,.14)]` (cyan glow) | `bg-editor-panelHigh text-[var(--qc-fg)]`, no glow |
| :55 | idle hover | `hover:bg-gray-400/50` (heavy grey slab) | `text-[var(--qc-fg-subtle)] hover:text-[var(--qc-fg)] hover:bg-editor-panelHigh/60` |
| :59 | active indicator | `bg-framework-cirq` (#46eaed), inset 4px | `bg-[var(--qc-accent)]`, `-left-1` so it touches the bar edge, `h-5 w-[2px]` |

### 4.3 Explorer (`components/ide/ExplorerView.tsx`)

| Line | Element | Current | Proposed |
|---|---|---|---|
| :673 | header | `bg-gray-500/10 backdrop-blur-sm` | `bg-transparent border-b border-editor-border` (remove blur) |
| :676 | "EXPLORER" label | `text-[11px] tracking-[0.14em] uppercase text-black dark:text-gray-400` | `text-[11px] font-medium tracking-[0.06em] uppercase text-[var(--qc-fg-subtle)]` (also fixes pure black in light) |
| :679 | counts | `text-black dark:text-gray-500` | `text-[var(--qc-fg-subtle)]` |
| :782, :790 | icon buttons | `hover:bg-gray-100` (white flash in dark) | `hover:bg-editor-panelHigh` |
| :598 | file row | `py-1.5 text-sm rounded-md border` (about 30px) | `h-7 text-[13px] rounded-md border border-transparent` |
| :600 | **selected row** | `bg-editor-accent/90 border-editor-accent text-gray-100` (solid bright-blue pill) | `bg-[color-mix(in_srgb,var(--qc-accent)_14%,transparent)] text-[var(--qc-fg)]` plus `shadow-[inset_2px_0_0_var(--qc-accent)]` |
| :601 | idle row | `text-gray-900 dark:text-gray-100 hover:bg-editor-border/40` | `text-[var(--qc-fg-muted)] hover:bg-editor-panelHigh/60 hover:text-[var(--qc-fg)]` |
| :634 | class typo | `hover:bg-editor-border/70bg-editor-accent/90` | add the missing space |
| :45 | active-row icon | forced white | keep the file-type colour |
| :708, :968 | context menus | `backdrop-blur-xl shadow-[0_24px_48px_rgba(0,0,0,.5)]` | solid `bg-editor-panelHigh`, `shadow-[0_8px_24px_rgba(0,0,0,.35)]`, no blur |
| :26-41 | file icon colours | `.md` sky-300, `.json` emerald-300 (arbitrary) | `.py` qiskit, `.qasm` cirq, `.js` pennylane; everything else `--qc-fg-subtle` |

### 4.4 Editor tabs and toolbar

| File:line | Element | Current | Proposed |
|---|---|---|---|
| EditorTabs.tsx:22 | strip | `bg-slate-100 dark:bg-slate-900` (blue-tinted, clashes with the neutral editor) | `bg-editor-sidebar border-b border-editor-border h-9` |
| EditorTabs.tsx:29 | active tab | `bg-gray-200 text-white dark:bg-gray-800` (white text on gray-200 in light) | `bg-editor-bg text-[var(--qc-fg)]` plus `shadow-[inset_0_2px_0_var(--qc-accent)]` (top accent line) |
| EditorTabs.tsx:30 | inactive tab | `bg-editor-sidebar text-editor-text` | `text-[var(--qc-fg-subtle)] hover:text-[var(--qc-fg-muted)]` |
| EditorTabs.tsx:39 | close | `<button>` nested in `<button>` (invalid HTML) | make the tab a `div role="tab"` with two sibling buttons; close `opacity-0 group-hover:opacity-100` except on the active tab |
| EditorPane.tsx:1262 | toolbar | `backdrop-blur-sm` | remove the blur |
| EditorPane.tsx:1338 | **Run** | `bg-gradient-to-r from-quantum-blue-light/20 to-quantum-blue-light/10` (low-emphasis primary) | solid primary: `bg-[#2563eb] hover:bg-[#1d4ed8] text-white`, `h-8 px-3 rounded-md font-medium`, `active:scale-[.98] transition-[background-color,transform] duration-150` |
| EditorPane.tsx:1333 | split wrapper | `shadow-[0_4px_16px_rgba(0,0,0,.22)]` | none |
| EditorPane.tsx:1362 | run menu | `rounded-xl backdrop-blur-md shadow-[0_20px_45px…]` | `rounded-lg bg-editor-panelHigh shadow-[0_8px_24px_rgba(0,0,0,.35)]`, no blur |
| EditorPane.tsx:1380 | mode active | `shadow-[0_0_18px_rgba(59,130,246,.25)]` glow | no glow; `bg-[color-mix(in_srgb,var(--qc-accent)_14%,transparent)] text-[var(--qc-fg)] ring-1 ring-[var(--qc-accent)]/40` |

### 4.5 Monaco themes (`components/EditorPane.tsx`)

`quantum-dark` (:393) is good. Keep the palette and fix these:

| Key | Current | Proposed |
|---|---|---|
| `editor.background` | `#131313` | `#121418` (matches the new `editor.bg`) |
| `editor.lineHighlightBackground` | `#1b1b1c` | `#181b21` |
| `editorGutter.background` | `#0e0e0e` (darker than the code area, looks like a separate panel) | same as the background, `#121418` |
| `editorLineNumber.foreground` | `#8b90a0` | `#5b6270` (quieter) |
| `editorLineNumber.activeForeground` | `#e5e2e1` | `#a1a8b5` |
| `editor.selectionBackground` | `#2f4d74` | `#264f8a` |
| comment token | `8B90A0` italic | `7C8493` italic (4.6:1 on `#121418`) |
| string vs. function | both `46EAED` | string `46EAED`, function `E5E2E1` with `fontStyle: ''` (two cyan roles are hard to scan) |

`quantum-light` (:431):

| Key | Current | Proposed |
|---|---|---|
| background | `#f7f9fc`, overridden to `#fff` by globals.css:683 | `#ffffff`, and delete the CSS override (:683, :594, :687) |
| string / function | `0F9EA8` (3.2:1, fails AA) | `0B7D85` |
| line numbers | `#64748b` | `#8a919e`, active `#11141a` |

- globals.css:699-713 target `.token.*` classes that Monaco never emits. Delete them.
- Fix the QASM Monarch rule (see B2).

### 4.6 Results pane (`components/ResultsPane.tsx`)

| Line | Element | Current | Proposed |
|---|---|---|---|
| :668 | header | `h-12 bg-editor-sidebar/10` | `h-10 bg-editor-sidebar border-b border-editor-border` |
| :693-695 | **tabs** | active `bg-editor-accent text-gray-100` (solid bright-blue pill, louder than Run) | underline tabs: `h-10 px-3 text-[13px] text-[var(--qc-fg-subtle)]`, active `text-[var(--qc-fg)] shadow-[inset_0_-2px_0_var(--qc-accent)]` |
| :702 | error count | `bg-red-500 text-white rounded-full` | `bg-[#f26d6d]/15 text-[#f26d6d] rounded px-1.5 font-mono text-[11px]` |
| :714-761 | action buttons | `btn-ghost p-1` (each in a 40px bordered box with 0.75rem radius) | `h-7 w-7 rounded-md text-[var(--qc-fg-subtle)] hover:bg-editor-panelHigh hover:text-[var(--qc-fg)]`, no border |
| :1006-1012 | Execution Summary | `bg-gray-900 border-gray-700 text-green-400` (everything green, terminal cosplay) | `bg-editor-panelLowest border-editor-border text-[var(--qc-fg)]`; colour only the status line (`--qc-success`) |
| :712 | QASM header condition | `compiledQasm && …` renders `0` | see B1 |
| :591-595 | log glyphs | `✓ ✗ ⚠` text glyphs | lucide `Check`, `X`, `AlertTriangle` at `w-3.5 h-3.5` in the status colours |

### 4.7 Histogram (Chart.js, ResultsPane.tsx:1115-1195)

| Option | Current | Proposed |
|---|---|---|
| bar `backgroundColor` | `rgba(99,102,241,.6)` (muddy indigo) | `#6ea8ff` dark / `#1f5fd1` light, solid |
| bar `borderColor` / width | `rgba(99,102,241,1)` / 1 | none / 0 |
| `borderRadius` | 4 | `{ topLeft: 3, topRight: 3 }` |
| `maxBarThickness` | unset (bars are 350px wide for 2 states) | `56`, `categoryPercentage .7` |
| grid | `rgba(255,255,255,.1)` on both axes | y only: `#23272e` dark / `#e7eaef` light; x `display:false` |
| ticks | `rgba(255,255,255,.8)`, x `monospace` | `#8a92a1` dark / `#646b7a` light, family `var(--font-jetbrains-mono)`, size 11 |
| tooltip | Chart.js default (black, sans) | `backgroundColor #1b1e24`, `borderColor #2a2f38`, `borderWidth 1`, `padding 8`, mono body |
| zero-count states | shown as empty slots | keep, but label the y axis "Counts (1024 shots)" so the scale is clear |
| animation | default 1000ms | `{ duration: 250, easing: 'easeOutQuart' }`; `false` under reduced motion |

### 4.8 Stats tab (ResultsPane.tsx:1447-1537)

| Line | Element | Current | Proposed |
|---|---|---|---|
| :1447-1495 | 3 hero cards | green/blue/purple gradient fills, `text-2xl font-bold text-{color}-400` | one neutral row: `bg-editor-panelLowest border border-editor-border rounded-lg p-3`, label `text-[11px] text-[var(--qc-fg-subtle)]`, value `font-mono text-lg tabular-nums text-[var(--qc-fg)]`; only the status dot is coloured |
| :188-191 | Fidelity | falls back to `100.0` | "—" when not provided (B6) |
| :1507-1537 | performance tiles | four colours (cyan, emerald, amber, rose) | same neutral style as above; no per-tile colour |

### 4.9 Toasts

| File:line | Current | Proposed |
|---|---|---|
| app/layout.tsx:159 | react-hot-toast, bg `#252526`, border `#3e3e42`, top-right | **Done in this branch:** `var(--qc-surface-2)`, `1px solid var(--qc-line)`, radius 8, 13px, theme-aware (position unchanged: top-right) |
| XPToast.tsx:61, :101 | infinite `animate-pulse` overlays | removed (done) |
| XPToast.tsx:64, :67, :74 | infinite `animate-bounce` | removed (done) |
| XPToast.tsx:81 | "Level Up! 🎉" | "Level up" (done) |
| AchievementToast.tsx:108, :125 | infinite pulse glow and `shimmer 2.5s infinite` | removed (done); entry is a 220ms ease-out slide and fade |
| AchievementToast.tsx entry | `cubic-bezier(.34,1.56,.64,1)` overshoot, 0.5s | `cubic-bezier(.2,.8,.2,1)` at 220ms (done) |

### 4.10 Modals

| File:line | Current | Proposed |
|---|---|---|
| MenuBar :402/:407/:503/:601, ExplorerView :837/:1049 | `quantum-glass-dark` (blur 20px, `rgba(15,15,35,.6)`, navy-tinted) on `bg-black/50` | panel `bg-editor-panelHigh border border-editor-border rounded-xl shadow-[0_16px_48px_rgba(0,0,0,.45)]`; backdrop `bg-black/55`, no blur; entry `opacity 0→1, scale .98→1, 180ms ease-out` |
| ShareModal.tsx:258 | `backdrop-blur-md` | remove the blur |
| ShareModal.tsx:263 | `animate-in fade-in zoom-in-95` (plugin not installed, so a no-op) | use the `qc-pop-in` keyframe from globals.css (added in this branch) |
| ShareModal.tsx:265-266 | `blur-3xl` decorative orbs | delete |
| EditProfileModal.tsx:142 | `animate-modal-in` (undefined keyframe) | `qc-pop-in` (done in this branch) |

### 4.11 Light theme (app/globals.css)

These rules are global `!important` overrides that the IDE depends on. Fix them by moving the IDE to tokens, then delete the overrides:

| Line | Rule | Problem | Proposed |
|---|---|---|---|
| :513 | `.light .text-white → #1e293b` | turns white text on coloured fills dark (2D/3D toggle, red badge, avatar initials) | migrate IDE text to `text-[var(--qc-fg)]`, then delete |
| :522 | `.light .text-gray-400 → #94a3b8` | 2.6:1 on white | `#646b7a` |
| :526 vs :856 | `.light .text-gray-300` declared twice (`#cbd5e1`, then `#475569`) | confusing | keep a single `#4b5262` |
| :793, :801 | `text-green-400 → #16a34a`, `text-yellow-400 → #ca8a04` | 3.3:1 and 2.9:1 | `#15803d` (5.0:1), `#a16207` (4.9:1) |
| :822 | `.light .min-h-screen → gradient` | repaints any full-height element | delete (no marketing page uses it any more) |
| :827 | `.light .sticky → blur(8px)` | blur on every sticky element | delete |
| :636, :640 | `.light .bg-black`, `.bg-opacity-50` | breaks the mobile overlay in app/app/page.tsx:464 | delete; use `bg-black/40` |
| :543, :547 | `.light .border-t`, `.border-b` | recolours every border | delete once `editor.border` is a CSS var |
| many IDE files | `text-black dark:text-gray-400` | pure black in light mode, heavier than surrounding text | `text-[var(--qc-fg-muted)]` |

### 4.12 Mobile and narrow layouts

- **700px:** the user chip is clipped at the right edge (`live-app-narrow.png`). Hide the username and level text below `lg` and keep the avatar.
- **390px:** the menu bar overflows (B: "Help" is clipped), the results tabs scroll off-screen without an affordance, and Monaco word-wraps code mid-call (`cirq.H\n(q0)`). Use the overflow menu (4.1). Make the results tabs `overflow-x-auto` with a right fade mask. Set Monaco `wordWrap: 'off'` on mobile and accept horizontal scroll, or show a "best on a laptop" banner below 640px.
- **Assistant drawer:** IDELayout.tsx:193 uses `backdrop-blur-2xl` and `shadow-[0_32px_72px…]`. Switch to a solid panel. IDELayout.tsx:204 hardcodes "Model: Claude Opus 4.6"; read it from config.
