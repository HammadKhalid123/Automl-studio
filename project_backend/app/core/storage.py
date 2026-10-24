import json
import os
import re
import shutil
import sqlite3
import time
import zipfile
from contextlib import contextmanager
from threading import Lock
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from app.core import config, limits
from app.services.data_profile import DataValidationError

DATASETS_DIR = config.DATA_DIR / "datasets"
JOBS_DIR = config.DATA_DIR / "jobs"
MODELS_DIR = config.ARTIFACTS_DIR
DATABASE_PATH = config.DATA_DIR / "automl.sqlite3"

DATASET_FILE = "data.csv"
DATASET_META_FILE = "meta.json"
MODEL_FILE = "pipeline.joblib"
SPLIT_FILES = ("train.csv", "validation.csv", "test.csv")
_storage_initialized = False
_storage_init_lock = Lock()


class StorageError(Exception):
    pass


class NotFoundError(StorageError):
    pass


class PayloadTooLargeError(DataValidationError):
    pass


def ensure_storage_dirs():
    global _storage_initialized
    if _storage_initialized:
        return
    with _storage_init_lock:
        if _storage_initialized:
            return
        for folder in (DATASETS_DIR, JOBS_DIR, MODELS_DIR):
            folder.mkdir(parents=True, exist_ok=True)
        config.DATA_DIR.mkdir(parents=True, exist_ok=True)
        with _db_connection() as connection:
            connection.execute("""CREATE TABLE IF NOT EXISTS jobs (
                job_id TEXT PRIMARY KEY,
                status TEXT NOT NULL,
                dataset_id TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                report_json TEXT
            )""")
            connection.execute("CREATE INDEX IF NOT EXISTS idx_jobs_dataset_created ON jobs(dataset_id, created_at DESC)")
            connection.execute("CREATE INDEX IF NOT EXISTS idx_jobs_status_created ON jobs(status, created_at DESC)")
            _migrate_job_files(connection)
        _storage_initialized = True


@contextmanager
def _db_connection():
    connection = sqlite3.connect(DATABASE_PATH, timeout=30)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA journal_mode=WAL")
    connection.execute("PRAGMA synchronous=NORMAL")
    connection.execute("PRAGMA foreign_keys=ON")
    connection.execute("PRAGMA busy_timeout=30000")
    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def _migrate_job_files(connection):
    for path in JOBS_DIR.glob("*.json"):
        if not is_valid_id(path.stem):
            continue
        try:
            payload = read_json(path)
            encoded = json.dumps(payload, allow_nan=False)
        except (OSError, json.JSONDecodeError, ValueError):
            continue
        report_json = None
        model_id = payload.get("model_id")
        report_path = MODELS_DIR / model_id / "report.json" if model_id and is_valid_id(model_id) else None
        if report_path and report_path.is_file():
            try:
                report_json = report_path.read_text(encoding="utf-8")
            except OSError:
                pass
        created = payload.get("created_at") or ""
        connection.execute(
            "INSERT OR IGNORE INTO jobs(job_id,status,dataset_id,created_at,updated_at,payload_json,report_json) VALUES(?,?,?,?,?,?,?)",
            (payload.get("job_id", path.stem), payload.get("status", "failed"), payload.get("dataset_id", ""), created, payload.get("finished_at") or created, encoded, report_json),
        )


def new_id():
    return uuid4().hex[:12]


def is_valid_id(value):
    return isinstance(value, str) and re.fullmatch(limits.ID_PATTERN, value) is not None


def _checked_id(value, label):
    if not is_valid_id(value):
        raise NotFoundError(f"{label} not found.")
    return value


def _safe_child(base, name):
    base = base.resolve()
    child = (base / name).resolve()
    if base != child and base not in child.parents:
        raise NotFoundError("Path not allowed.")
    return child


def _clean_filename(filename):
    name = Path(filename or "").name
    name = re.sub(r"[^\w.\- ]", "_", name).strip()
    return name[: limits.MAX_FILENAME_LENGTH]


def write_json(path, data):
    path = Path(path)
    temp_path = path.with_name(path.name + ".tmp")
    temp_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    os.replace(temp_path, path)


def read_json(path):
    path = Path(path)
    if not path.is_file():
        raise NotFoundError("Record not found.")
    return json.loads(path.read_text(encoding="utf-8"))


def dataset_dir(dataset_id):
    _checked_id(dataset_id, "Dataset")
    folder = _safe_child(DATASETS_DIR, dataset_id)
    if not folder.is_dir():
        raise NotFoundError("Dataset not found.")
    return folder


