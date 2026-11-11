# Application Stats Benchmarks

This subfolder measures **generic application-level performance** for QCanvas — the same class of stats you'd measure for any serious web app or code editor (VS Code, CodeSandbox, Jupyter). These are **not** quantum simulation metrics; those live in `../notebooks/`.

> **Why separate?** The Paper 5 benchmarks measure quantum correctness and algorithm equivalence. These notebooks measure QCanvas as a *product*: is the API fast? Does the browser feel snappy? Can it handle load? Does every example actually work?

---

## Directory Layout

```
application_stats/
├── README.md                          ← This file
├── fixtures/
│   └── example_circuits.json          ← 25 built-in example circuits as JSON
├── notebooks/
│   ├── nb01_api_latency.ipynb         ← p50/p95/p99 per endpoint (httpx)
│   ├── nb02_load_test.ipynb           ← RPS, concurrent users, error rate (asyncio)
│   ├── nb03_resource_usage.ipynb      ← CPU, memory, DB query, Redis hit rate (psutil)
│   ├── nb04_conversion_success.ipynb  ← 25 examples batch convert + simulate
│   ├── nb05_web_vitals.ipynb          ← LCP, FCP, TTI, bundle size (Playwright)
│   └── nb06_editor_ux_latency.ipynb   ← Monaco/compile/result-pane timing (Playwright)
├── scripts/
│   ├── api_timing.py                  ← Timed httpx helpers (used by nb01, nb02)
│   ├── locust_scenarios.py            ← Locust user class definitions (used by nb02)
│   ├── resource_monitor.py            ← psutil CPU/memory sampler (used by nb03)
│   ├── batch_converter.py             ← Batch pipeline runner (used by nb04)
│   └── playwright_helpers.py          ← Browser timing + Lighthouse helpers (nb05, nb06)
└── results/
    ├── api/                           ← latency.csv, cold_warm.csv
    ├── load/                          ← rps.csv, error_rate.csv
    ├── resources/                     ← cpu_mem.csv, db_query.csv
    ├── success_rate/                  ← conversion_report.csv, simulation_report.csv
    └── frontend/                      ← vitals.csv, editor_timing.csv
```

---

## Stats Measured

### Category 1 — API Performance
| Metric | Endpoint(s) | Output |
|--------|-------------|--------|
| p50 / p95 / p99 latency | converter, simulator, hybrid, projects, auth | `results/api/latency.csv` |
| Cold vs. Warm response time | converter, simulator | `results/api/cold_warm.csv` |
| Throughput (RPS) | converter | `results/load/rps.csv` |
| Error rate under load | all endpoints | `results/load/error_rate.csv` |
| Latency vs. concurrency curve | converter | `results/load/concurrency_curve.csv` |

### Category 2 — Frontend / Web Vitals (Playwright)
| Metric | Page | Output |
|--------|------|--------|
| LCP, FCP, TTI | Landing, IDE, Login | `results/frontend/vitals.csv` |
| Total Blocking Time (TBT) | IDE | `results/frontend/vitals.csv` |
| Cumulative Layout Shift (CLS) | All pages | `results/frontend/vitals.csv` |
| JS bundle size | Build output | `results/frontend/bundle_sizes.csv` |

### Category 3 — Editor / IDE UX (Playwright)
| Metric | Interface | Output |
|--------|-----------|--------|
| Code→compile turnaround | IDE editor | `results/frontend/editor_timing.csv` |
| Monaco keystroke latency | Monaco editor | `results/frontend/editor_timing.csv` |
| Result pane render time | Results panel | `results/frontend/editor_timing.csv` |

### Category 4 — Server Resource Utilization
| Metric | Operation | Output |
|--------|-----------|--------|
| Peak CPU % during conversion | All 3 frameworks | `results/resources/cpu_mem.csv` |
| Peak RAM during simulation | statevector / density | `results/resources/cpu_mem.csv` |
| Redis cache hit rate | Repeated simulations | `results/resources/cache_stats.csv` |

### Category 5 — Reliability / Correctness
| Metric | Dataset | Output |
|--------|---------|--------|
| Conversion success rate | 25 built-in examples | `results/success_rate/conversion_report.csv` |
| Simulation success rate | Converted QASM files | `results/success_rate/simulation_report.csv` |
| End-to-end pipeline pass rate | Full Cirq/Qiskit/PennyLane chains | `results/success_rate/e2e_report.csv` |

---

## Execution Order

Run notebooks in numbered order. Notebooks 1–4 require only the **backend** to be running. Notebooks 5–6 additionally require the **frontend** to be running and Playwright installed.

| # | Notebook | Requires | Key Output |
|---|----------|---------|-----------|
| 1 | `nb01_api_latency` | backend @ :8000 | latency percentile plots |
| 2 | `nb02_load_test` | backend @ :8000 | RPS + concurrency curve |
| 3 | `nb03_resource_usage` | backend @ :8000 | CPU/RAM per operation |
| 4 | `nb04_conversion_success` | backend @ :8000 | pass/fail table for all examples |
| 5 | `nb05_web_vitals` | backend + frontend @ :3000 + playwright | Lighthouse score card |
| 6 | `nb06_editor_ux_latency` | backend + frontend @ :3000 + playwright | editor timing plots |

---

## Prerequisites

```bash
# Backend Python env (already set up if you can run the backend)
pip install httpx psutil pandas matplotlib seaborn scipy tqdm

# For load testing (nb02) — optional but recommended
pip install locust

# For browser notebooks (nb05, nb06)
pip install playwright
playwright install chromium
```

### Start Services
```bash
# Terminal 1 — Backend
cd backend
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Terminal 2 — Frontend (only needed for nb05, nb06)
cd frontend
npm run dev
```

---

## Results Interpretation

- **API latency p95 < 2s** → meets `techContext.md` target
- **Conversion success rate = 100%** → all 25 examples are regression-safe
- **Lighthouse Performance > 75** → acceptable for a complex IDE app
- **Editor turnaround < 3s** → "feels instant" for typical circuits
- **CPU peak < 80% per request** → backend can handle concurrent users
