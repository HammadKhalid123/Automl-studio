from pathlib import Path
import os

BASE_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = BASE_DIR / "data"
ARTIFACTS_DIR = BASE_DIR / "artifacts"
SAMPLE_DIR = BASE_DIR / "sample_data"

RANDOM_SEED = 42
TEST_SIZE = 0.2
CV_FOLDS = 5

SUPPORTED_TASKS = ("classification", "regression")

MAX_FILE_MB = 20
MIN_ROWS = 20
MAX_ROWS = 100_000
MIN_COLUMNS = 2
MAX_COLUMNS = 100

MAX_CLASSES = 20
MIN_CLASS_COUNT = 2

HIGH_MISSING_PCT = 50.0
ID_UNIQUE_RATIO = 0.95
MAX_CATEGORIES = 50


def _load_env():
    env_path = BASE_DIR / ".env"
    if not env_path.is_file():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip().upper(), value.strip().strip("\"'"))


_load_env()
GROQ_API_KEY = os.getenv("GROQ_API_KEY") or os.getenv("GROQ_AI_API_KEY", "")
MODEL_NAME = "openai/gpt-oss-20b"
GROQ_MODEL = os.getenv("GROQ_MODEL", MODEL_NAME)

# Authentication and persistence settings. Secrets are read from the environment;
# values are intentionally never included in startup logs or API responses.
DATABASE_URL = os.getenv("DATABASE_URL") or f"sqlite:///{(DATA_DIR / 'app.db').as_posix()}"
JWT_SECRET = os.getenv("JWT_SECRET", "")
JWT_EXPIRE_MINUTES = int(os.getenv("JWT_EXPIRE_MINUTES", "2880"))
GITHUB_CLIENT_ID = os.getenv("GITHUB_CLIENT_ID", "")
GITHUB_CLIENT_SECRET = os.getenv("GITHUB_CLIENT_SECRET", "")
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET", "")
SMTP_HOST = os.getenv("SMTP_HOST", "")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
MAIL_FROM = os.getenv("MAIL_FROM", "")
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:5173").rstrip("/")
# FastAPI Cloud provides FASTAPI_PUBLIC_URL at runtime. Prefer an explicit
# BACKEND_URL when configured, otherwise use the platform's public app URL so
# OAuth providers never receive the local-development callback in production.
BACKEND_URL = (
    os.getenv("BACKEND_URL")
    or os.getenv("FASTAPI_PUBLIC_URL")
    or "http://127.0.0.1:8000"
).rstrip("/")


def ensure_dirs():
    for folder in (DATA_DIR, ARTIFACTS_DIR, SAMPLE_DIR):
        folder.mkdir(parents=True, exist_ok=True)