def dataset_csv_path(dataset_id):
    path = dataset_dir(dataset_id) / DATASET_FILE
    if not path.is_file():
        raise NotFoundError("Dataset not found.")
    return path


def dataset_split_path(dataset_id, split):
    if split not in SPLIT_FILES:
        raise NotFoundError("Dataset split not found.")
    path = dataset_dir(dataset_id) / split
    if not path.is_file():
        raise NotFoundError("Dataset split not found.")
    return path


def read_dataset_meta(dataset_id):
    return read_json(dataset_dir(dataset_id) / DATASET_META_FILE)


def save_upload(file_obj, filename, user_id=None):
    ensure_storage_dirs()
    original_name = _clean_filename(filename)
    extension = Path(original_name).suffix.lower()
    if extension not in limits.ALLOWED_EXTENSIONS:
        raise DataValidationError("Only .csv and .zip files are supported.")

    dataset_id = new_id()
    folder = _safe_child(DATASETS_DIR, dataset_id)
    folder.mkdir(parents=True)
    target = folder / DATASET_FILE
    total = 0

    try:
        if extension == ".csv":
            with open(target, "wb") as handle:
                while True:
                    chunk = file_obj.read(limits.UPLOAD_CHUNK_BYTES)
                    if not chunk:
                        break
                    total += len(chunk)
                    if total > limits.MAX_UPLOAD_BYTES:
                        raise PayloadTooLargeError(f"File is larger than {config.MAX_FILE_MB} MB.")
                    handle.write(chunk)
        else:
            archive_path = folder / "upload.zip"
            with open(archive_path, "wb") as handle:
                while True:
                    chunk = file_obj.read(limits.UPLOAD_CHUNK_BYTES)
                    if not chunk:
                        break
                    total += len(chunk)
                    if total > limits.MAX_UPLOAD_BYTES:
                        raise PayloadTooLargeError(f"File is larger than {config.MAX_FILE_MB} MB.")
                    handle.write(chunk)
            archive_format, split_names = _extract_archive(archive_path, folder)
            archive_path.unlink()
            if archive_format == "raw":
                shutil.copyfile(folder / split_names[0], folder / DATASET_FILE)
        if total == 0:
            raise DataValidationError("The file is empty.")
    except Exception:
        shutil.rmtree(folder, ignore_errors=True)
        raise

    meta = {
        "dataset_id": dataset_id,
        "original_name": original_name,
        "size_bytes": total,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "format": archive_format if extension == ".zip" else "raw",
        "user_id": user_id,
    }
    if extension == ".zip":
        meta["splits"] = split_names
    write_json(folder / DATASET_META_FILE, meta)
    return meta


def _extract_archive(archive_path, folder):
    aliases = {
        "train.csv": "train.csv",
        "training.csv": "train.csv",
        "test.csv": "test.csv",
        "testing.csv": "test.csv",
        "validation.csv": "validation.csv",
        "valid.csv": "validation.csv",
        "val.csv": "validation.csv",
        "dev.csv": "validation.csv",
    }
    try:
        with zipfile.ZipFile(archive_path) as archive:
            members = {}
            csv_members = []
            for info in archive.infolist():
                if info.is_dir():
                    continue
                name = Path(info.filename).name.lower()
                if not name.endswith(".csv"):
                    continue
                if info.file_size > limits.MAX_UPLOAD_BYTES:
                    raise PayloadTooLargeError(f"{name} is larger than {config.MAX_FILE_MB} MB.")
                csv_members.append(info)
                split_name = aliases.get(name)
                if split_name:
                    if split_name in members:
                        raise DataValidationError(f"ZIP contains duplicate {split_name} files.")
                    members[split_name] = info
            if not csv_members:
                raise DataValidationError("ZIP must contain at least one CSV file.")
            if len(csv_members) == 1:
                selected = csv_members[0]
                output_name = "raw.csv"
                members = {output_name: selected}
                archive_format = "raw"
            elif "train.csv" in members and "test.csv" in members:
                if "validation.csv" in members:
                    archive_format = "provided"
                    members = {name: members[name] for name in SPLIT_FILES}
                else:
                    archive_format = "train_test"
                    members = {name: members[name] for name in ("train.csv", "test.csv")}
            else:
                raise DataValidationError(
                    "ZIP splits could not be identified. Use train/test CSV names, or upload one CSV."
                )
            for name, info in members.items():
                output = folder / name
                with archive.open(info) as source, open(output, "wb") as target:
                    shutil.copyfileobj(source, target, limits.UPLOAD_CHUNK_BYTES)
            return archive_format, list(members)
    except zipfile.BadZipFile as exc:
        raise DataValidationError("The uploaded ZIP file is invalid.") from exc


