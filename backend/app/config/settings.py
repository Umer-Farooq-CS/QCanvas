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
    # Max idle session length. Active users get a fresh token via /api/auth/refresh.
    # Default: 7 days. (Was a hardcoded 30 min, which silently broke saves/file loads
    # for anyone who kept the IDE open or came back later.)
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7
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
