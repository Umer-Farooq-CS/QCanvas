# QCanvas production load test

This folder contains a small Locust workload for the deployed QCanvas API. It
repeatedly compiles a two-qubit Qiskit circuit and runs a two-qubit OpenQASM
statevector simulation through the same endpoints used by the application.
Requests use 128 shots and each virtual user waits 5–8 seconds between tasks.

## Safety limits

- The defaults target `https://qcanvas.codes` with only 2 virtual users for 3
  minutes.
- Production runs are blocked unless `LOAD_TEST_ALLOW_PRODUCTION=YES` is set.
- The test enforces a maximum of 5 concurrent users, a spawn rate of 1 user per
  second, and a maximum run time of 5 minutes on the production host.
- The API applies its own rate limits. HTTP 429 responses are counted as
  failures; do not try to evade those limits.
- Run this only with the site owner's approval, during an agreed test window.
  Watch application, hosting, database, and error-rate metrics throughout.
  Stop the test immediately if availability degrades or error rates rise.

This is a low-impact capacity smoke test, not permission to run an unbounded
stress test. Coordinate any test above the built-in caps with the hosting
provider and increase limits only after arranging an isolated staging
environment or an approved production test plan.

## Run from Windows PowerShell

From the repository root, install the isolated test dependency:

```powershell
py -m venv Load-Test\.venv
Load-Test\.venv\Scripts\python.exe -m pip install -r Load-Test\requirements.txt
```

Check that the backend API is reachable before generating traffic:

```powershell
Invoke-WebRequest https://api.qcanvas.codes/api/health/
```

Then start the default test after approval:

```powershell
$env:LOAD_TEST_ALLOW_PRODUCTION = "YES"
Load-Test\.venv\Scripts\locust.exe -f Load-Test\locustfile.py --config Load-Test\locust.conf
```

`locust.conf` provides the bounded defaults. To override them within the
production caps:

```powershell
New-Item -ItemType Directory -Force Load-Test\results | Out-Null
Load-Test\.venv\Scripts\locust.exe -f Load-Test\locustfile.py --config Load-Test\locust.conf --users 4 --spawn-rate 1 --run-time 5m --headless --csv Load-Test\results\workshop
```

The CSV option writes request statistics under `Load-Test\results\`; create
that folder first if using the option. Press `Ctrl+C` to stop early.

## Reading the result

Review the Locust request statistics for both `compile` and `simulate`:

- **Failures:** Investigate non-2xx responses, timeouts, JSON errors, and
  application responses with `success=false`. Rate-limited 429 responses mean
  the workload reached the API's configured limit, not necessarily that the
  server crashed.
- **Latency:** Compare median and 95th/99th percentile response times against
  the workshop's acceptable wait time and your normal baseline.
- **Availability:** Check deployment/provider health, backend logs, and
  database connection/resource metrics before, during, and after the run.

A passing run at these limits is not a guarantee against every workshop
traffic pattern. For a meaningful higher-capacity test, use a staging
deployment with production-equivalent resources and review its scaling and
rate-limit configuration first.
