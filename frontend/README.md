# QCanvas frontend

Next.js 14 (App Router, TypeScript, Tailwind) app for QCanvas: the IDE at `/app`, plus the landing,
docs, examples, auth and profile pages.

```bash
npm install
npm run dev     # http://localhost:3000 (talks to http://127.0.0.1:8000 on localhost)
npm run lint
npm run build
```

- `app/`: routes. `app/app/page.tsx` is the IDE.
- `components/ide/`: IDE shell (menu bar, activity bar, explorer, tabs).
- `components/EditorPane.tsx`, `components/ResultsPane.tsx`: Monaco editor and results.
- `components/site/`: shared layout for the public pages.
- `lib/`: API client (`api.ts`), auth and session (`authStore.ts`, `session.ts`, `auth.ts`), file store (`store.ts`).

Set `NEXT_PUBLIC_API_BASE` for deployments where the API isn't on localhost.

See the [root README](../README.md) for the full stack, configuration and tests.
License: Open Quantum Workbench Proprietary License (see the repository root `LICENSE`).
