# Workshop Polishing: what changed on this branch

Branch: `workshop-polishing` (38 commits ahead of `main`, 3 of them merge commits)
Prepared for: the QCanvas team (students and supervisors)
Decision needed: whether to make this branch the new `main` before the Qiskit workshop on Friday 2026-11-13 (100 to 200 attendees).

Every claim below comes from a commit message on the branch. Short SHAs are given so each item can be checked with `git show <sha>`.

Overall size of the diff against `main`: 4681 files changed, 17,195 insertions, 25,966 deletions. The file count is large mostly because whole unused directories were deleted (see section 5). Restricted to `frontend/`, `backend/`, `quantum_converters/`, `quantum_simulator/` and `qcanvas/`, it is 170 files, +13,593 / -11,638.

---

## 1. Summary

- **Login bug root cause found and fixed.** Access tokens expired after a hardcoded 30 minutes, but the frontend kept `isAuthenticated=true` in localStorage forever and ignored 401 responses. Returning users looked logged in while every files and projects request failed silently. Sessions now refresh while active, and an expired session redirects to login with an explanation.
- **Private guest workspaces replace the shared demo account.** "Try demo" used to log every visitor into one shared account. On production, strangers' files were in it and anyone could overwrite or delete anyone else's work. Each visitor now gets an isolated, temporary workspace.
- **User code runs in an isolated, killable child process.** Before, a `while True` loop hung the API forever and `import os` exposed `SECRET_KEY`, database and AWS credentials. Now there is a hard wall-clock kill, a stripped environment, resource limits and a blocked-imports sandbox.
- **Converter and simulator correctness.** Cirq, Qiskit and PennyLane converters were producing silently wrong histograms (injected fake gates, dropped operations). All shipped examples now pass on all three backends: 141 of 141 checks, up from 101.
- **Workshop capacity.** Multiple API workers, simulations and conversions off the event loop with bounded queues, Redis-backed rate limits keyed on real client IP or user, batched audit logging, configurable DB pool and simulation caps.
- **Security hardening, including automated-review follow-ups.** Rate-limit bypass closed, guest creation capped, open-redirect holes closed, FastQSim credentials kept away from user code, trusted-proxy handling for client IPs. A FastQSim session token was committed in git history and must be rotated (section 3).
- **UI redesign and IDE polish.** One brand across the site and IDE, a live Bell-state hero run on the homepage, themed editor tabs, working light theme, readable error messages, and the `/app` first-load JavaScript cut from 551 kB to 235 kB (latest production build).
- **Repo cleanup and docs.** Dead files and template leftovers removed, scripts and archives moved, README rewritten, license metadata now proprietary everywhere.

---

## 2. Bugs fixed

### 2.1 Authentication and sessions

| What users saw | Root cause | Fix | Commits |
|---|---|---|---|
| Returning users appeared signed in, but the explorer was empty or broken until they logged out and in again. | Tokens expired after a fixed 30 minutes; the frontend never checked expiry and ignored 401s. | Token lifetime comes from settings. New `POST /api/auth/refresh` for sliding sessions. Frontend checks JWT expiry, clears the session and redirects to `/login?next=...` on any 401, validates and refreshes the session before loading user data, and keeps it alive hourly and on tab focus. Login honours `?next=` and says why the user was signed out. | `27bf2ae` |
| Admin approval links could in principle act as login sessions. | Purpose-specific tokens were accepted as session tokens. | Approval tokens are rejected as login sessions. | `27bf2ae` |
| Logging out did not invalidate the token. | No server-side revocation. | Logout bumps `token_version`, revoking all of that user's tokens. The frontend calls it (keepalive), except on the session-expired path. | `640d1b9` |
| Sessions could be refreshed forever. | No absolute cap. | Access tokens last 24 hours. Tokens carry `auth_time` through refreshes, and refresh is refused after `SESSION_MAX_AGE_DAYS` (30). | `640d1b9` |
| Everyone who clicked "Try demo" shared one account. Files from strangers were visible and editable. "Data will be cleared on logout" was never implemented server-side. | Shared `demo@qcanvas.dev` account. | `POST /api/auth/guest` creates an isolated guest account per visitor (random password never shown, undeliverable `.invalid` email). Guest data is purged on logout and expires after `GUEST_ACCOUNT_TTL_HOURS` (72). Password login to any demo-role account is refused. | `78cfc4f` |
| Auth endpoints could return 429 for a whole venue. | Hardcoded 5 to 20 per minute limits shared by one NAT. | Auth routes use the configurable `RATE_LIMIT_*` settings. | `78cfc4f` |
| Opening `/profile` directly bounced signed-in users to `/login`. | The auth hook decided before the persisted session had hydrated. | `useRequireAuth` waits for hydration before redirecting. | `a77300d` |
| `/profile` still bounced signed-in users to `/app`. | The guard used Zustand's hydration snapshot (no token). | It now decides from the live store and redirects back through `?next=`. | `ac1b41b` |
| Sign-up and login password rules disagreed. | Client-side minimums did not match the backend. | Sign-up minimum matches the backend (8). Login no longer enforces a client-side minimum. | `2588b8c` |
| Admin approval happened on a plain page load. | No confirmation step. | Admin approval requires a click. | `2588b8c` |
| "Try it without an account" looked frozen during the slow first `/app` load. | The button reset its loading state as soon as the API returned. | It shows "Opening the editor..." until navigation completes, and the login and signup pages prefetch `/app`. | `9daff2d` |

