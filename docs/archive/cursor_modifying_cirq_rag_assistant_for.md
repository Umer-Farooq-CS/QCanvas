# Modifying cirq rag assistant for AWS
_Exported on 4/17/2026 at 02:19:01 GMT+5 from Cursor (3.1.15)_

---

**User**

I have attached the cirq rag assistant to this project. Now I want to  modify it in such a way that I have no issue with it in deployment of it on AWS. Now I dont think there will be any issue will there be explain to me. Also should I make it so that I create a new table in my db and store the vector store and embeddings on it with the proper encoded and original text so it is better and easier. Give me tips

---

**Cursor**

I've gone through the Cirq RAG assistant end-to-end (`src/server.py`, `src/rag/vector_store.py`, `src/rag/embeddings.py`, `config/config.json`, `Dockerfile`, `docker-compose.yml`, knowledge base, and the integration guide) so I can give you a grounded answer instead of a generic one.

Short answer: **no, it will not "just work" on AWS out of the box** — it'll run, but you'll hit several real deployment problems. Also, **yes — moving the vector store into your Postgres DB (via `pgvector`) is the right call for production.** I'll explain both clearly.

---

## 1. Deployment issues you *will* hit on AWS

### Issue 1 — FAISS index lives on the local filesystem
`config.json` says:

```26:39:Cirq-RAG-Code-Assistant/config/config.json
  "rag": {
    "knowledge_base": {
      "path": "data/knowledge_base",
      "size_target": 2500
    },
    "vector_store": {
      "type": "faiss",
      "index_path": "data/models/vector_index",
      "use_gpu": false
    },
```

And `VectorStore.save/load` writes `faiss.index` + `metadata.pkl` to disk:

```421:433:Cirq-RAG-Code-Assistant/src/rag/vector_store.py
        if self.vector_db_type == "faiss":
            index_file = save_path / "faiss.index"
            faiss.write_index(self.index, str(index_file))
            
            metadata_file = save_path / "metadata.pkl"
            with open(metadata_file, 'wb') as f:
                pickle.dump({
                    "metadata": self.metadata,
                    "id_to_index": self.id_to_index,
                    "index_to_id": self.index_to_id,
                    "next_id": self.next_id,
                }, f)
```

What goes wrong on AWS:
- **ECS Fargate / App Runner** → filesystem is ephemeral. Every cold start re-embeds the KB (and re-embedding via Bedrock Nova is rate-limited — see issue 4).
- **Multiple instances behind an ALB** → each replica has its own copy of the index. Adding a document on one replica is invisible to the others.
- **EC2 single instance** → works, but you've now coupled "my RAG data" to "this one VM". Terminate the VM = lose the index.

Baking the prebuilt index into the Docker image "works" until you want to update it without a full redeploy.

### Issue 2 — Docker image is huge and carries dependencies you don't actually use
Your config has `models.embedding.provider = "aws"` (Nova via Bedrock), but `requirements.txt` + the Dockerfile still pulls in `torch`, `transformers`, `sentence-transformers`, `faiss-cpu`, etc. That's a **~3–5 GB image** for a service that is fundamentally just "FastAPI → boto3 → Bedrock + a small FAISS in-memory index".

On Fargate/App Runner this means:
- Long pull times per task
- Slow cold starts
- Bigger ECR storage bill

### Issue 3 — No CORS middleware
`src/server.py` has no `CORSMiddleware`. In dev you're proxying through Vite (`/cirq-api`), so you don't see it. In production, if QCanvas frontend talks to the Cirq API on a different origin (e.g. `api-cirq.yourdomain.com`), the browser blocks it.

### Issue 4 — Bedrock throttling + synchronous 15–60s requests
Two things compound here:

1. Your embedding code explicitly sleeps between Bedrock calls:
   ```231:238:Cirq-RAG-Code-Assistant/src/rag/embeddings.py
               delay_seconds = get_config().get("aws", {}).get("embeddings", {}).get("request_delay_seconds", 5.0)
               embeddings_list = []
               for i, t in enumerate(texts):
                   if i > 0:
                       time.sleep(delay_seconds)
                   embeddings_list.append(self._encode_single_aws(t))
   ```
2. A single `/api/v1/generate` call runs Designer → Validator → Optimizer (looped) → Final Validator → Educational, all hitting Bedrock serially.