def delete_dataset(dataset_id):
    if not is_valid_id(dataset_id):
        return
    folder = _safe_child(DATASETS_DIR, dataset_id)
    shutil.rmtree(folder, ignore_errors=True)


def job_path(job_id):
    _checked_id(job_id, "Job")
    return _safe_child(JOBS_DIR, f"{job_id}.json")


def save_job(job):
    ensure_storage_dirs()
    encoded = json.dumps(job, allow_nan=False)
    report_json = None
    model_id = job.get("model_id")
    if model_id and job.get("status") == "completed" and is_valid_id(model_id):
        report_path = MODELS_DIR / model_id / "report.json"
        if report_path.is_file():
            report_json = report_path.read_text(encoding="utf-8")
    with _db_connection() as connection:
        connection.execute(
            """INSERT INTO jobs(job_id,status,dataset_id,created_at,updated_at,payload_json,report_json)
            VALUES(?,?,?,?,?,?,?) ON CONFLICT(job_id) DO UPDATE SET
            status=excluded.status,dataset_id=excluded.dataset_id,updated_at=excluded.updated_at,
            payload_json=excluded.payload_json,report_json=COALESCE(excluded.report_json,jobs.report_json)""",
            (job["job_id"], job["status"], job["dataset_id"], job.get("created_at", ""), job.get("finished_at") or job.get("started_at") or job.get("created_at", ""), encoded, report_json),
        )
    write_json(job_path(job["job_id"]), job)


def load_job(job_id):
    ensure_storage_dirs()
    with _db_connection() as connection:
        row = connection.execute("SELECT payload_json FROM jobs WHERE job_id=?", (job_id,)).fetchone()
    if row:
        return json.loads(row["payload_json"])
    path = job_path(job_id)
    if not path.is_file():
        raise NotFoundError("Job not found.")
    return read_json(path)


def load_job_report(job_id):
    if not is_valid_id(job_id):
        raise NotFoundError("Job not found.")
    ensure_storage_dirs()
    with _db_connection() as connection:
        row = connection.execute("SELECT report_json FROM jobs WHERE job_id=?", (job_id,)).fetchone()
    if not row or not row["report_json"]:
        raise NotFoundError("Run results not found.")
    return json.loads(row["report_json"])


def list_jobs():
    ensure_storage_dirs()
    with _db_connection() as connection:
        rows = connection.execute("SELECT payload_json, report_json FROM jobs ORDER BY created_at DESC").fetchall()
    jobs = []
    for row in rows:
        try:
            job = json.loads(row["payload_json"])
            if row["report_json"]:
                job["_report"] = json.loads(row["report_json"])
            jobs.append(job)
        except (json.JSONDecodeError, TypeError):
            continue
    return jobs


def model_dir(model_id):
    _checked_id(model_id, "Model")
    folder = _safe_child(MODELS_DIR, model_id)
    if not folder.is_dir():
        raise NotFoundError("Model not found.")
    return folder


def model_file_path(model_id):
    path = model_dir(model_id) / MODEL_FILE
    if not path.is_file():
        raise NotFoundError("Model not found.")
    return path


def read_model_report(model_id):
    return read_json(model_dir(model_id) / "report.json")


def _is_expired(path, cutoff):
    try:
        return path.stat().st_mtime < cutoff
    except FileNotFoundError:
        return False


def cleanup_expired(max_age_hours=None):
    hours = limits.RETENTION_HOURS if max_age_hours is None else max_age_hours
    cutoff = time.time() - hours * 3600
    removed = {"datasets": 0, "jobs": 0, "models": 0}

    for folder, key in ((DATASETS_DIR, "datasets"), (MODELS_DIR, "models")):
        if not folder.is_dir():
            continue
        for item in folder.iterdir():
            if item.is_dir() and is_valid_id(item.name) and _is_expired(item, cutoff):
                shutil.rmtree(item, ignore_errors=True)
                removed[key] += 1

    if JOBS_DIR.is_dir():
        for item in JOBS_DIR.glob("*.json"):
            if is_valid_id(item.stem) and _is_expired(item, cutoff):
                item.unlink(missing_ok=True)
                removed["jobs"] += 1

    return removed