### 2.2 Code execution and security of execution

| What users saw | Root cause | Fix | Commits |
|---|---|---|---|
| A `while True` in a hybrid run hung the server for everyone. | User code was exec'd inside the API process; the thread timeout never fired. | Child process (forkserver on Linux, spawn elsewhere) with hard wall-clock kill, allow-listed environment, rlimits, uid drop when root, JSON-only result pipe, bounded concurrency with 503 when busy. Server-side timeout cap. | `a5d3413` |
| `import os` in user code worked and exposed secrets. | No sandbox. | Dangerous imports blocked by default, AST guard against object-walking escapes, read-only module proxies. | `a5d3413` |
| `/api/converter/convert` still ran user code in-process. | The isolation work had not yet covered this route. | `/convert` now runs through the isolated child process. | `2e2dbfb` |
| Every run looked up the SSM online-mode setting. | No caching. | The lookup is cached. | `a5d3413` |
| A broken run showed only "Run failed". A student with a missing parenthesis saw no cause or line. | The error formatter replaced any message over 100 characters, or containing "Error:", with a generic string. | It strips internal wrapper text and keeps the real message, for example `'(' was never closed (line 6)`. Only genuine transport failures (network, timeout, 401, 429, 5xx) map to friendly text; "line 404" no longer reads as "Resource not found". Error entries show the real file name and parsed line number instead of "File: circuit". | `54796e1` |

### 2.3 Compilation and simulation correctness

Commit `7f787ae` addresses silently wrong results across all three frameworks.

| Area | Problem | Fix |
|---|---|---|
| Cirq and PennyLane to QASM | Fake operations (`if/x`, an `ry` loop) were injected into the emitted QASM. | Removed. |
| Cirq | `append()` crash; loop, register and `GridQubit` index bugs. | Fixed. |
| Qiskit | `compose`, `if_test` and multi-register circuits had operations dropped. | Fixed. |
| PennyLane | `Rot`, measure and conditional operations dropped. | Fixed. |
| Unsupported constructs | Wrong QASM was emitted without warning. | A clear error is raised instead (`circuit_validation.py`). Parser `eval()` replaced by `safe_eval.py`. |
| Simulator | Gates and modifiers missing on some backends; no real feed-forward; inconsistent classical-bit order; SWAP removal; PennyLane terminal measurements and reset. | All emitted gates and modifiers implemented on all three backends, real feed-forward (teleportation), consistent bit ordering, PennyLane terminal measurements and reset, Qiskit exact mode, no SWAP removal, standard includes only, unknown backend raises. |
| Result | 101 of 141 example checks passed. | 141 of 141 pass on cirq, qiskit and pennylane. |

Related fixes:

- `qcanvas.compile(QuantumCircuit)` failed with "expected string", which was the documented hybrid pattern. Circuit objects now use the converter's object path. (`028fc72`)
- The Variational (PennyLane) template failed with "Input parameter 'theta' has no value". It now reads module-level params and simulates, with the same distribution on all three backends. (`a77300d`)
- The QNN (PennyLane) example used unseeded parameters and silently produced zeros. It now uses fixed deterministic parameters and fails with a clear error instead (see section 8). (`a77300d`)
- The QRNG (Qiskit) example imported `execute, Aer`, which were removed in Qiskit 1.0. Fixed. (`ac1b41b`)
- A Qiskit test fixture called `qc.global_phase(...)`, which is a property in Qiskit; fixed. PennyLane `MultiRZ`, `adjoint` and `ctrl` now raise instead of being dropped, and the PennyLane demo is marked as a known gap. (`2e2dbfb`)

### 2.4 Backend capacity and reliability

Commit `8213465` unless noted.

| Problem | Fix |
|---|---|
| FastQSim online results were discarded. | Fixed. |
| Clients could set their own XP. | Fixed (server decides). |
| First-simulation bonus used the wrong key and never applied. | Fixed. |
| Ownerless files could be deleted. | Fixed. |
| Cirq proxy forwarded the user's Authorization and Cookie headers upstream. | No longer forwarded. |
| 500 responses leaked internal messages. | Generic message unless `DEBUG`. |
| Hybrid runs sent the server's FastQSim credentials to user code. | Hybrid always simulates locally in the child process (`2e2dbfb`). |
| Qubit limit could be bypassed. | See section 3. |
| A fresh deploy crashed on startup. | SQLAlchemy 2.1 defaults `postgresql://` to psycopg 3, which is not installed. The URL is now pinned to psycopg2. (`028fc72`) |
| `docker compose up` failed without AWS keys. | The Cirq AI service is opt-in (`--profile ai`) with an optional `.env`. (`028fc72`) |
| Event-loop isolation test assumed slow process start. | Test no longer assumes it. (`028fc72`) |

### 2.5 Frontend and IDE

