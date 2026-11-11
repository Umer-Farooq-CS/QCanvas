# QCanvas: Quantum Unified Simulator

QCanvas is a browser-based quantum programming IDE. Write circuits in **Qiskit**, **Cirq** or
**PennyLane**, compile them to **OpenQASM 3.0**, and simulate them with the **QSim** engine. It is built
under *Open Quantum Workbench*, a FAST University initiative.

- **Editor:** Monaco-based IDE with files, folders and projects, templates and an examples gallery.
- **Compile:** framework source code to OpenQASM 3.0 (`quantum_converters`).
- **Simulate:** OpenQASM 3.0 on Cirq, Qiskit (Aer) or PennyLane backends (`quantum_simulator`, the `qsim` package).
- **Hybrid mode:** run Python that calls `compile(...)` and `qsim.run(...)` in a loop, sandboxed on the server.
- **Accounts:** email sign-up, or **Try demo** for a private, temporary guest workspace.
- **Extras:** XP, achievements and a leaderboard, plus an optional Cirq AI assistant (admin only).

---

## Architecture

```
Browser ── Next.js 14 frontend (frontend/)
              │  REST + JWT
              ▼
         FastAPI backend (backend/app)  ── PostgreSQL (users, files, projects, XP)
              │                         └─ Redis (shared rate-limit counters)
              ├─ quantum_converters/   framework source → OpenQASM 3.0
              ├─ quantum_simulator/    `qsim`: OpenQASM 3.0 → cirq / qiskit / pennylane simulation
              └─ qcanvas/              SDK facade + hybrid-mode sandbox
                    user code runs in an isolated child process
                    (killed at the time limit, secrets stripped, dangerous imports blocked)

Optional: Cirq-RAG-Code-Assistant/ (AI assistant via AWS Bedrock, proxied at /api/cirq-agent/*)
```

### Repository layout

| Path | What it is |
|------|------------|
| `frontend/` | Next.js 14 (App Router) app: IDE at `/app`, landing, docs, examples, auth, profile |
| `backend/app/` | FastAPI app: `api/routes`, `services`, `models`, `core` (middleware, rate limits, concurrency) |
| `backend/alembic/` | Database migrations |
| `backend/scripts/` | Admin scripts: create users and admins, seed achievements, inspect or reset the DB |
| `backend/tests/` | Backend tests (`legacy/` holds older ad-hoc tests) |
| `quantum_converters/` | Qiskit / Cirq / PennyLane → OpenQASM 3.0 converters |
| `quantum_simulator/` | QSim simulator package (`qsim`), installed editable |
| `qcanvas/` | Python SDK published as `qcanvas-sdk` (see `qcanvas/README.md`), plus the hybrid sandbox |
| `config/` | Hybrid-execution sandbox settings (`config/config.py`) |
| `tests/` | Converter, simulator, sandbox and end-to-end tests |
| `Cirq-RAG-Code-Assistant/` | Optional AI assistant service |
| `examples/` | Sample circuits per framework |
| `scripts/` | Linux helper scripts (`setup.sh`, `run.sh`, `run_tests.py`) |
| `docs/` | Documentation; `docs/archive/` holds benchmarks, old planning notes and the memory bank |

---

## Quick start (local Docker)

Prerequisites: Docker with Compose v2, Node.js 18 or newer, and Git.

```bash
git clone https://github.com/Umer-Farooq-CS/QCanvas.git
cd QCanvas

# 1. Environment (local only; .env is gitignored). Set a random SECRET_KEY.
cp .env.example .env

# 2. Start PostgreSQL, Redis and the API (first build takes a while)
docker compose up -d --build

# 3. Create the database schema
docker compose exec backend python -m alembic upgrade head

# 4. Frontend
cd frontend
npm install
npm run dev                 # http://localhost:3000
```

- API: <http://localhost:8000>. Docs at `/docs`, health at `/api/health`.
- On `localhost` the frontend automatically talks to `http://127.0.0.1:8000`.
- **Try demo** on the login page creates a private guest workspace, so no email setup is needed.

### Services

| Service | Container | Host port | Notes |
|---------|-----------|-----------|-------|
| PostgreSQL (pgvector) | `qcanvas_postgres` | 5433 | |
| Redis | `qcanvas_redis` | 6379 | rate-limit storage |
| QCanvas API | `qcanvas_backend` | 8000 | hot-reloads `backend/`, `quantum_*`, `qcanvas/`, `config/` |
| Cirq AI (optional) | `qcanvas_cirq_agent` | 8001 | `docker compose --profile ai up -d`; needs `Cirq-RAG-Code-Assistant/.env` with AWS Bedrock keys |
| SonarQube (optional) | `qcanvas_sonarqube` | 9000 | `docker compose --profile metrics up -d` |