On AWS this means:
- ALB idle timeout default is **60 s** — you'll truncate long runs. Bump to 120 s or more.
- API Gateway hard limit is **29 s** — so you **cannot** put API Gateway in front of this service as-is.
- You must request quota increases for the Bedrock models/region you use.

### Issue 5 — In-memory run history (`_RUN_HISTORY`)
```136:137:Cirq-RAG-Code-Assistant/src/server.py
_RUN_HISTORY: Dict[str, GenerateResponse] = {}
_MAX_HISTORY = 50
```
Behind a load balancer, user A lands on replica 1, clicks the run-history list on replica 2, and gets a **404**. Fine for a single container, broken for any horizontal scaling. Move to Redis (you already have it in `docker-compose.yml`) or DynamoDB.

### Issue 6 — AWS credentials in `.env`
`docker-compose.yml` uses:
```46:47:docker-compose.yml
    env_file:
      - ./Cirq-RAG-Code-Assistant/.env
```
That's fine locally. On AWS, **don't** bake keys into the image or push an `.env` with real keys. Use an **IAM Task Role** (ECS) or **instance profile** (EC2). Boto3 will pick it up automatically, no code changes needed.

### Issue 7 — `--reload` and bind-mounts in the compose file
```54:56:docker-compose.yml
    volumes:
      - ./Cirq-RAG-Code-Assistant:/app
    command: [ "uvicorn", "src.server:app", "--host", "0.0.0.0", "--port", "8000", "--reload" ]
```
This is a dev setup: it bind-mounts your host code over `/app` and enables auto-reload. On AWS you want a separate `docker-compose.prod.yml` (or just an ECS task definition) that removes the volume and drops `--reload`.

### Issue 8 — Bedrock model/region availability
Your config references `anthropic.claude-opus-4-6-v1`, `anthropic.claude-sonnet-4-6`, `anthropic.claude-haiku-4-5-20251001-v1:0`, and `amazon.nova-2-multimodal-embeddings-v1:0`. Before launch, verify each of those is:
- Available in `AWS_DEFAULT_REGION` (the config says `us-east-1`),
- Has **model access granted** in Bedrock console for your account,
- That you have inference profiles (or correct model IDs) set in `.env` — the code uses `BEDROCK_INFERENCE_PROFILE_ARN_*`.

### Issue 9 — No auth on the API
Any internet-facing deployment with `POST /api/v1/generate` open is a direct line to your Bedrock bill. Either put it in a private VPC reachable only by the QCanvas backend, or add an API key middleware, or both.

### Issue 10 — Logging to `outputs/logs/`
`logging.log_file: "outputs/logs/cirq_rag.log"` writes to disk. On Fargate this file is lost on task restart. Switch to stdout only (CloudWatch captures it automatically) or ship to CloudWatch Logs directly.

### Issue 11 — Ollama leftovers in the README
The README mentions creating `cirq-designer-agent` and `cirq-edu-agent` via Ollama, but `config.json` wires every agent to Bedrock. This is fine (Ollama is unused), but the README is misleading and may confuse whoever deploys this. Either delete those sections or mark them "local-dev only".

---

## 2. Should you move the vector store + embeddings into your DB?

**Yes. For your scale and architecture, this is a clear win.** You already run Postgres. Use **`pgvector`**.

### Why it's better than FAISS-on-disk for your situation

| Concern | FAISS on disk (current) | `pgvector` in Postgres |
|---|---|---|
| Persistence across container restarts | Requires volume/S3 sync | Free — DB is already persistent |
| Multi-replica consistency | Every replica has its own copy | Single source of truth |
| Add/update/delete a single KB entry | Re-build or re-save index | `INSERT` / `UPDATE` / `DELETE` |
| Filter by metadata (e.g. only "designer" examples) | Python post-filter after search | `WHERE agent_type='designer' ORDER BY embedding <=> q LIMIT 5` |
| Backups | Manual (you must back up the `.index` + `.pkl`) | Covered by your normal Postgres backups |
| Operational cost at your size (140 → 2,500 rows) | Negligible | Negligible and faster to query than cold-starting FAISS |
| Works with RDS/Aurora | N/A | Fully supported (Aurora Postgres + pgvector, RDS Postgres ≥ 15.5) |

At ~2,500 entries, pgvector with an **HNSW index** will serve queries in single-digit milliseconds. FAISS is only meaningfully faster at millions of vectors.

