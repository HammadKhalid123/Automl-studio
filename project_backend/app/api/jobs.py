from fastapi import APIRouter, Depends, HTTPException, Path, status

from app.core import limits, storage
from app.core.debuglog import agent_log
from app.schemas.job import JobHistoryItem, JobRequest, JobResponse, JobResultsResponse
from app.services import job_runner
from app.core.auth import get_current_user
from app.db.models import User

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.post("", response_model=JobResponse, status_code=status.HTTP_202_ACCEPTED)
def create_job(request: JobRequest, user: User = Depends(get_current_user)):
    try:
        meta = storage.read_dataset_meta(request.dataset_id)
        if meta.get("user_id") != user.id:
            raise HTTPException(status_code=404, detail="Dataset not found.")
        return job_runner.submit_job(request, user_id=user.id)
    except HTTPException:
        raise
    except job_runner.JobBusyError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except (storage.NotFoundError, storage.StorageError) as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.get("", response_model=list[JobHistoryItem])
def list_jobs(user: User = Depends(get_current_user)):
    history = []
    for job in storage.list_jobs():
        if job.get("user_id") != user.id:
            continue
        report = job.pop("_report", None)
        item = {
            "job_id": job.get("job_id"),
            "status": job.get("status"),
            "dataset_id": job.get("dataset_id"),
            "task": job.get("task"),
            "target": job.get("target"),
            "feature_columns": [],
            "excluded_columns": [],
            "created_at": job.get("created_at"),
            "finished_at": job.get("finished_at"),
            "model_id": job.get("model_id"),
            "error": job.get("error"),
            "options": job.get("options") or {},
            "params": {},
            "metrics": {},
            "leaderboard": [],
        }
        model_id = job.get("model_id")
        if report is not None:
            item["best_model"] = report.get("best_model")
            item["metrics"] = {
                key: value
                for key, value in (report.get("test_metrics") or {}).items()
                if key not in ("labels", "confusion_matrix", "status", "reason")
            }
            item["options"] = report.get("options") or item["options"]
            item["excluded_columns"] = report.get("excluded_columns") or []
            item["feature_columns"] = report.get("feature_columns") or [*(report.get("numeric_columns") or []), *(report.get("categorical_columns") or [])]
            item["leaderboard"] = report.get("leaderboard") or []
            item["cv_folds"] = report.get("cv_folds")
            item["n_train"] = report.get("n_train")
            item["n_test"] = report.get("n_test")
            best = next((row for row in item["leaderboard"] if row.get("model") == item["best_model"]), None)
            item["params"] = (best or {}).get("params") or {}
        elif job.get("status") == "completed" and model_id:
            try:
                report = storage.read_json(storage.model_dir(model_id) / "report.json")
                item["best_model"] = report.get("best_model")
                item["metrics"] = {
                    key: value
                    for key, value in (report.get("test_metrics") or {}).items()
                    if key not in ("labels", "confusion_matrix", "status", "reason")
                }
                item["options"] = report.get("options") or item["options"]
                item["excluded_columns"] = report.get("excluded_columns") or []
                item["feature_columns"] = report.get("feature_columns") or [*(report.get("numeric_columns") or []), *(report.get("categorical_columns") or [])]
                item["leaderboard"] = report.get("leaderboard") or []
                item["cv_folds"] = report.get("cv_folds")
                item["n_train"] = report.get("n_train")
                item["n_test"] = report.get("n_test")
                best = next((row for row in item["leaderboard"] if row.get("model") == item["best_model"]), None)
                item["params"] = (best or {}).get("params") or {}
            except storage.NotFoundError:
                pass
        history.append(item)
    # #region agent log
    agent_log("D", "jobs.py:list_jobs", "Listed run history", {"count": len(history), "completed": sum(1 for item in history if item.get("status") == "completed")})
    # #endregion
    return history


@router.get("/{job_id}", response_model=JobResponse)
def get_job(job_id: str = Path(pattern=f"^{limits.ID_PATTERN}$"), user: User = Depends(get_current_user)):
    try:
        job = job_runner.get_job(job_id)
        if job.get("user_id") != user.id:
            raise HTTPException(status_code=404, detail="Job not found.")
        return job
    except HTTPException:
        raise
    except storage.NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.get("/{job_id}/results", response_model=JobResultsResponse)
def get_job_results(job_id: str = Path(pattern=f"^{limits.ID_PATTERN}$"), user: User = Depends(get_current_user)):
    try:
        job = job_runner.get_job(job_id)
        if job.get("user_id") != user.id:
            raise HTTPException(status_code=404, detail="Job not found.")
        if job["status"] != "completed" or not job.get("model_id"):
            if job["status"] == "failed":
                raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=job["error"])
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Job has not completed.")
        try:
            report = job_runner.storage.load_job_report(job_id)
        except storage.NotFoundError:
            report = job_runner.storage.read_json(
                job_runner.storage.model_dir(job["model_id"]) / "report.json"
            )
        if report.get("user_id") != user.id:
            raise HTTPException(status_code=404, detail="Results not found.")
        # #region agent log
        charts = report.get("charts") or {}
        agent_log(
            "C",
            "jobs.py:get_job_results",
            "Returning job results",
            {
                "model_id": job.get("model_id"),
                "has_charts": bool(charts),
                "chart_keys": list(charts),
                "has_confusion": bool(charts.get("confusion_matrix") or (report.get("test_metrics") or {}).get("confusion_matrix")),
                "leaderboard_params": [bool(row.get("params")) for row in report.get("leaderboard") or []],
            },
        )
        # #endregion
        return report
    except HTTPException:
        raise
    except storage.NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