### Useful commands

```bash
docker compose logs -f backend                               # follow API logs
docker compose exec backend python scripts/create_user.py    # create a user or admin interactively
docker compose down                                          # stop (keeps data)
docker compose down -v                                       # stop and DELETE database data
```

### Without Docker (backend)

```bash
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt                        # also installs quantum_simulator in editable mode
cd backend && python start.py                          # needs PostgreSQL; see DATABASE_URL below
```

---

## Configuration

Settings come from environment variables or the root `.env` (see `.env.example` and
`backend/app/config/settings.py`). The most important ones:

| Variable | Default | Purpose |
|----------|---------|---------|
| `SECRET_KEY` | dev value | **Must be set in production.** Signs JWTs. |
| `DATABASE_URL` / `POSTGRES_*` | local Postgres | Database connection |
| `REDIS_URL` / `REDIS_*` | `localhost:6379` | Shared rate-limit storage (in-memory fallback) |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `1440` | Session length; active users are refreshed automatically |
| `SESSION_MAX_AGE_DAYS` | `30` | Absolute session cap |
| `GUEST_ACCOUNT_TTL_HOURS` | `72` | Guest workspaces are deleted after this, or on logout |
| `WEB_CONCURRENCY` | auto | Uvicorn worker processes (about 300–400 MB each) |
| `SIM_MAX_QUBITS` / `SIM_MAX_SHOTS` | `24` / `100000` | Simulation limits |
| `HYBRID_MAX_EXECUTION_TIME` | `60` | Seconds before hybrid user code is killed |
| `USER_CODE_MAX_CONCURRENCY` | CPU count | Concurrent sandboxed user-code processes per worker |
| `FORWARDED_TRUSTED_HOPS` / `TRUSTED_PROXY_CIDRS` | `1` / private ranges | Real client IP behind a load balancer |
| `RATE_LIMIT_*` | sized for a workshop | Per-user / per-IP limits |
| `AUTH_EMAIL_OTP_ENABLED`, `RESEND_API_KEY` | off | Email verification codes for sign-up and password reset |
| `CIRQ_AGENT_URL`, `CIRQ_RAG_API_KEY` | | Optional AI assistant proxy |

Frontend: `NEXT_PUBLIC_API_BASE` sets the API URL for non-localhost deployments
(default `https://api.qcanvas.codes`).

---

## Testing

```bash
# Backend API (auth, sessions, guests, rate limits, concurrency)
cd backend && pytest --ignore=tests/legacy/test_api.py --ignore=tests/legacy/test_auth.py

# Converters, simulator, sandbox and end-to-end (from the repo root, with requirements installed)
pytest tests

# Correctness table: every shipped example on all three backends
python tests/integration/test_workshop_correctness.py

# Sandbox isolation on Linux (inside the container)
docker compose exec backend sh -c "cd /app && pip install pytest && python -m pytest tests/test_isolated_exec.py tests/test_sandbox_security.py"

# Frontend
cd frontend && npm run lint && npm run build
```

CI (`.github/workflows/ci.yml`) runs the backend tests and the frontend lint and build on every push and PR.

---

## Production notes

- **Size:** for about 200 concurrent users, use 4 vCPU / 8 GB, `WEB_CONCURRENCY=4`, a reachable Redis, and
  `USER_CODE_MAX_CONCURRENCY=1–2`.
- **Run the API container as root.** User code is then dropped to an unprivileged account (`nobody`).
  On a non-root deployment, hybrid execution is refused unless you explicitly set `USER_CODE_ALLOW_SAME_UID=true`.
- **Behind a load balancer:** keep `FORWARDED_TRUSTED_HOPS` equal to the number of proxies (ALB = 1;
  Cloudflare → ALB = 2) and make sure the balancer's addresses are in `TRUSTED_PROXY_CIDRS`.
- **Secrets:** never bake `.env` into images; `.dockerignore` excludes it.
- **AWS:** block the instance metadata endpoint for the task, or scope its IAM role tightly.

---

## License

Proprietary: **Open Quantum Workbench Proprietary License**. See [LICENSE](LICENSE).

## Team

**QCanvas:** Umer Farooq, Hussan Waseem Syed, Muhammad Irtaza Khan
**QSim:** Aneeq Ahmed Malik, Abeer Noor, Abdullah Mehmood
**Supervisors:** Dr. Imran Ashraf (Supervisor), Dr. Muhammad Nouman Noor (Co-Supervisor)
