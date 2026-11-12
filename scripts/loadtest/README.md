# Load tests

Simulates workshop attendees against a running backend.

| File | What it does |
|---|---|
| `locustfile.py` | One user = one attendee: creates a guest, loads the tree, then loops (5-20 s think time) over save file, convert, run (`execute-qsim`, qiskit, 1024 shots), with some `parse` and hybrid runs. Logs out on stop, which deletes the guest. 429/503/5xx/timeouts get their own stats rows. |
| `sim_capacity.py` | Maximum `execute-qsim` throughput: N guests run back to back. |
| `sample_stats.sh`, `proc_sampler.py` | Container and per-process CPU/memory sampling during a run. |

```bash
# 200 attendees, ~4 min ramp, 8 min run
locust -f scripts/loadtest/locustfile.py --host http://127.0.0.1:8000 \
  --headless -u 200 -r 0.8 -t 8m --csv scripts/loadtest/results_X
python scripts/loadtest/sim_capacity.py http://127.0.0.1:8000 60 40
```

Rate-limit counters live in Redis and persist between runs; clear them before
repeating a run (`redis-cli --scan --pattern 'LIMITS:*' | xargs redis-cli del`).

## Results (local Docker, 12 CPUs, 2026-11-12)

| Setup | 200 attendees | Run (`execute-qsim`) |
|---|---|---|
| `uvicorn --reload` (docker-compose default, 1 process) | Collapsed at ~100-150 users: DB pool exhaustion, 23-46% of requests failed | - |
| `start.py`, 4 workers | 4,776 requests, **0 errors** | p50 7.2 s, p95 46 s (simulator saturated at ~5 runs/s) |
| `start.py`, 4 workers, after the Aer caching fix | - | **26.8 runs/s**, 0 errors (`sim_capacity.py`, 60 users) |

The qiskit backend spent ~92% of each run rebuilding Qiskit Aer's target in
`transpile()` (116 ms per Bell circuit vs ~7 ms for cirq/pennylane). Caching
the simulator and pass manager per thread brought it to 6.9 ms.

For a live session use the production server, e.g.
`docker compose -f docker-compose.yml -f docker-compose.workshop.yml up -d postgres redis backend`.
