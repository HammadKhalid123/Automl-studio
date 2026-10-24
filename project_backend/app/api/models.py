from fastapi import APIRouter, Depends, HTTPException, Path, status
from fastapi.responses import FileResponse

from app.core import limits, storage
from app.schemas.model import PredictRequest, PredictResponse
from app.services.data_profile import DataValidationError
from app.services.training import load_pipeline, predict
from app.core.auth import get_current_user
from app.db.models import User

router = APIRouter(prefix="/models", tags=["models"])


def _owned_model(model_id, user):
    report = storage.read_model_report(model_id)
    if report.get("user_id") != user.id:
        raise HTTPException(status_code=404, detail="Model not found.")
    return report


@router.get("/{model_id}/download")
def download_model(model_id: str = Path(pattern=f"^{limits.ID_PATTERN}$"), user: User = Depends(get_current_user)):
    try:
        _owned_model(model_id, user)
        path = storage.model_file_path(model_id)
        return FileResponse(path, filename="pipeline.joblib", media_type="application/octet-stream")
    except storage.NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post("/{model_id}/predict", response_model=PredictResponse)
def predict_model(
    request: PredictRequest,
    model_id: str = Path(pattern=f"^{limits.ID_PATTERN}$"),
    user: User = Depends(get_current_user),
):
    if len(request.rows) > limits.MAX_PREDICT_ROWS:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"At most {limits.MAX_PREDICT_ROWS} rows can be predicted at once.",
        )
    try:
        _owned_model(model_id, user)
        predictions = predict(load_pipeline(model_id), request.rows)
        return {"model_id": model_id, "predictions": predictions}
    except (FileNotFoundError, storage.NotFoundError) as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Model not found.") from exc
    except DataValidationError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
