from typing import Any

from pydantic import BaseModel, ConfigDict


class DatasetColumn(BaseModel):
    name: str
    kind: str
    display_kind: str = "categorical"
    dtype: str
    missing_pct: float
    unique: int


class DatasetProfile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    n_rows: int
    n_columns: int
    duplicate_rows: int
    missing_cells: int
    columns: list[DatasetColumn]
    flagged: dict[str, list[str]]
    warnings: list[str]


class DatasetResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    dataset_id: str
    original_name: str
    size_bytes: int
    created_at: str
    profile: DatasetProfile
    preview: list[dict[str, Any]]
    format: str
    splits: list[str] | None = None


class DatasetProfileResponse(BaseModel):
    dataset_id: str
    original_name: str
    size_bytes: int
    created_at: str
    profile: DatasetProfile
    format: str
    splits: list[str] | None = None