| What users saw | Root cause and fix | Commits |
|---|---|---|
| Explorer sidebar disappeared on narrow windows and never returned. | It auto-collapsed below 768px and never restored. Now restores automatically; activity bar icons toggle it (VS Code style); explicit show/hide button. | `27bf2ae` |
| Ctrl+S downloaded an SVG every time. | Forced download removed (also no longer clobbers text typed mid-request or duplicates unsaved files). | `27bf2ae`, `2588b8c` |
| Advertised shortcuts did nothing. | Ctrl+B, Ctrl+J, Ctrl+Shift+K, Ctrl+Shift+R now work; Alt+N for new file (browsers swallow Ctrl+N); Select All works. | `2588b8c` |
| Failed delete, rename or move looked successful. | `apiRequest` never throws, so catch blocks never ran. Store now checks `res.success`, reverts optimistic updates and shows a toast. | `2588b8c` |
| File id confusion between local and server files. | Local files get `local-*` ids; server ids detected by `isServerFileId`; project ids normalised to strings. | `2588b8c` |
| Hybrid API calls were unauthenticated; the circuit parser always used a regex fallback. | Hybrid calls send the token. The parser calls the real `/api/converter/parse` (it was 404ing on Next.js). | `2588b8c` |
| Misleading error text, algorithm hints matching substrings. | Accurate messages; whole-word hint detection. Stale closure in the Cirq assistant fixed. Dynamic Tailwind classes on `/profile` that were purged in production fixed. | `2588b8c` |
| Monaco threw on every QASM view and highlighting died. | The OpenQASM header tokenizer regex had a nested capture group. Fixed. | `a77300d` |
| Opening an example from the homepage sometimes showed no file, or two highlighted rows. | Race with the initial explorer load. The editor now loads the explorer first, then creates the pending example; `createFile` replaces instead of appending; the explorer dedupes by id. | `9daff2d` |
| React hydration warning in the templates picker and in editor tabs. | Nested `<button>` elements (invalid HTML). Removed in both. | `7d5f46a`, `95f9791` |
| Light theme looked broken: near-black rows with grey text in the project picker, menus, tabs, templates, profile menu. | Dark-only classes. Missing light overrides added; `text-gray-300` no longer near-invisible. | `95f9791` |
| Editor accent colour ignored the theme. | Tailwind's `editor.accent` was a hardcoded `#3291ff` and the CSS variable was never read. Retinted to brand indigo, as were hardcoded light-theme blues. | `95f9791` |
| File > New File opened the browser's native `prompt()`. | Now opens the explorer's inline name field (also Alt+N). | `95f9791` |
| Histogram axis cut off; Stats card showed an invented "Fidelity 100.0%". | Histogram fills the pane. Stats shows shots unless a real fidelity is reported. | `95f9791` |
| Toasts covered the account menu. | Moved to top-center. | `95f9791` |
| Red errors in VS Code's TypeScript 6. | Dropped deprecated `downlevelIteration` and `baseUrl` from `tsconfig`. | `55dd47e` |

### 2.5a Local development

| What users saw | Root cause | Fix | Commit |
|---|---|---|---|
| "Failed to fetch" when signing in from a dev server on any port other than 3000 (e.g. `next dev -p 3001`). | CORS allowed only `http://localhost:3000`. | With `ENVIRONMENT=development` (opt-in, local `.env` only) the API accepts any `localhost` / `127.0.0.1` port. The default is `production`, which keeps the strict allow-list, so a deploy that forgets the setting stays safe (follow-up from the automated security review). | `b922cb5`, see section 9.2 |

### 2.6 Site pages

| What users saw | Fix | Commits |
|---|---|---|
| Fabricated content: testimonial, `aggregateRating` in JSON-LD, "thousands of researchers", links to non-existent Discord/Twitter/LinkedIn, "open-source" wording. | Removed. | `26bbb1a`, `5aed213`, `2909b2e` |
| A supervisor entry carried a student's email (and another supervisor email belonging to someone else was exposed). | Blanked with a TODO in `lib/config`; hidden on About. | `5aed213`, `a77300d` |
| 6 MB generated OG image (2816x1536, with an image-generator watermark). | Replaced by a 1200x630, 71 KB card showing the Bell-state OpenQASM and counts. | `12618f3` |
| Docs documented a WebSocket API that does not exist; shot limit wrong. | WebSocket section removed; shot limit corrected to 100,000. | `ac1b41b` |
| Invented "Quantum Realm" location on profile. | Removed. | `ac1b41b` |
| About photos ballooned on wide screens; homepage padding too loose. | Fixed height cap; section padding tightened. | `ac1b41b` |
| No custom 404. | Plain, titled 404 page in the site style. | `f5fde3a`, `b604fa3` |
| Scroll listeners and sticky positioning did not work reliably. | Window is the scroll container again (`body overflow-x: clip`); no global section transition. | `26bbb1a` |
| Docs code blocks widened the page at 390px. | Fixed. | `536799c` |

---

## 3. Security fixes

### 3.1 Action required: rotate the FastQSim token

A FastQSim session token cache file was committed to the repository. Commit `028fc72` removed it and added it to `.gitignore`, **but the token is still present in git history**. It must be revoked and rotated with FastQSim. Deleting the file does not make it safe. If the repository is, or has been, shared outside the team, treat the token as exposed.

### 3.2 Fixes

