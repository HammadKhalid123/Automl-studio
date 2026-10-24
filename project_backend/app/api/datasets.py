from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Path, Query, UploadFile, status

from app.core import limits, storage
from app.core.debuglog import agent_log
from app.schemas.dataset import DatasetProfileResponse, DatasetResponse
from app.services.charts import dataset_charts
from app.services.data_profile import DataValidationError, load_csv, profile_dataframe
from app.core.auth import get_current_user
from app.db.models import User

router = APIRouter(prefix="/datasets", tags=["datasets"])


def _owned_meta(dataset_id, user):
    meta = storage.read_dataset_meta(dataset_id)
    if meta.get("user_id") != user.id:
        raise HTTPException(status_code=404, detail="Dataset not found.")
    return meta


def _profile_response(dataset_id):
    meta = storage.read_dataset_meta(dataset_id)
    path = storage.dataset_split_path(dataset_id, "train.csv") if meta.get("format") in ("provided", "train_test") else storage.dataset_csv_path(dataset_id)
    profile = profile_dataframe(load_csv(path))
    return {
        **{key: value for key, value in meta.items() if key != "user_id"},
        "profile": profile,
    }


@router.post("", response_model=DatasetResponse, status_code=status.HTTP_201_CREATED)
def upload_dataset(file: UploadFile, user: User = Depends(get_current_user)):
    try:
        meta = storage.save_upload(file.file, file.filename or "", user_id=user.id)
        path = storage.dataset_split_path(meta["dataset_id"], "train.csv") if meta.get("format") in ("provided", "train_test") else storage.dataset_csv_path(meta["dataset_id"])
        dataframe = load_csv(path)
        if meta.get("format") in ("provided", "train_test"):
            columns = list(dataframe.columns)
            required_splits = ("validation.csv", "test.csv") if meta["format"] == "provided" else ("test.csv",)
            for split in required_splits:
                split_frame = load_csv(storage.dataset_split_path(meta["dataset_id"], split))
                split_columns = list(split_frame.columns)
                valid_columns = split_columns == columns or (
                    split == "test.csv"
                    and set(split_columns).issubset(columns)
                    and len(split_columns) >= 1
                )
                if not valid_columns:
                    raise DataValidationError("Train, validation, and test columns must match in the same order.")
        response = {
            **{key: value for key, value in meta.items() if key != "user_id"},
            "profile": profile_dataframe(dataframe),
            "preview": dataframe.head(5).where(dataframe.head(5).notna(), None).to_dict(orient="records"),
        }
        return response
    except storage.PayloadTooLargeError as exc:
        if "meta" in locals():
            storage.delete_dataset(meta["dataset_id"])
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail=str(exc)) from exc
    except DataValidationError as exc:
        if "meta" in locals():
            storage.delete_dataset(meta["dataset_id"])
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get("/{dataset_id}/charts")
def get_dataset_charts(
    dataset_id: str = Path(pattern=f"^{limits.ID_PATTERN}$"),
    target: str | None = Query(default=None),
    numeric_impute: Literal["median", "mean", "most_frequent", "constant"] = Query(default="median"),
    categorical_impute: Literal["most_frequent", "constant"] = Query(default="most_frequent"),
    user: User = Depends(get_current_user),
):
    try:
        meta = _owned_meta(dataset_id, user)
        path = storage.dataset_split_path(dataset_id, "train.csv") if meta.get("format") in ("provided", "train_test") else storage.dataset_csv_path(dataset_id)
        payload = dataset_charts(load_csv(path), target=target, numeric_impute=numeric_impute, categorical_impute=categorical_impute)
        payload["dataset_id"] = dataset_id
        # #region agent log
        explore = payload.get("explore") or {}
        clean = payload.get("clean") or {}
        agent_log(
            "B",
            "datasets.py:get_dataset_charts",
            "Built dataset charts",
            {
                "dataset_id": dataset_id,
                "histograms": len(explore.get("histograms") or []),
                "categories": len(explore.get("categories") or []),
                "missing": len(explore.get("missing") or []),
                "clean_missing": len(clean.get("missing_before_after") or []),
                "has_target": bool(explore.get("target")),
            },
        )
        # #endregion
        return payload
    except (storage.NotFoundError, DataValidationError) as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.get(
    "/{dataset_id}/profile",
    response_model=DatasetProfileResponse,
)
def get_dataset_profile(
    dataset_id: str = Path(pattern=f"^{limits.ID_PATTERN}$"),
    user: User = Depends(get_current_user),
):
    try:
        _owned_meta(dataset_id, user)
        return _profile_response(dataset_id)
    except (storage.NotFoundError, DataValidationError) as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

