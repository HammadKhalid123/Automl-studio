from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class PredictRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    rows: list[dict[str, Any]] = Field(min_length=1)


class PredictResponse(BaseModel):
    model_id: str
    predictions: list[Any]