| Issue | Fix | Commits |
|---|---|---|
| User code could hang the API or read secrets (`os`, env vars, DB and AWS credentials). | Isolated child process, stripped env, blocked imports, AST guard, rlimits, uid drop. | `a5d3413` |
| `/convert` ran user code in-process. | Routed through the isolated child. | `2e2dbfb` |
| Any user could print the server's FastQSim credentials from hybrid code. | Hybrid runs never receive them; hybrid always simulates locally, regardless of whether user code mentions "fastqsim". | `2e2dbfb` |
| Qubit cap bypass: the route's regex pre-check could be defeated with expression-sized registers. | Cap enforced in `qsim.run_qasm` on the built circuit (`RunArgs.max_qubits` / `QSIM_MAX_QUBITS`, default 24). | `2e2dbfb` |
| Rate-limit identity spoofing via `X-Forwarded-For`. | Forwarded headers and `CLIENT_IP_HEADER` are honoured only when the TCP peer is in `TRUSTED_PROXY_CIDRS` (private ranges by default, i.e. the ALB). | `2e2dbfb` |
| Parser used `eval()`. | Replaced by `safe_eval.py`. | `7f787ae` |
| Sandbox could run user code as the API's own uid, letting it read the API's memory or `/proc/<pid>/environ`. | Refused on POSIX unless `USER_CODE_ALLOW_SAME_UID=true` or `ENVIRONMENT=development`. API process marked non-dumpable. The Docker image runs as root and drops children to `nobody`, so production is unaffected. | `dbb7842` |
| A configured `USER_CODE_RUN_AS_UID` could silently fail to switch accounts. | It only counts as isolation when the API is root and the target is not root; otherwise the same-uid refusal applies. The child raises instead of silently running as the API's uid. | `83789ed` |
| A `.env` could be baked into the Docker image and read by user code. | `.dockerignore` added (it was previously gitignored, so it could never be committed). | `dbb7842` |
| Open redirect through login `?next=` ("/\host"). | `?next=` is resolved against the current origin; backslashes and control characters rejected. | `640d1b9` |
| Open redirect through dot-segments ("/.//evil.com" normalises to "//evil.com"). | Final normalised path is validated. | `dbb7842` |
| Tokens could be refreshed forever; logout did not revoke. | 24 h tokens, 30-day absolute cap, revocation on logout. | `640d1b9` |
| Cirq proxy forwarded user Authorization and Cookie headers. | Stopped. | `8213465` |
| Clients could award themselves XP. | Server-side. | `8213465` |
| Verbose 500 messages. | Generic unless `DEBUG`. | `8213465` |

### 3.3 Follow-ups from the automated security review

These came from review findings on the guest-workspace work and are separate commits:

1. **Guest token farming (`83cb6aa`).** The default limiter key preferred the user id from any valid bearer token. Because `/api/auth/guest` hands out valid tokens, an attacker could mint a new guest token per attempt and get a fresh login, OTP or reset bucket each time. All unauthenticated auth endpoints (login, register, OTP, password reset, guest) now always key on the real client IP.
2. **Guest creation cap (`83cb6aa`).** Per-IP limit of 60 per minute, 400 per hour, 1500 per day (still enough for about 200 attendees behind one NAT), plus a global cap `GUEST_MAX_ACTIVE` beyond which `/guest` returns 503.
3. **Cap lockout (`02be6ab`).** Two sources could fill the cap and lock everyone out of "Try demo". Abandoned guests (idle for `GUEST_IDLE_TTL_HOURS`, 3 h, with no saved files) are now evicted oldest first, a few on every guest creation and up to 200 when the cap is reached, before any 503. The global cap was raised to 5000.
4. **Eviction safety (`017f70b`).** A guest counts as abandoned only if it owns no files, folders, projects, simulations or conversions, so eviction cannot destroy workspace data. Activity is recorded on every authenticated request (throttled to one write per 15 minutes) and on refresh, so an active guest is never mistaken for an abandoned one.
5. **Sandbox host hardening (`dbb7842`, `83789ed`)** and the `?next=` dot-segment fix, listed above.

Residuals stated in the commits: the guest-cap count-then-create is not atomic (the cap is approximate), and the client IP depends on `FORWARDED_TRUSTED_HOPS` matching the real proxy chain.

---

## 4. Improvements

### 4.1 UI and UX

