from pydantic_settings import BaseSettings
from pydantic import field_validator
from typing import Optional
from pathlib import Path
import json
from urllib.parse import urlparse


ROOT_ENV_FILE = Path(__file__).resolve().parents[3] / ".env"

DEFAULT_CORS_ORIGINS = [
    "http://localhost:3000",
    "http://localhost:8000",
    "http://127.0.0.1:3000",
    "http://127.0.0.1:8000",
    "https://qcanvas.codes",
    "https://www.qcanvas.codes",
]

class Settings(BaseSettings):
    PROJECT_NAME: str = "QCanvas"
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api/v1"
    
    # Database
    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: str = "postgres"
    POSTGRES_SERVER: str = "127.0.0.1"
    POSTGRES_PORT: str = "5433"
    POSTGRES_DB: str = "qcanvas_db"
    DATABASE_URL: Optional[str] = None

    # Redis
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0
    REDIS_URL: Optional[str] = None

    # Security
    SECRET_KEY: str = "development_secret_key"
    # Access-token lifetime. Active users get a fresh token via /api/auth/refresh
    # (on IDE load, hourly, and on tab focus), so this is the max idle time.
    # (Was a hardcoded 30 min that silently broke saves/file loads mid-session.)
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24
    # Absolute session cap: refresh is refused this long after the original login.
    SESSION_MAX_AGE_DAYS: int = 30
    # "Try demo" creates a private temporary guest account per visitor.
    # Guest workspaces are purged on logout or after this many hours.
    GUEST_ACCOUNT_TTL_HOURS: int = 72
    # Per client IP. Sized so ~200 attendees behind one venue NAT can all start
    # within a few minutes, while bounding abuse.
    GUEST_CREATE_RATE_LIMIT: str = "60/minute;400/hour;1500/day"
    # Global cap on live guest accounts; beyond it /guest returns 503.
    # Well above any single IP's allowance; at the cap, abandoned guests are
    # evicted first (see guest_service.purge_idle_guests).
    GUEST_MAX_ACTIVE: int = 5000
    # A guest with no saved files and no activity for this long is "abandoned".
    GUEST_IDLE_TTL_HOURS: int = 3
    AUTH_EMAIL_OTP_ENABLED: bool = False
    OTP_EXPIRE_MINUTES: int = 5
    OTP_MAX_ATTEMPTS: int = 5
    OTP_RESEND_COOLDOWN_SECONDS: int = 60
    OTP_PEPPER: str = ""

    # Email
    EMAIL_PROVIDER: str = "resend"
    EMAIL_FROM_NAME: str = "QCanvas"
    EMAIL_FROM_ADDRESS: str = "noreply@example.com"
    RESEND_API_KEY: str = ""
    RESEND_API_BASE_URL: str = "https://api.resend.com"
    FRONTEND_URL: str = "http://localhost:3000"
    MASTER_ADMIN_EMAIL: str = ""
    
    # CORS
    BACKEND_CORS_ORIGINS: list[str] = DEFAULT_CORS_ORIGINS

    # Cirq-RAG-Code-Assistant (proxied at /api/cirq-agent/*). Use port 8001 locally to avoid clashing with QCanvas on 8000.
    CIRQ_AGENT_URL: str = "http://127.0.0.1:8001"
    # API key the proxy sends as X-API-Key to the Cirq agent. Leave empty to skip.
    CIRQ_RAG_API_KEY: str = ""

    # FastQSim Online Mode settings
    FASTQSIM_ONLINE_MODE: bool = False
    FASTQUBIT_USER_ID: str = ""
    FASTQSIM_API_TOKEN: str = ""
    FASTQUBIT_ENDPOINT: str = "https://fastqubit.dev/api"
    FASTQSIM_EXECUTION_MODE: str = "cloud"
    # Seconds to cache the FASTQSIM_ONLINE_MODE lookup (it may hit AWS SSM).
    FASTQSIM_ONLINE_MODE_CACHE_SECONDS: int = 30

    # General
    # When True, unhandled-exception responses include the exception text/type.
    DEBUG: bool = False
    # "production" disables dev conveniences such as accepting any localhost
    # port as a CORS origin. Set ENVIRONMENT=production in deployed envs.
    ENVIRONMENT: str = "development"

    # ------------------------------------------------------------------
    # Rate limiting (slowapi). Limit strings use the "N/period" syntax and may
    # be combined with ";" (e.g. "300/minute;3000/hour").
    # Keys: authenticated requests are keyed by user id; everything else by the
    # real client IP (taken from X-Forwarded-For, see FORWARDED_TRUSTED_HOPS).
    # Workshop note: 100-200 students usually share ONE venue NAT IP, so per-IP
    # limits on auth endpoints must allow everyone to sign up / log in at once.
    # ------------------------------------------------------------------
    RATE_LIMIT_ENABLED: bool = True
    # "" or "auto": use REDIS_URL if it answers a ping at startup, else memory://.
    # Set explicitly (e.g. "memory://" or "redis://host:6379/1") to skip the probe.
    RATE_LIMIT_STORAGE_URI: str = ""
    RATE_LIMIT_REDIS_TIMEOUT_SECONDS: float = 0.5
    # Number of trusted proxies that append to X-Forwarded-For (ALB = 1;
    # Cloudflare -> ALB = 2). 0 ignores X-Forwarded-For entirely.
    FORWARDED_TRUSTED_HOPS: int = 1
    # Forwarded headers (X-Forwarded-For / CLIENT_IP_HEADER) are honoured ONLY
    # when the TCP peer is in one of these CIDRs, i.e. the request really came
    # through our load balancer. Clients connecting directly can't spoof their IP.
    # Defaults cover private networks (where an AWS ALB connects from).
    TRUSTED_PROXY_CIDRS: str = "10.0.0.0/8,172.16.0.0/12,192.168.0.0/16,127.0.0.0/8,::1/128,fc00::/7"
    # Optional header that already carries the real client IP (e.g. "CF-Connecting-IP").
    CLIENT_IP_HEADER: str = ""

    # Auth endpoints (keyed per IP: there is no session yet)
    RATE_LIMIT_LOGIN: str = "300/minute;3000/hour"
    RATE_LIMIT_REGISTER: str = "300/minute;2000/hour"
    RATE_LIMIT_REGISTER_ADMIN: str = "10/minute"
    RATE_LIMIT_OTP_SEND: str = "200/minute;1000/hour"
    RATE_LIMIT_OTP_VERIFY: str = "300/minute"
    RATE_LIMIT_PASSWORD_RESET: str = "120/minute"
    # Compute endpoints (convert / simulate): per signed-in user, and per IP for
    # anonymous callers (who share the venue IP).
    RATE_LIMIT_COMPUTE_PER_USER: str = "30/minute"
    RATE_LIMIT_COMPUTE_PER_IP: str = "600/minute"
    # Circuit parsing for visualization (cheap AST parse)
    RATE_LIMIT_PARSE_PER_USER: str = "120/minute"
    RATE_LIMIT_PARSE_PER_IP: str = "1200/minute"
    # Client-reported gamification activities (POST /api/gamification/activity)
    RATE_LIMIT_GAMIFICATION_ACTIVITY: str = "20/hour"
    # Comma-separated activity types the client may report itself. Everything
    # else (simulation_run, conversion, algorithm_*, ...) is awarded server-side only.
    GAMIFICATION_CLIENT_ACTIVITY_TYPES: str = "tutorial_completed,quiz_passed,concept_mastered,easter_egg_found"

    # ------------------------------------------------------------------
    # Simulation safety (enforced server-side in /api/simulator/*)
    # ------------------------------------------------------------------
    SIM_MAX_QUBITS: int = 24
    # The PennyLane path can add one wire per measured qubit (deferred
    # measurement), doubling the statevector width; 12 keeps it <= ~24 wires.
    SIM_MAX_QUBITS_PENNYLANE: int = 12
    # Legacy /api/simulator/execute builds a Python-list statevector (2^n entries).
    SIM_LEGACY_MAX_QUBITS: int = 16
    SIM_MAX_SHOTS: int = 100_000
    SIM_MAX_QASM_CHARS: int = 200_000
    # Max simulations running at once PER WORKER PROCESS; extra requests queue.
    SIM_MAX_CONCURRENCY: int = 2
    # How long a queued simulation waits for a slot before getting a 503 "busy".
    SIM_QUEUE_TIMEOUT_SECONDS: float = 60.0
    # Same idea for /api/converter/* conversions.
    CONVERT_MAX_CONCURRENCY: int = 4
    CONVERT_QUEUE_TIMEOUT_SECONDS: float = 60.0

    # ------------------------------------------------------------------
    # Database connection pool (per worker process!). Total connections to
    # Postgres = WEB_CONCURRENCY * (DB_POOL_SIZE + DB_MAX_OVERFLOW) + audit writer.
    # ------------------------------------------------------------------
    DB_POOL_SIZE: int = 5
    DB_MAX_OVERFLOW: int = 5
    DB_POOL_TIMEOUT: int = 10
    DB_POOL_RECYCLE: int = 1800
    DB_POOL_PRE_PING: bool = True
    DB_CONNECT_TIMEOUT: int = 10

    # ------------------------------------------------------------------
    # API audit log (api_activity table). Written off the request path in
    # batches by a background thread; never blocks or fails a request.
    # ------------------------------------------------------------------
    AUDIT_LOG_ENABLED: bool = True
    AUDIT_LOG_BATCH_SIZE: int = 200
    AUDIT_LOG_FLUSH_INTERVAL_SECONDS: float = 2.0
    AUDIT_LOG_MAX_QUEUE: int = 10_000
    # Comma-separated path prefixes that are never logged (health/docs are always skipped).
    AUDIT_LOG_EXCLUDE_PATHS: str = ""


    @field_validator("BACKEND_CORS_ORIGINS", mode="before")
    @classmethod
    def parse_cors_origins(cls, value):
        if value is None or value == "":
            return DEFAULT_CORS_ORIGINS
        if isinstance(value, list):
            return [str(v).strip() for v in value if str(v).strip()]
        if isinstance(value, str):
            raw = value.strip()
            if not raw:
                return DEFAULT_CORS_ORIGINS

            # Supports JSON arrays in env vars for ECS/Secrets Manager.
            if raw.startswith("["):
                try:
                    parsed = json.loads(raw)
                    if isinstance(parsed, list):
                        return [str(v).strip() for v in parsed if str(v).strip()]
                except json.JSONDecodeError:
                    pass

            # Fallback: comma-separated origins.
            return [item.strip() for item in raw.split(",") if item.strip()]

        return DEFAULT_CORS_ORIGINS

    def _should_rebuild_database_url(self) -> bool:
        if not self.DATABASE_URL:
            return True

        local_hosts = {"127.0.0.1", "localhost"}
        if self.POSTGRES_SERVER in local_hosts:
            return False

        return any(host in self.DATABASE_URL for host in local_hosts)

    def model_post_init(self, __context):
        if self._should_rebuild_database_url():
            self.DATABASE_URL = f"postgresql://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_SERVER}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        if self.REDIS_URL is None:
            self.REDIS_URL = f"redis://{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"

        # Ensure FRONTEND_URL (if set) is included in CORS origins to allow browser requests
        try:
            parsed = urlparse(self.FRONTEND_URL or "")
            origin = f"{parsed.scheme}://{parsed.netloc}" if parsed.scheme and parsed.netloc else None
        except Exception:
            origin = None

        if origin:
            # BACKEND_CORS_ORIGINS may be a list; ensure we don't duplicate
            if isinstance(self.BACKEND_CORS_ORIGINS, list):
                if origin not in self.BACKEND_CORS_ORIGINS:
                    self.BACKEND_CORS_ORIGINS.append(origin)
            else:
                # If somehow parsed as a string, rebuild as list
                self.BACKEND_CORS_ORIGINS = [origin]

    class Config:
        case_sensitive = True
        env_file = str(ROOT_ENV_FILE)
        extra = "ignore"

settings = Settings()
