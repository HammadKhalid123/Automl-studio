from contextlib import asynccontextmanager
import logging

from fastapi import FastAPI
from fastapi.responses import Response
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware

from app.api.datasets import router as datasets_router
from app.api.jobs import router as jobs_router
from app.api.models import router as models_router
from app.api.assistant import router as assistant_router
from app.api.auth import router as auth_router
from app.core import config, storage
from app.services import job_runner
from app.db.session import cleanup_auth_records, init_db

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    del _app
    if len(config.JWT_SECRET) < 32:
        raise RuntimeError("Set a JWT_SECRET with at least 32 characters in project_backend/.env before starting the API.")
    config.ensure_dirs()
    init_db()
    if config.DATABASE_URL.startswith("sqlite:"):
        logger.warning("DATABASE_URL is not configured; accounts and run history use local SQLite and may be lost when the host restarts.")
    storage.ensure_storage_dirs()
    cleanup_auth_records()
    storage.cleanup_expired()
    job_runner.recover_interrupted_jobs()
    try:
        yield
    finally:
        job_runner.shutdown_runner()


app = FastAPI(title="AutoML Studio", lifespan=lifespan)
app.add_middleware(
    SessionMiddleware,
    secret_key=config.JWT_SECRET,
    same_site="lax",
    https_only=config.FRONTEND_URL.startswith("https://"),
    max_age=600,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=list(dict.fromkeys([config.FRONTEND_URL, "http://localhost:5173", "http://127.0.0.1:5173"])),
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(datasets_router)
app.include_router(jobs_router)
app.include_router(models_router)
app.include_router(assistant_router)
app.include_router(auth_router)


@app.get("/")
def root():
    return {
        "name": "AutoML Studio API",
        "status": "ok",
        "frontend": "http://localhost:5173",
        "docs": "/docs",
        "health": "/health",
    }


@app.get("/health")
def health():
    durable = not config.DATABASE_URL.startswith("sqlite:")
    return {"status": "ok", "persistent_database": durable, "persistent_history": durable}


@app.get("/favicon.ico", include_in_schema=False)
def favicon():
    return Response(status_code=204)