- **Shared design tokens (`26bbb1a`).** Theme-aware `--qc-*` palette (WCAG AA in both themes) exposed as Tailwind `qc-*` colours, a display type scale and the Instrument Sans display face. Pre-paint theme script, `prefers-reduced-motion` support, per-route titles and canonical URLs.
- **Landing page (`26bbb1a`).** Now a Server Component with small client islands and concrete product copy (code to OpenQASM to counts). Orbs, floating icons, gradient text and the duplicate feature grid removed.
- **Navbar (`26bbb1a`, `a5eb196`).** Solid surface, active state, accessible mobile menu, no scroll listener. Signed-in account menu with open editor, profile, achievements, log out and a guest warning.
- **Restyled pages.** Sign-in, sign-up and account recovery (`76db468`, shared `AuthShell`, labelled inputs with autocomplete attributes); docs with sticky table of contents (`536799c`); examples with source tabs, search and filters, visible without JS (`ad56353`); About as a static page (`5aed213`); profile, achievements and XP/achievement toasts (`c89e852`: solid surfaces, 200 ms ease-out, no infinite pulse or bounce, no emoji); 404 (`f5fde3a`).
- **One brand across site and IDE (`a5eb196`).** `BrandLogo` (gradient mark and wordmark) in the navbar, auth pages, footer and IDE menu bar. Accent moved from generic blue to brand indigo in both the site (`--qc-accent*`) and the IDE (`--editor-accent`), WCAG AA in light and dark.
- **Live hero run (`a5eb196`).** The homepage hero runs a real Bell-state example (Qiskit, Cirq and PennyLane tabs): it reveals the source, compiles to OpenQASM line by line, then fills the histogram with real counts. "Run again" replays; reduced motion shows the final state. Starters are the workshop's Qiskit templates.
- **IDE (`a5eb196`, `95f9791`).** New Templates picker (framework chips defaulting to Qiskit, Esc, focus handling, press feedback, creating state); animated menus without the hover border jump; polished profile menu; actionable empty editor (Qiskit Bell state, Browse templates); rebuilt editor tabs (active tab merges into the editor with an indigo top line, framework dot, close button on hover or active, middle-click to close); run options panel animates like other menus.
- **Circuit diagram rewrite (`26bfd4b`).** The 2D diagram was imperative d3 that tore down and redrew the whole SVG on every hover, drew the CNOT target as a ⊗, and drew every gate other than cx, cz and swap as a box on one qubit (crx, cp, ccx and mcx were wrong). It is now declarative SVG built from a shared layout (`lib/circuitLayout.ts`):
  - correct ⊕ targets, control dots, CZ dots, swap crosses, Toffoli and multi-controlled X, measure meter, `|0⟩` reset, dashed barrier;
  - angles as π fractions;
  - columns that never overlap a control line;
  - auto-fit to the panel, zoom and fit controls, hover tooltip, click for details, SVG export.

  The 3D view uses the same layout, renders on demand (no GPU work while idle), frames the camera to the circuit, and draws proper CNOT rings, control spheres and swap crosses. OpenQASM files now draw too (they showed nothing before).
- **Navbar logo (`1aa8977`).** Larger and vertically centred with the nav links.
- **Copy (`a5eb196`, `78cfc4f`).** No "demo account" wording, no version footer, no shared credentials shown, plain copy instead of exclamation-mark prompts.

### 4.2 Performance

| Change | Result | Commit |
|---|---|---|
| Narrow store selectors and `memo` across the IDE | Typing no longer re-renders the whole IDE | `2588b8c` |
| Memoised d3 diagram colours | The diagram no longer redraws per keystroke | `2588b8c` |
| Circuit diagram: memoised SVG glyphs, cached parses (32 entries), stale requests aborted, 350 ms debounce, 3D `frameloop="demand"` with capped DPR | Hover re-renders one gate; tab switches and undo show the diagram instantly; an idle 3D view costs nothing | `26bfd4b` |
| Lazy-loaded chart.js, d3 diagram, markdown/KaTeX and the Cirq assistant | `/app` first-load JS 551 kB to 245 kB (`2588b8c`). The CHANGELOG records 238 kB; the team's current measurement is about 235 kB. All figures are in the same range. | `2588b8c` |
| Landing page as Server Component | `/` first-load JS 197 kB to 118 kB | `2909b2e` |
| OG image 6.15 MB to 71 KB | Faster link previews | `12618f3` |
| Audit log is pure ASGI and batch-written by a background thread | Logging off the request path | `8213465` |
| SSM lookup cached | One lookup instead of one per run | `a5d3413` |
| Login and signup pages prefetch `/app` | Faster first editor load | `9daff2d` |

### 4.3 Desktop and resolution scaling

- Desktop-first container of 96rem so pages use the screen width (`a5eb196`).
- Site pages scale with screen resolution through rem scaling at 1800, 2300 and 3200 px, scoped to site pages. The IDE is unchanged. Pixel-sized hero and logo text converted to rem so it scales too. (`95f9791`)
- Profile and achievements use the full desktop width (`ac1b41b`).

### 4.4 Light and dark theme coverage

- Site palette meets WCAG AA in both themes (`26bbb1a`, `a5eb196`).
- IDE light theme: project picker, menus, tabs, templates and profile menu had dark-only classes; light overrides added (`95f9791`). Profile and achievement surfaces mapped onto `qc-*` tokens so they read in both themes (`c89e852`).

### 4.5 Docs

- Root README rewritten for the actual stack, with a verified local Docker quick start, configuration table, test commands, production notes and repo layout (`5a06f14`).
- `qcanvas/README.md` is now the PyPI page for `qcanvas-sdk` (pyproject points to it), with corrected extras names and an object/source support table. `frontend/` and `backend/` READMEs replaced with short, accurate guides (`5a06f14`).
- CHANGELOG updated (`5a06f14`). Live-site design audit with an IDE visual issue list added in `design-audit/` (`5dfcf16`, `b604fa3`).
- Docs page corrected: WebSocket section removed, shot limit fixed (`ac1b41b`).

---

## 5. Repository cleanup and restructure

All removals are recoverable from git history (`028fc72`).

**Removed**

