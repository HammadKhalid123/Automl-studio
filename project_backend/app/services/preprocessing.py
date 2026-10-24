import numpy as np
from sklearn.base import BaseEstimator, TransformerMixin
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import MinMaxScaler, OneHotEncoder, RobustScaler, StandardScaler

DEFAULT_OPTIONS = {
    "numeric_impute": "median",
    "categorical_impute": "most_frequent",
    "scaling": "standard",
    "numeric_fill_value": 0,
    "categorical_fill_value": "Missing",
    "outlier_method": "none",
    "remove_duplicates": False,
    "column_types": {},
}

NUMERIC_IMPUTE_CHOICES = ("median", "mean", "most_frequent", "constant")
CATEGORICAL_IMPUTE_CHOICES = ("most_frequent", "constant")
SCALER_CHOICES = {
    "standard": StandardScaler,
    "minmax": MinMaxScaler,
    "robust": RobustScaler,
    "none": None,
}


class IQRClipper(BaseEstimator, TransformerMixin):
    """Learn IQR fences during fit and clip numeric values during transform."""

    def fit(self, X, y=None):
        values = np.asarray(X, dtype=float)
        q1, q3 = np.nanpercentile(values, [25, 75], axis=0)
        spread = q3 - q1
        self.lower_ = q1 - 1.5 * spread
        self.upper_ = q3 + 1.5 * spread
        return self

    def transform(self, X):
        return np.clip(np.asarray(X, dtype=float), self.lower_, self.upper_)


def resolve_options(options=None):
    resolved = {**DEFAULT_OPTIONS, **(options or {})}
    unknown = set(resolved) - set(DEFAULT_OPTIONS)
    if unknown:
        raise ValueError(f"Unknown preprocessing options: {sorted(unknown)}")
    if resolved["numeric_impute"] not in NUMERIC_IMPUTE_CHOICES:
        raise ValueError(f"numeric_impute must be one of {NUMERIC_IMPUTE_CHOICES}.")
    if resolved["categorical_impute"] not in CATEGORICAL_IMPUTE_CHOICES:
        raise ValueError(f"categorical_impute must be one of {CATEGORICAL_IMPUTE_CHOICES}.")
    if resolved["scaling"] not in SCALER_CHOICES:
        raise ValueError(f"scaling must be one of {tuple(SCALER_CHOICES)}.")
    if resolved["outlier_method"] not in ("none", "iqr_clip"):
        raise ValueError("outlier_method must be 'none' or 'iqr_clip'.")
    if not isinstance(resolved["remove_duplicates"], bool):
        raise ValueError("remove_duplicates must be a boolean.")
    if not isinstance(resolved["column_types"], dict):
        raise ValueError("column_types must be a mapping of column names to numeric or categorical.")
    return resolved


def build_preprocessor(numeric_cols, categorical_cols, options=None):
    if not numeric_cols and not categorical_cols:
        raise ValueError("At least one input column is required.")

    opts = resolve_options(options)
    transformers = []

    if numeric_cols:
        imputer_options = {"strategy": opts["numeric_impute"]}
        if opts["numeric_impute"] == "constant":
            imputer_options["fill_value"] = opts["numeric_fill_value"]
        steps = [("imputer", SimpleImputer(**imputer_options))]
        if opts["outlier_method"] == "iqr_clip":
            steps.append(("outlier_clip", IQRClipper()))
        scaler_class = SCALER_CHOICES[opts["scaling"]]
        if scaler_class is not None:
            steps.append(("scaler", scaler_class()))
        transformers.append(("numeric", Pipeline(steps), list(numeric_cols)))

    if categorical_cols:
        imputer_options = {"strategy": opts["categorical_impute"]}
        if opts["categorical_impute"] == "constant":
            imputer_options["fill_value"] = opts["categorical_fill_value"]
        steps = [
            ("imputer", SimpleImputer(**imputer_options)),
            ("encoder", OneHotEncoder(handle_unknown="ignore", sparse_output=False)),
        ]
        transformers.append(("categorical", Pipeline(steps), list(categorical_cols)))

    return ColumnTransformer(transformers=transformers, remainder="drop")


def build_pipeline(preprocessor, estimator):
    return Pipeline([("preprocess", preprocessor), ("model", estimator)])
