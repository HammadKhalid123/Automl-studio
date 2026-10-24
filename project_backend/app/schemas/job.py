from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

from app.core import config, limits

JobStatus = Literal["queued", "running", "completed", "failed"]


class PreprocessingOptions(BaseModel):
    model_config = ConfigDict(extra="forbid")

    numeric_impute: Literal["median", "mean", "most_frequent", "constant"] = "median"
    categorical_impute: Literal["most_frequent", "constant"] = "most_frequent"
    scaling: Literal["standard", "minmax", "robust", "none"] = "standard"
    numeric_fill_value: float = 0
    categorical_fill_value: str = "Missing"
    outlier_method: Literal["none", "iqr_clip"] = "none"
    remove_duplicates: bool = False
    column_types: dict[str, Literal["numeric", "categorical"]] = Field(default_factory=dict, max_length=config.MAX_COLUMNS)


class JobRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    dataset_id: str = Field(pattern=f"^{limits.ID_PATTERN}$")
    target: str = Field(min_length=1, max_length=200)
    task: Literal["classification", "regression"]
    exclude: list[str] = Field(default_factory=list, max_length=config.MAX_COLUMNS)
    include: list[str] = Field(default_factory=list, max_length=config.MAX_COLUMNS)
    exclude_flagged: bool = False
    selected_models: list[str] = Field(default_factory=list, max_length=20)
    run_all: bool = True
    options: PreprocessingOptions = Field(default_factory=PreprocessingOptions)


class JobResponse(BaseModel):
    job_id: str
    status: JobStatus
    progress: int = Field(ge=0, le=100)
    stage: str
    dataset_id: str
    task: str
    target: str
    created_at: str
    started_at: Optional[str] = None
    finished_at: Optional[str] = None
    model_id: Optional[str] = None
    error: Optional[str] = None
    logs: list[str] = Field(default_factory=list)
    options: Optional[dict] = None
    selected_models: list[str] = Field(default_factory=list)
    run_all: Optional[bool] = None
    exclude: list[str] = Field(default_factory=list)
    include: list[str] = Field(default_factory=list)
    exclude_flagged: Optional[bool] = None


class LeaderboardRow(BaseModel):
    model: str
    cv_mean: Optional[float] = None
    cv_std: Optional[float] = None
    seconds: Optional[float] = None
    error: Optional[str] = None
    params: dict = Field(default_factory=dict)
    evaluation_metrics: dict = Field(default_factory=dict)
    evaluation_split: Optional[str] = None
    evaluation_error: Optional[str] = None


class JobResultsResponse(BaseModel):
    model_id: str
    task: str
    target: str
    best_model: str
    leaderboard: list[LeaderboardRow]
    test_metrics: dict
    numeric_columns: list[str]
    categorical_columns: list[str]
    feature_columns: list[str] = Field(default_factory=list)
    excluded_columns: list[str]
    options: dict
    cv_folds: int
    n_train: int
    n_test: int
    n_validation: int = 0
    split_mode: str = "random"
    test_evaluation_available: bool = True
    random_seed: int
    created_at: str
    versions: dict
    charts: dict = Field(default_factory=dict)


class JobHistoryItem(BaseModel):
    job_id: str
    status: JobStatus
    dataset_id: str
    task: str
    target: str
    feature_columns: list[str] = Field(default_factory=list)
    excluded_columns: list[str] = Field(default_factory=list)
    created_at: str
    finished_at: Optional[str] = None
    model_id: Optional[str] = None
    error: Optional[str] = None
    best_model: Optional[str] = None
    metrics: dict = Field(default_factory=dict)
    options: dict = Field(default_factory=dict)
    params: dict = Field(default_factory=dict)
    leaderboard: list[LeaderboardRow] = Field(default_factory=list)
    cv_folds: Optional[int] = None
    n_train: Optional[int] = None
    n_test: Optional[int] = None