### Recommended table schema
```sql
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE rag_knowledge_base (
    id             BIGSERIAL PRIMARY KEY,
    source         TEXT NOT NULL,                      -- 'designer' | 'optimizer' | 'validator' | ...
    doc_id         TEXT NOT NULL UNIQUE,               -- stable external id (e.g. hash or file+index)
    content        TEXT NOT NULL,                      -- original text / code snippet
    content_hash   TEXT NOT NULL,                      -- sha256 of content, for dedup + cache invalidation
    metadata       JSONB NOT NULL DEFAULT '{}'::jsonb, -- algorithm, tags, complexity, etc.
    embedding      vector(1024) NOT NULL,              -- Nova dim matches config.embedding_dimension
    model_id       TEXT NOT NULL,                      -- which embedding model produced this vector
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX rag_kb_embedding_hnsw
    ON rag_knowledge_base
    USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);

CREATE INDEX rag_kb_source_idx   ON rag_knowledge_base (source);
CREATE INDEX rag_kb_metadata_gin ON rag_knowledge_base USING gin (metadata);
```

A few notes on the schema choices:
- **`embedding vector(1024)`** matches `aws.embeddings.embedding_dimension: 1024` in your config. Lock this with a CHECK or a config constant so you don't accidentally mix dimensions.
- **`model_id`** lets you re-embed with a newer model without losing old vectors during migration.
- **`content_hash`** lets you skip re-embedding unchanged documents — important because Nova is throttled/slow/paid.
- **`metadata JSONB`** replaces the pickle metadata dict; you can filter with SQL.
- **HNSW with `vector_cosine_ops`** matches what you're doing now in FAISS (you normalize L2, which is equivalent to cosine on unit vectors). If you use `vector_l2_ops` instead, you must make sure the embeddings stay normalized.

### A clean `VectorStore` integration path
Keep the existing `VectorStore` abstraction and add a third backend, e.g. `pgvector`, parallel to `faiss` and `chroma`. That preserves local-dev ergonomics:

- Local dev → FAISS (fast, zero infra)
- Deployed (AWS / docker-compose) → pgvector

```python
# pseudo-code, fits your current VectorStore shape
if self.vector_db_type == "pgvector":
    self._init_pgvector()  # psycopg2 / asyncpg + pgvector-python
```

Your `add()` becomes `INSERT … RETURNING id`, and `search()` becomes:
```sql
SELECT id, content, metadata,
       1 - (embedding <=> $1) AS score
FROM   rag_knowledge_base
WHERE  ($2::text IS NULL OR source = $2)
ORDER  BY embedding <=> $1
LIMIT  $3;
```

### Ingestion / migration script
Write a one-shot script (`scripts/ingest_kb_to_pgvector.py`) that:

1. Reads every `.jsonl` under `data/knowledge_base/`.
2. For each row, computes `content_hash`.
3. Checks `SELECT 1 FROM rag_knowledge_base WHERE doc_id=? AND content_hash=?`.
4. If missing or changed, calls Bedrock Nova once (respecting your 5 s delay) and upserts.
5. Runs idempotently so you can re-run safely.

This gives you an "embed once, query forever" flow, which is exactly what you want given Bedrock's embedding throttling.

