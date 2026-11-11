# QCanvas backend

FastAPI service for QCanvas. It handles auth (accounts and private guest sessions), files, folders and
projects, compiling framework code to OpenQASM 3.0, simulation with QSim, sandboxed hybrid execution,
and XP and achievements.

```bash
# from the repo root, with Docker (recommended)
docker compose up -d --build
docker compose exec backend python -m alembic upgrade head

# or locally (needs PostgreSQL; see DATABASE_URL in the root README)
cd backend && python start.py      # http://localhost:8000 (docs at /docs)
```

| Path | Contents |
|------|----------|
| `app/main.py` | App setup: middleware, CORS, routers |
| `app/api/routes/` | `auth`, `files`, `folders`, `projects`, `converter`, `simulator`, `hybrid`, `gamification`, `shared`, `health`, `cirq_agent_proxy` |
| `app/services/` | Conversion, simulation, isolated user-code execution, guest accounts, gamification, email/OTP |
| `app/core/` | Rate limiting, audit log, security headers, concurrency limits |
| `app/config/` | Settings (env vars) and database engine |
| `alembic/` | Migrations (`python -m alembic upgrade head`) |
| `scripts/` | Admin scripts (`create_user.py`, `seed_*.py`, `verify_database.py`, ...) |
| `tests/` | Tests: `pytest --ignore=tests/legacy/test_api.py --ignore=tests/legacy/test_auth.py` |

`start.py` runs uvicorn with `WEB_CONCURRENCY` workers and proxy-header support.

See the [root README](../README.md) for configuration, production notes and the full test suite.