- One-off and dead files: `append_new.py`, `verify_*.py`, `environment.env` (a personal PYTHONPATH), a TODO-only root `Dockerfile`, `tools.txt`, a conflicting `setup.cfg`, a duplicate root `alembic.ini`, backend debug scripts.
- The committed FastQSim session token cache (now gitignored; see section 3.1).
- Unused Vite, Express and Netlify template leftovers in `frontend/` (`server/`, `shared/`, `netlify/`, vite configs, `index.html`, `AGENTS.md`) and the vite and express dependencies.
- `Test-Pypi-Imports/` and `qsim-test/` demos.
- Dead `TopBar.tsx`, `Sidebar.tsx`, mock `app/api/files` routes and stale txt files (`2588b8c`).

**Moved**

| From | To |
|---|---|
| Backend admin scripts | `backend/scripts/` |
| Legacy loose tests | `backend/tests/legacy/` (CI paths updated) |
| Shell scripts | `scripts/` |
| Stale notes and `memory-bank/` | `docs/archive/` |
| `benchmarks/` | `docs/archive/benchmarks/` |
| `icons/` | `docs/assets/icons/` |

**Config and license**

- `.dockerignore` committed (it had been gitignored, so it could not exist) (`dbb7842`).
- `docker-compose.yml`: Cirq AI service opt-in via `--profile ai`, `qcanvas/` and `config/` bind-mounted for dev, obsolete `version` key removed (`028fc72`).
- **License:** the packages declared MIT while the repository `LICENSE` is the Open Quantum Workbench Proprietary License. Package metadata now declares the proprietary license everywhere (`028fc72`, `5a06f14`), and "open-source" wording was removed from the site (`2909b2e`).

---

## 6. How it was tested

Stated as the commit messages report it. Nothing here was re-run to write this document.

| Area | What was run | Commit |
|---|---|---|
| Sessions | New `backend/tests/test_auth_session.py`: lifetime, refresh, absolute cap, approval-token rejection, logout revocation, demo exemption. | `640d1b9` |
| Guest and rate limits | Tests for IP-keyed auth limits and the guest cap. Eviction rules covered in follow-ups. | `83cb6aa`, `02be6ab`, `017f70b` |
| Converters and simulator | `tests/integration/test_workshop_correctness.py`: every shipped example on cirq, qiskit and pennylane, 141 of 141 checks (101 before). Test fixtures corrected (Qiskit `global_phase`, PennyLane known-gap marking). | `7f787ae`, `2e2dbfb` |
| Isolation and sandbox | `tests/test_isolated_exec.py` and `tests/test_sandbox_security.py`. The first commit says Linux-only paths were untested on the development machine and must be run in the Docker image. They were then run on Docker (Linux, Python 3.11): 84 isolation and sandbox tests passed. | `a5d3413`, `028fc72` |
| Qiskit | 301 Qiskit tests passed on Docker (Linux, Python 3.11). | `028fc72` |
| End to end on Docker | Qiskit compile, simulate and hybrid execution verified end to end; fresh-deploy crashes (psycopg driver, compose without AWS keys) found and fixed during this run. | `028fc72` |
| Browser | Commit messages describe browser verification (for example the production findings behind `78cfc4f`, and the 390 px layout fixes in `536799c`) and a live-site design audit (`5dfcf16`). They do not list a formal automated browser test suite. | `78cfc4f`, `536799c`, `5dfcf16` |
| CI | `.github/workflows/ci.yml` runs backend tests and the frontend lint and build (per the README). | `5a06f14` |

Test commands are in the root README under "Testing".

---

## 7. Deployment notes and configuration changes

### 7.1 Deploy backend and frontend together

The new backend refuses password login to any demo-role account, which retires the shared `demo@qcanvas.dev` login. An old frontend still calls that login, so "Try demo" will fail with a new backend. The new frontend calls `POST /api/auth/guest`, which an old backend lacks. Deploy both from this branch at the same time.

### 7.2 New or changed settings

Defaults are those in the README and commit messages. Settings live in `backend/app/config/settings.py` and `.env.example`.