### AWS-specific tips for pgvector
- On **RDS Postgres**, confirm your engine is ≥ 15.5 / 16.x (it supports `pgvector`). Enable the extension once: `CREATE EXTENSION vector;`.
- On **Aurora Postgres**, also supported — usually the better pick if you're already cloud-native.
- Use IAM DB auth or Secrets Manager for the DB password (don't hardcode it in `.env`).
- Put the Cirq service + RDS in the same VPC/subnet — don't route through the internet.

---

## 3. Concrete checklist I recommend you apply before AWS deploy

Production hardening for `Cirq-RAG-Code-Assistant`:
- [ ] Add `CORSMiddleware` for your QCanvas frontend origin(s).
- [ ] Add an API key / JWT / IAM Signature v4 check on `POST /api/v1/generate`.
- [ ] Split `requirements.txt` into `requirements-base.txt` (boto3, fastapi, pgvector client, cirq) and `requirements-local.txt` (torch, transformers, sentence-transformers, faiss). Dockerfile installs only base. Cuts image ~70–80%.
- [ ] Remove `--reload` and the host bind-mount in the production compose/task definition.
- [ ] Switch AWS auth from `.env` to IAM task role (ECS) or instance profile (EC2).
- [ ] Replace `_RUN_HISTORY` with Redis (you already have it in compose) or DynamoDB with TTL.
- [ ] Log to stdout only; ship to CloudWatch Logs.
- [ ] Raise ALB idle timeout ≥ 120 s; don't front this with API Gateway.
- [ ] Add a `/health` endpoint (trivial) so ECS/ALB health checks don't hit `/docs`.
- [ ] Pre-warm the container on start by loading the FAISS/pgvector client (avoid the first-request latency cliff).
- [ ] Request Bedrock model access + quota increases in your deployment region.
- [ ] Remove/mark Ollama instructions in the README as local-dev-only.

Vector-store migration to pgvector:
- [ ] Add `pgvector` extension to your RDS/Aurora instance.
- [ ] Create the `rag_knowledge_base` table + HNSW index.
- [ ] Add a `pgvector` backend to `VectorStore`.
- [ ] Write and run `scripts/ingest_kb_to_pgvector.py` with dedupe via `content_hash`.
- [ ] Set `rag.vector_store.type = "pgvector"` in the deployed config, keep `"faiss"` in your local `config.json`.
- [ ] Delete `data/models/vector_index/` from the production image.

---

### TL;DR

- It'll boot on AWS, but you'll hit: ephemeral FAISS on disk, a bloated image carrying torch/transformers you don't need, no CORS, no auth, in-memory run history that breaks behind a load balancer, ALB timeouts vs. Bedrock latency, and AWS creds in `.env`.
- Moving the vector store into Postgres with `pgvector` is the right move: one source of truth, survives restarts, shared across replicas, native SQL filtering, covered by your existing backups — and at 140→2,500 docs it's effectively as fast as FAISS. Keep FAISS only as a local-dev backend behind the same `VectorStore` abstraction.

Want me to:

1. Actually add a `pgvector` backend to `src/rag/vector_store.py` + write the ingestion script, or
2. Slim down the Dockerfile/requirements and add CORS + a proper `/health` endpoint first?

Either one is a focused next step — tell me which you want and I'll do it.

---

**User**

I want you to do and fix all of these issues, give me a proper plan for it. You can ask questions.

---

**Cursor**

Before I write the plan, two questions will materially change the shape of it — the rest I can figure out from the code.

> **What is the AWS deployment target for Cirq-RAG-Code-Assistant? This changes how we handle auth, secrets, networking, image size, and the run-history store.**
> - ECS Fargate behind an ALB (serverless containers, recommended for this workload) ✔
> - Single EC2 instance running docker-compose (simplest, cheapest, no autoscaling)
> - AWS App Runner (managed, but has 120s request limit and smaller tasks)
> - ECS on EC2 (more control, shared EBS volume possible)
> - Not sure yet, pick the one you'd recommend and plan around it

> **Where should the pgvector-backed knowledge base live?**
> - Inside the existing QCanvas Postgres (qcanvas_db in docker-compose.yml, same DB as the rest of QCanvas) - new table alongside QCanvas tables
> - In the same Postgres instance but a separate logical DB (e.g. cirq_rag_db) - isolated but one server
> - A dedicated AWS RDS/Aurora Postgres instance just for the Cirq RAG service
> - Not sure, pick the one you'd recommend ✔

Let me do a quick look at `requirements.txt` and the backend's Postgres setup so I can be specific about the split and reuse existing patterns.

I have enough to write a concrete plan. My DB recommendation, since you left it to me: **same Postgres instance/database as QCanvas (`qcanvas_db`), but in its own schema (`cirq_rag`)** — isolates the RAG tables without needing a second DB server, and easy to promote to its own RDS later by only changing the connection URL.

---

**User**

Implement the plan as specified, it is attached for your reference. Do NOT edit the plan file itself.

To-do's from the plan have already been created. Do not create them again. Mark them as in_progress as you work, starting with the first one. Don't stop until you have completed all the to-dos.

---

**Cursor**

Now I'll implement the pgvector backend. I'll add it as a third branch alongside FAISS and Chroma.

Now add the `_init_pgvector` method and related methods. Let me insert them after `_init_chroma`.

Now update the `add` method body to dispatch to pgvector and update the docstring, then add the pgvector-specific methods. Let me find and update:

Now add `_add_pgvector` after `_add_chroma`, and update the `search` dispatch. Let me find and update:

Now update the `search` method to dispatch pgvector, and add the `_search_pgvector` method:

Add `_search_pgvector` after `_search_chroma`:

Now update `get_by_id`, `size`, `save`, `load` to handle pgvector:

Now update `save` and `load` to no-op on pgvector (DB is the persistence):

Let me verify the file reads cleanly:

Now mark first todo complete, start next: the SQL migration file.

Now update `config.json` to add pgvector block, and `config_loader.py` for env override mapping. I'll handle config.json and then the env overrides (both todos pgvector_config + env_overrides share the loader file).

Now let me tackle both `pgvector_config` and `env_overrides` together by adding an explicit env override mapping in config_loader.py:

Now the ingestion script. It needs to read the three JSONL files, dedupe via SHA256, call Bedrock via EmbeddingModel, and upsert into Postgres:

Now split requirements into three files:

Now update the existing `requirements.txt` to just point to the dev bundle for back-compat:

Now rewrite the Dockerfile as a multi-stage slim build and add a `Dockerfile.dev`, plus update `.dockerignore`:

Update `.dockerignore` to exclude more heavy paths:

The imports in `embeddings.py` are already inside `try/except` so torch and sentence-transformers are already optional. However the `_init_local` raises ImportError. Also the `config_loader.py` has `setup_pytorch()` that imports torch. Let me check everywhere torch might be imported at module-level:

Good — torch, sentence-transformers, and faiss are already guarded by try/except in both files. Let me also check `config_loader.py`'s `setup_pytorch()`:

`setup_pytorch()` is called at module init unconditionally. This does `import torch` with a try/except so it's safe but adds useless work in prod. Let me make it skip if we're clearly not using torch (provider=aws and no torch available):

Now let me also defensively guard `_determine_device` in embeddings.py — it references `torch.cuda.is_available()` which is only fine if torch imported, which we already guard with `TORCH_AVAILABLE`. Let me verify the embeddings path doesn't break in the slim image. When `provider=="aws"`, `_init_aws` is called and `_determine_device` is never used. Good.

Let me also double-check `knowledge_base.py` for torch imports:

Fine. Let me also check the agents for torch imports:

Good — no torch imports in production code paths. Slim image should be torch-free.

Let me look at the logging module before rewriting server.py:

Now let me create `src/run_history.py` first, then update `src/server.py` with auth, CORS, health, error handling, run-history integration, startup validation, and stdout logging:

Now a small `src/auth.py` module:

Now let me rewrite `src/server.py` with all the production hardening:

The warnings are pre-existing from the original code. Let me verify the logging module won't break with `enable_file=False`. Looking at the `LoggingConfig.__init__`, it unconditionally creates the log directory. Let me fix that:

Also fix `setup_standard_logging` which unconditionally tries to create a file handler when `enable_file` is True, but uses `FileHandler` (not rotating) and also adds `NullHandler` wrong:

Also make loguru stdout format use JSON serializer when requested:

Now mark the completed todos. Note that `cors_auth_health`, `redis_run_history`, `error_envelope`, `logging_stdout`, and `startup_validation` are all done in this rewrite:

Now the production compose file:

Now the ECS task definition and deployment docs. Create `deploy/ecs/` directory with task def JSON, IAM policy snippets, and a README:

Now docs update. Mark Ollama as local-only in README, note X-API-Key in integration guide, and add `docs/deployment-aws.md`:

Also update the "Docker Deployment" section in the README to reference the new files:

Now update the integration guide to note `X-API-Key`:

Also update the API client in the integration guide to send the header:

Now create the deployment guide doc:

Good, test tree exists. Let me write the three unit tests:

Now the auth test:

Now the pgvector unit test with a mocked psycopg connection:

These are style nitpicks only. Let me add a nested comment for the empty close method and leave `np.random.rand` (unchanged behaviour and fine for tests):

Now the opt-in integration test and the smoke script:

Now the smoke script:

Let me clean up the clearly bogus conditional in the ingest script:

Now let me do a final sanity check by running the new unit tests to make sure they work. First let me verify the test imports can be resolved:

Existing tests use `from src.xxx`. Need to add project root (not `src`) to sys.path. Let me update `conftest.py`:

Let me try actually running the unit tests I added to make sure they pass:

All 21 new unit tests pass. Let me also confirm I didn't break any existing tests:

All existing unit tests still pass. Let me also run the full test tree briefly to make sure I haven't broken anything at a module-import level:

All tests collect cleanly. Mark the last todo done:

All 18 todos complete. Here is a recap of what changed, grouped by the plan's phases.

## Phase 1 — pgvector backend
- [Cirq-RAG-Code-Assistant/src/rag/vector_store.py](Cirq-RAG-Code-Assistant/src/rag/vector_store.py): new `pgvector` backend branch (init, upsert, cosine search, get_by_id, size, save/load no-op) alongside the existing FAISS and Chroma ones.
- [Cirq-RAG-Code-Assistant/scripts/sql/001_init_pgvector.sql](Cirq-RAG-Code-Assistant/scripts/sql/001_init_pgvector.sql): extension + `cirq_rag` schema + `rag_knowledge_base` table (1024-dim `vector`) + HNSW cosine index + source/metadata indexes + `updated_at` trigger.
- [Cirq-RAG-Code-Assistant/config/config.json](Cirq-RAG-Code-Assistant/config/config.json): adds `rag.vector_store.pgvector` block (`schema`, `table`, `dsn_env`).
- [Cirq-RAG-Code-Assistant/scripts/ingest_kb_to_pgvector.py](Cirq-RAG-Code-Assistant/scripts/ingest_kb_to_pgvector.py): idempotent ingestion script (SHA-256 dedup, `--limit`, `--dry-run`) that reads all `curated_*_examples.jsonl` files and upserts with the current embedding `model_id`.

## Phase 2 — slim Docker / dependency split
- [Cirq-RAG-Code-Assistant/requirements-base.txt](Cirq-RAG-Code-Assistant/requirements-base.txt) (prod runtime, no torch), [Cirq-RAG-Code-Assistant/requirements-local.txt](Cirq-RAG-Code-Assistant/requirements-local.txt) (adds FAISS/torch/sentence-transformers), [Cirq-RAG-Code-Assistant/requirements-dev.txt](Cirq-RAG-Code-Assistant/requirements-dev.txt) (tests + notebooks + research libs), [Cirq-RAG-Code-Assistant/requirements.txt](Cirq-RAG-Code-Assistant/requirements.txt) reduced to a back-compat alias.
- [Cirq-RAG-Code-Assistant/Dockerfile](Cirq-RAG-Code-Assistant/Dockerfile): multi-stage slim build, non-root user, `libpq5` only, `HEALTHCHECK` against `/health`, `CIRQ_RAG_LOG_MODE=stdout CIRQ_RAG_LOG_FORMAT=json` in env.
- [Cirq-RAG-Code-Assistant/Dockerfile.dev](Cirq-RAG-Code-Assistant/Dockerfile.dev): dev image with the full stack and `--reload`.
- [Cirq-RAG-Code-Assistant/.dockerignore](Cirq-RAG-Code-Assistant/.dockerignore): excludes notebooks, docs, `data/models`, tests, `.cache`, etc.
- `config_loader._should_setup_pytorch()` skips `setup_pytorch()` in the slim image so a torch-less runtime never tries to import it.

## Phase 3 — production server hardening
- [Cirq-RAG-Code-Assistant/src/auth.py](Cirq-RAG-Code-Assistant/src/auth.py): `require_api_key` FastAPI dep using `hmac.compare_digest`; dev is permissive, prod fails closed if `CIRQ_RAG_API_KEY` is unset.
- [Cirq-RAG-Code-Assistant/src/run_history.py](Cirq-RAG-Code-Assistant/src/run_history.py): `RunHistoryStore` interface + `InMemoryRunHistory` and `RedisRunHistory` (ZSET index, 24 h TTL, auto-stale cleanup) and `build_run_history_store` factory.
- [Cirq-RAG-Code-Assistant/src/server.py](Cirq-RAG-Code-Assistant/src/server.py) rewritten to add:
  - `CORSMiddleware` driven by `CIRQ_RAG_ALLOWED_ORIGINS`
  - `X-API-Key` dep on every `/api/v1/*`
  - `GET /health`, `GET /readiness` (checks run-history + Postgres when pgvector is on)
  - `_classify_error` + global exception handler → 503 with `Retry-After` on Bedrock throttling / timeouts
  - Startup banner + `_validate_prod_env` that fails fast on missing prod env vars
  - Runs now persist via the `RunHistoryStore`
  - `/docs`, `/redoc`, `/openapi.json` toggleable with `CIRQ_RAG_DISABLE_DOCS`.

## Phase 4 — config, logging, startup
- [Cirq-RAG-Code-Assistant/config/config_loader.py](Cirq-RAG-Code-Assistant/config/config_loader.py): explicit `_ENV_OVERRIDES` table (including `CIRQ_RAG_VECTOR_STORE_TYPE`, CORS origins, run-history backend, log mode/format), `_set_dotted` helper, PyTorch init skipped when AWS+no-torch.
- [Cirq-RAG-Code-Assistant/src/cirq_rag_code_assistant/config/logging.py](Cirq-RAG-Code-Assistant/src/cirq_rag_code_assistant/config/logging.py): JSON console logging via loguru `serialize=True`, tolerates read-only filesystems, `enable_file` respected end-to-end.

## Phase 5 — compose + ECS
- [docker-compose.yml](docker-compose.yml): `cirq_agent` dev service now uses `Dockerfile.dev`, healthchecks hit `/health`.
- [docker-compose.prod.yml](docker-compose.prod.yml) (new): slim image, Postgres + Redis + cirq_agent, pgvector DSN, Redis run history, API key env, stdout JSON logs.
- [Cirq-RAG-Code-Assistant/deploy/ecs/cirq-agent.taskdef.json](Cirq-RAG-Code-Assistant/deploy/ecs/cirq-agent.taskdef.json), [task-role-policy.json](Cirq-RAG-Code-Assistant/deploy/ecs/task-role-policy.json), [execution-role-policy.json](Cirq-RAG-Code-Assistant/deploy/ecs/execution-role-policy.json), [deploy/ecs/README.md](Cirq-RAG-Code-Assistant/deploy/ecs/README.md) (ECR push, IAM roles, Secrets Manager entries, service creation, ALB idle-timeout note, "do NOT front with API Gateway").

## Phase 6 — docs
- [Cirq-RAG-Code-Assistant/README.md](Cirq-RAG-Code-Assistant/README.md): Ollama section marked local-only; Docker section points to slim + dev images + new deployment guide.
- [Cirq-RAG-Code-Assistant/QCANVAS_INTEGRATION_GUIDE.md](Cirq-RAG-Code-Assistant/QCANVAS_INTEGRATION_GUIDE.md): prod base URL guidance, `X-API-Key` header requirement, 503 / `Retry-After` error envelope, TS client updated to send the header.
- [Cirq-RAG-Code-Assistant/docs/deployment-aws.md](Cirq-RAG-Code-Assistant/docs/deployment-aws.md) (new): target topology diagram, required env vars, health endpoints, runbook.

## Phase 7 — tests
- [tests/unit/test_vector_store_pgvector.py](Cirq-RAG-Code-Assistant/tests/unit/test_vector_store_pgvector.py), [test_run_history.py](Cirq-RAG-Code-Assistant/tests/unit/test_run_history.py), [test_auth_api_key.py](Cirq-RAG-Code-Assistant/tests/unit/test_auth_api_key.py) — **21 tests, all passing**; pre-existing unit tests still green.
- [tests/integration/test_pgvector_roundtrip.py](Cirq-RAG-Code-Assistant/tests/integration/test_pgvector_roundtrip.py): opt-in, skipped unless `CIRQ_RAG_DB_URL` is set.
- [scripts/smoke_prod.py](Cirq-RAG-Code-Assistant/scripts/smoke_prod.py): `/health` + `/readiness` + minimal `/api/v1/generate` round-trip, sends `X-API-Key`.
- `tests/conftest.py`: adds project root to `sys.path` so `from src.xxx import ...` works in tests.

### Next real-world step for you
1. Provision RDS Postgres 15.5+ and run `scripts/sql/001_init_pgvector.sql`.
2. Create the Secrets Manager entries listed in `deploy/ecs/README.md`.
3. `docker build -f Dockerfile -t cirq-agent:prod .`, push to ECR.
4. `python scripts/ingest_kb_to_pgvector.py` once (with `CIRQ_RAG_DB_URL` exported) to seed the KB.
5. Register the task definition, create the ECS service, raise ALB idle timeout to 180s.
6. Smoke-test with `python scripts/smoke_prod.py --base-url https://... --api-key ...`.

