from sqlalchemy import create_engine, event, inspect, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.core import config


def _database_url():
    url = config.DATABASE_URL
    if url.startswith("postgres://"):
        return "postgresql+psycopg://" + url[len("postgres://"):]
    if url.startswith("postgresql://"):
        return "postgresql+psycopg://" + url[len("postgresql://"):]
    return url


DATABASE_URL = _database_url()
if DATABASE_URL.startswith("sqlite:"):
    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    engine = create_engine(
        DATABASE_URL,
        connect_args={"check_same_thread": False, "timeout": 30},
        pool_pre_ping=True,
    )

    @event.listens_for(engine, "connect")
    def _enable_sqlite_foreign_keys(connection, _record):
        cursor = connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA busy_timeout=30000")
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.close()
else:
    engine = create_engine(DATABASE_URL, pool_pre_ping=True)


class Base(DeclarativeBase):
    pass


SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db():
    with SessionLocal() as session:
        yield session


def init_db():
    from app.db import models  # noqa: F401

    Base.metadata.create_all(bind=engine)
    # create_all does not add columns to existing accounts databases. Keep this
    # small additive migration backward-compatible with existing SQLite installs.
    columns = {column["name"] for column in inspect(engine).get_columns("users")}
    if "display_name" not in columns:
        with engine.begin() as connection:
            connection.execute(text("ALTER TABLE users ADD COLUMN display_name VARCHAR(80)"))


def cleanup_auth_records():
    from sqlalchemy import delete
    from app.db.models import OAuthCode, OneTimeEmailToken, RevokedToken, utcnow

    now = utcnow()
    with SessionLocal.begin() as session:
        session.execute(delete(OAuthCode).where(OAuthCode.expires_at < now))
        session.execute(delete(OneTimeEmailToken).where(OneTimeEmailToken.expires_at < now))
        session.execute(delete(RevokedToken).where(RevokedToken.expires_at < now))