| Variable | Default | Why it matters |
|---|---|---|
| `SECRET_KEY` | dev value | Must be set to a random value in production. Signs JWTs. |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | 1440 (24 h) | Was a hardcoded 30 minutes. Active users refresh automatically. |
| `SESSION_MAX_AGE_DAYS` | 30 | Absolute session cap; refresh refused after this. |
| `GUEST_ACCOUNT_TTL_HOURS` | 72 | Guest workspaces are deleted after this, or on logout. |
| `GUEST_IDLE_TTL_HOURS` | 3 | Empty, inactive guests are evicted after this. |
| `GUEST_MAX_ACTIVE` | 5000 | Global live-guest cap; above it `/guest` returns 503 after eviction. |
| `RATE_LIMIT_*` | sized for a workshop | Per-user or per-IP limits. Guest creation per IP: 300/min, 1000/h, 3000/day (raised from 60/min in `06b6f02`: a workshop room shares one NAT address). |
| `REDIS_URL` / `REDIS_*` | `localhost:6379` | Shared rate-limit counters. Falls back to in-memory if unreachable, which is per worker and weaker. |
| `WEB_CONCURRENCY` | auto | Uvicorn workers; about 300 to 400 MB each. README suggests 4 for about 200 users. |
| `FORWARDED_TRUSTED_HOPS` | 1 | Number of proxies in front of the API (ALB = 1; Cloudflare then ALB = 2). Wrong value gives wrong client IPs. |
| `TRUSTED_PROXY_CIDRS` | private ranges | `X-Forwarded-For` is trusted only from these peers. Make sure the load balancer's addresses are included. |
| `CLIENT_IP_HEADER` | empty (unused) | Optional header carrying the real client IP (e.g. `CF-Connecting-IP`). Honoured only from trusted proxies. |
| `SIM_MAX_QUBITS` / `QSIM_MAX_QUBITS` | 24 | Qubit cap enforced on the built circuit. |
| `SIM_MAX_SHOTS` | 100000 | Shot cap. |
| `HYBRID_MAX_EXECUTION_TIME` | 60 s | Child process is killed after this; also capped server-side. |
| `USER_CODE_MAX_CONCURRENCY` | CPU count | Concurrent sandboxed processes per worker. README suggests 1 to 2 for about 200 users. Excess requests get 503. |
| `USER_CODE_RUN_AS_UID` | `nobody` when root | Privilege drop for user code. Only counts as isolation when the API is root and the target is not root. |
| `USER_CODE_ALLOW_SAME_UID` | false | Escape hatch for non-root deployments. Without it (or `ENVIRONMENT=development`), hybrid execution is refused. |
| `DB_POOL_SIZE` / `DB_MAX_OVERFLOW` | 5 / 5 | Per worker. Postgres needs about `WEB_CONCURRENCY x (DB_POOL_SIZE + DB_MAX_OVERFLOW)` connections plus the audit writer. |
| `DB_POOL_TIMEOUT` / `DB_POOL_RECYCLE` / `DB_POOL_PRE_PING` / `DB_CONNECT_TIMEOUT` | 10 s / 1800 s / true / 10 s | Fail fast when the pool is exhausted, recycle before idle timeouts, detect dead connections. |
| `ENVIRONMENT` | `production` | Fail-closed default. Only a local `.env` should set `development`, which also accepts any `localhost` / `127.0.0.1` port as a CORS origin. Never set `development` on a server. |
| `NEXT_PUBLIC_API_BASE` (frontend) | `https://api.qcanvas.codes` | API URL for non-localhost deployments. |

### 7.3 Operational checklist

- Run the API container as root so user code is dropped to `nobody`. If that is not possible, set `USER_CODE_ALLOW_SAME_UID=true` knowingly.
- Reach Redis from every worker. Without it, rate limits are per process.
- Suggested size for about 200 concurrent users, from the README: 4 vCPU, 8 GB, `WEB_CONCURRENCY=4`, `USER_CODE_MAX_CONCURRENCY=1` to `2`.
- Never bake `.env` into images; `.dockerignore` now excludes it.
- On AWS, block the instance metadata endpoint for the task or scope its IAM role tightly.
- Health checks can use the new cheap `/api/health` (`8213465`).
- Rotate the FastQSim token (section 3.1).
- Everyone behind one venue NAT shares one per-IP allowance. The guest limits were sized for about 200 people behind one NAT (`83cb6aa`).
- Fresh local setup: `docker compose up` now works without AWS keys; add `--profile ai` for the Cirq assistant.

---

## 8. Known limitations and not done

- **PennyLane QNN example: fixed (`8463195`).** Static loops that index module-level arrays are now unrolled (bounded), and the example matches real PennyLane probabilities to within 1e-7 on all three backends. PennyLane `MultiRZ`, `adjoint` and `ctrl` still raise instead of being converted (`a77300d`, `2e2dbfb`).
- **No per-account login lockout.** Auth limits are keyed on client IP, not on the targeted account.
- **Guest cap is approximate.** Count-then-create is not atomic (`02be6ab`).
- **Client IP depends on configuration.** `FORWARDED_TRUSTED_HOPS` and `TRUSTED_PROXY_CIDRS` must match the real proxy chain, or limits will key on the proxy and throttle the whole room (`02be6ab`, `2e2dbfb`).
- **Linux-only sandbox features.** Forkserver start, rlimits, uid drop and non-dumpable marking apply on Linux. On Windows and macOS the child uses spawn and the Linux-only paths are not exercised. Sandbox tests were run inside Docker on Linux, not on the development machine (`a5d3413`, `028fc72`).
- **Sandbox is not a full container boundary.** It blocks dangerous imports and drops privileges, but the README still advises blocking the AWS metadata endpoint and scoping IAM roles.
- **Co-supervisor email is blank.** A TODO in `lib/config` (`a77300d`).
- **FastQSim token is still in git history** (section 3.1).
- **IDE not rescaled.** Resolution scaling applies to site pages only; the IDE is unchanged (`95f9791`).
- **No automated browser test suite is mentioned in the commits.** UI behaviour was verified in the browser and through the design audit.
- **Bundle size figures differ slightly** between the commit (245 kB), the CHANGELOG (238 kB) and the team's latest measurement (about 235 kB). Re-measure with `npm run build` if the exact number matters.

---

## 9. How to revert and how to review

### 9.1 Reverting UI work

Four merge commits group the UI work. Each can be reverted as a unit:

