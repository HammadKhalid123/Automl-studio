import logging
import shutil
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

import pandas as pd

from app.core import limits, storage
from app.services.data_profile import DataValidationError, load_csv, profile_dataframe
from app.services.training import (
    save_artifacts,
    train_and_evaluate,
    train_and_evaluate_splits,
    train_and_evaluate_train_test,
)

logger = logging.getLogger(__name__)

MAX_LOG_LINES = 50
TIMEOUT_MESSAGE = "The job exceeded the time limit."

_lock = threading.RLock()
_active = set()
_executor = ThreadPoolExecutor(max_workers=limits.MAX_CONCURRENT_JOBS, thread_name_prefix="trainer")


class JobBusyError(Exception):
    pass


def _now():
    return datetime.now(timezone.utc).isoformat()


def _log_line(message):
    return f"{datetime.now(timezone.utc).strftime('%H:%M:%S')} {message}"


def _update_job(job_id, log=None, **fields):
    with _lock:
        job = storage.load_job(job_id)
        job.update(fields)
        if log:
            job["logs"] = (job["logs"] + [_log_line(log)])[-MAX_LOG_LINES:]
        storage.save_job(job)
        return job


def _is_overdue(job):
    if job["status"] != "running" or not job.get("started_at"):
        return False
    started = datetime.fromisoformat(job["started_at"])
    return (datetime.now(timezone.utc) - started).total_seconds() > limits.JOB_TIMEOUT_SECONDS


def _fail_job(job_id, message):
    return _update_job(job_id, log=f"Failed: {message}", status="failed", stage="Failed", error=message, finished_at=_now())


def submit_job(request, user_id=None):
    meta = storage.read_dataset_meta(request.dataset_id)
    if meta.get("format") in ("provided", "train_test"):
        splits = storage.SPLIT_FILES if meta["format"] == "provided" else ("train.csv", "test.csv")
        for split in splits:
            storage.dataset_split_path(request.dataset_id, split)
    else:
        storage.dataset_csv_path(request.dataset_id)

    with _lock:
        if len(_active) >= limits.MAX_CONCURRENT_JOBS:
            raise JobBusyError("A training job is already running. Please try again when it finishes.")
        job_id = storage.new_id()
        job = {
            "job_id": job_id,
            "status": "queued",
            "progress": 0,
            "stage": "Queued",
            "dataset_id": request.dataset_id,
            "user_id": user_id,
            "task": request.task,
            "target": request.target,
            "created_at": _now(),
            "started_at": None,
            "finished_at": None,
            "model_id": None,
            "error": None,
            "logs": [_log_line("Job queued")],
            "options": request.options.model_dump() if hasattr(request.options, "model_dump") else dict(request.options),
            "selected_models": list(request.selected_models),
            "run_all": request.run_all,
            "exclude": list(request.exclude),
            "include": list(request.include),
            "exclude_flagged": request.exclude_flagged,
        }
        storage.save_job(job)
        _active.add(job_id)

    params = request.model_dump()
    params["user_id"] = user_id
    _executor.submit(_run_job, job_id, params)
    return job


def get_job(job_id):
    with _lock:
        job = storage.load_job(job_id)
        if _is_overdue(job):
            return _fail_job(job_id, TIMEOUT_MESSAGE)
        return job


def recover_interrupted_jobs():
    storage.ensure_storage_dirs()
    recovered = 0
    for path in storage.JOBS_DIR.glob("*.json"):
        if not storage.is_valid_id(path.stem):
            continue
        job = storage.load_job(path.stem)
        if job["status"] in ("queued", "running"):
            _fail_job(job["job_id"], "The server restarted before this job finished.")
            recovered += 1
    return recovered


def shutdown_runner():
    _executor.shutdown(wait=False, cancel_futures=True)


def _prepare_cleaning(frame, options):
    cleaned = frame.copy()
    for column, kind in options.get("column_types", {}).items():
        if column not in cleaned.columns:
            continue
        if kind == "numeric":
            cleaned[column] = pd.to_numeric(cleaned[column], errors="coerce")
        elif kind == "categorical":
            cleaned[column] = cleaned[column].astype("string")
    if options.get("remove_duplicates"):
        cleaned = cleaned.drop_duplicates().reset_index(drop=True)
    return cleaned


def _run_job(job_id, params):
    try:
        _update_job(job_id, log="Loading dataset", status="running", stage="Loading data", progress=5, started_at=_now())
        meta = storage.read_dataset_meta(params["dataset_id"])
        if meta.get("format") in ("provided", "train_test"):
            train_df = load_csv(storage.dataset_split_path(params["dataset_id"], "train.csv"))
            test_df = load_csv(storage.dataset_split_path(params["dataset_id"], "test.csv"))
            validation_df = (
                load_csv(storage.dataset_split_path(params["dataset_id"], "validation.csv"))
                if meta["format"] == "provided"
                else None
            )
            df = train_df
        else:
            df = load_csv(storage.dataset_csv_path(params["dataset_id"]))

        options = params.get("options") or {}
        if meta.get("format") in ("provided", "train_test"):
            train_df = _prepare_cleaning(train_df, options)
            test_df = _prepare_cleaning(test_df, options)
            if validation_df is not None:
                validation_df = _prepare_cleaning(validation_df, options)
            df = train_df
        else:
            df = _prepare_cleaning(df, options)

        include = set(params.get("include") or [])
        available_columns = set(df.columns)
        unknown_includes = sorted(include - available_columns)
        if unknown_includes:
            raise DataValidationError(f"Included columns not found: {unknown_includes}")
        exclude = [name for name in params["exclude"] if name not in include]
        if params["exclude_flagged"]:
            profile = profile_dataframe(df, params["target"])
            for names in profile["flagged"].values():
                exclude.extend(name for name in names if name not in exclude and name not in include)
        if exclude:
            _update_job(job_id, log=f"Excluding {len(exclude)} columns")

        _update_job(job_id, log="Comparing models with cross-validation", stage="Training", progress=20)
        if meta.get("format") == "provided":
            result = train_and_evaluate_splits(
                train_df,
                validation_df,
                test_df,
                params["target"],
                params["task"],
                exclude,
                params["options"],
                params["selected_models"] if not params["run_all"] else None,
            )

        elif meta.get("format") == "train_test":
            result = train_and_evaluate_train_test(
                train_df,
                test_df,
                params["target"],
                params["task"],
                exclude,
                params["options"],
                params["selected_models"] if not params["run_all"] else None,
            )
        else:
            result = train_and_evaluate(
                df,
                params["target"],
                params["task"],
                exclude,
                params["options"],
                params["selected_models"] if not params["run_all"] else None,
            )

        result["user_id"] = params.get("user_id")

        _update_job(job_id, log=f"Best model: {result['best_model']}", stage="Saving model", progress=90)
        model_id, folder = save_artifacts(result)

        with _lock:
            job = storage.load_job(job_id)
            if job["status"] == "failed":
                shutil.rmtree(folder, ignore_errors=True)
                return
            _update_job(
                job_id,
                log="Finished",
                status="completed",
                stage="Completed",
                progress=100,
                model_id=model_id,
                finished_at=_now(),
            )
    except (DataValidationError, storage.StorageError, RuntimeError) as exc:
        _fail_job(job_id, str(exc))
    except Exception:
        logger.exception("Training job %s failed unexpectedly", job_id)
        _fail_job(job_id, "Training failed unexpectedly.")
    finally:
        with _lock:
            _active.discard(job_id)