| Merge commit | Scope |
|---|---|
| `2909b2e` | Redesign of non-IDE pages: landing, docs, examples, about, auth, profile and achievements, 404, shared `qc-*` palette. IDE unchanged. |
| `659b433` | UI polish: one brand across site and IDE, live hero run, Templates picker, desktop-width layout. |
| `39f1e34` | Circuit visualization rewrite (2D and 3D), parse caching, navbar logo. |
| `df61e3c` | UI polish round 2: themed tabs, light-theme coverage, inline New File, honest stats, resolution scaling, readable run errors, site audit fixes. |

```bash
git revert -m 1 <merge sha>
```

Revert newest first (`39f1e34`, then `df61e3c`, then `659b433`, then `2909b2e`) to reduce conflicts. Backend, security and correctness fixes are not part of these merges and stay in place. Caution: some later non-merge commits touch files the merges changed, so a revert may need conflict resolution. The merge commit messages for `2909b2e` note that guest "Try demo", `?next` validation, password rules and the click-to-approve admin flow were kept through conflict resolution, so reverting that merge needs a careful look at the auth pages.

### 9.2 Reviewing, in commit order

Oldest first, from `git log --reverse main..workshop-polishing`.

| # | SHA | Title |
|---|---|---|
| 1 | `27bf2ae` | Fix stale-session login bug and add sidebar toggle |
| 2 | `640d1b9` | Harden sessions: absolute cap, revocable logout, safe ?next redirect |
| 3 | `78cfc4f` | Replace shared demo account with private guest workspaces |
| 4 | `83cb6aa` | Key auth rate limits on client IP; cap guest account creation |
| 5 | `5dfcf16` | Add live-site design audit with IDE visual issue list |
| 6 | `02be6ab` | Evict abandoned guests before refusing new ones at capacity |
| 7 | `017f70b` | Tighten idle-guest eviction: no data of any kind, activity on every request |
| 8 | `2588b8c` | Frontend: fix IDE logic bugs, wire up shortcuts, cut /app bundle by more than half |
| 9 | `26bbb1a` | Add site design tokens and rebuild landing page and navbar |
| 10 | `76db468` | Restyle sign-in, sign-up and account recovery pages |
| 11 | `536799c` | Restyle documentation page |
| 12 | `ad56353` | Restyle examples page |
| 13 | `5aed213` | Rebuild About page as a static, factual page |
| 14 | `12618f3` | Replace 6 MB generated OG image with a 71 KB typographic card |
| 15 | `c89e852` | Restyle profile, achievements and gamification toasts |
| 16 | `f5fde3a` | Add a plain 404 page in the site style |
| 17 | `b604fa3` | Title the 404 page; document tokens and bundle sizes in the audit |
| 18 | `7f787ae` | Converters/simulator: fix silently wrong histograms across all backends |
| 19 | `a5d3413` | Run user code in an isolated, killable child process |
| 20 | `8213465` | Backend: workshop capacity, rate limits, and API bug fixes |
| 21 | `2e2dbfb` | Security fixes: isolated /convert, no FastQSim token in user code, real qubit cap, trusted-proxy IPs |
| 22 | `dbb7842` | Harden sandbox host, add .dockerignore, close ?next dot-segment redirect |
| 23 | `2909b2e` | Merge UI redesign (workshop-design) for non-IDE pages |
| 24 | `83789ed` | Sandbox: fail closed when the configured privilege drop is impossible |
| 25 | `a77300d` | Fix Monaco QASM crash, /profile bounce, wrong supervisor email, examples |
| 26 | `028fc72` | Clean up repo structure; fix fresh-deploy crashes found on local Docker |
| 27 | `7d5f46a` | Templates picker: remove nested button (invalid HTML, hydration warning) |
| 28 | `5a06f14` | Docs: rewrite README for the project, separate SDK README, update CHANGELOG |
| 29 | `55dd47e` | tsconfig: drop deprecated downlevelIteration/baseUrl |
| 30 | `a5eb196` | UI polish: one brand across site + IDE, live hero run, desktop-width layout |
| 31 | `659b433` | Merge UI polish (workshop-ui-polish) |
| 32 | `9daff2d` | Fix duplicate/vanishing example files; guest button stays busy until the editor opens |
| 33 | `ac1b41b` | Site audit fixes: account pages, spacing, docs accuracy, QRNG example |
| 34 | `95f9791` | IDE UX pass: themed tabs, light-theme coverage, inline New File, honest stats |
| 35 | `54796e1` | Readable run errors: keep the real cause and line number |
| 36 | `df61e3c` | Merge UI polish round 2 (workshop-ui-polish-2) |
| 37 | `b922cb5` | CORS: accept any localhost port in development ("Failed to fetch" on :3001) |
| 38 | `a41fede` | CORS dev allowance made opt-in (default `production`); About page team photos in portrait frames; this document |
| 39 | `b4aca35` | Cap ranges materialised from user code during static parsing (DoS) |
| 40 | `8463195` | PennyLane: resolve module-level array indexing in static loops (QNN example) |
| 41 | `06b6f02` | Workshop reliability: room-sized guest rate limit, 8 s refresh timeout (no endless "Loading QCanvas...") |
| 42 | `39f1e34` | Merge circuit visualization rewrite (workshop-viz) |

Suggested review order for a short session: `78cfc4f` (guest workspaces), `a5d3413` and `2e2dbfb` (sandbox), `7f787ae` (correctness), `8213465` (capacity), then the config table in section 7.
