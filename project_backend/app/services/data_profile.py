from pathlib import Path

import pandas as pd
from pandas.api.types import is_bool_dtype, is_integer_dtype, is_numeric_dtype
from pandas.api.types import is_categorical_dtype, is_string_dtype

from app.core import config


class DataValidationError(ValueError):
    pass


def _read_with_fallback(path):
    for encoding in ("utf-8", "latin-1"):
        try:
            return pd.read_csv(path, encoding=encoding)
        except UnicodeDecodeError:
            continue
        except pd.errors.EmptyDataError as exc:
            raise DataValidationError("The file is empty.") from exc
        except pd.errors.ParserError as exc:
            raise DataValidationError("The file could not be read as a valid CSV.") from exc
    raise DataValidationError("The file encoding is not supported.")


def load_csv(path):
    path = Path(path)
    if not path.is_file():
        raise DataValidationError(f"File not found: {path.name}")
    if path.suffix.lower() != ".csv":
        raise DataValidationError("Only .csv files are supported.")

    size_bytes = path.stat().st_size
    if size_bytes == 0:
        raise DataValidationError("The file is empty.")
    if size_bytes / (1024 * 1024) > config.MAX_FILE_MB:
        raise DataValidationError(f"File is larger than {config.MAX_FILE_MB} MB.")

    df = _read_with_fallback(path)
    df.columns = [str(name).strip() for name in df.columns]

    if any(name == "" for name in df.columns):
        raise DataValidationError("Every column must have a name.")
    if len(set(df.columns)) != len(df.columns):
        raise DataValidationError("Column names must be unique.")
    if df.shape[1] < config.MIN_COLUMNS:
        raise DataValidationError(f"At least {config.MIN_COLUMNS} columns are required.")
    if df.shape[1] > config.MAX_COLUMNS:
        raise DataValidationError(f"More than {config.MAX_COLUMNS} columns is not supported.")
    if df.shape[0] < config.MIN_ROWS:
        raise DataValidationError(f"At least {config.MIN_ROWS} rows are required.")
    if df.shape[0] > config.MAX_ROWS:
        raise DataValidationError(f"More than {config.MAX_ROWS:,} rows is not supported.")
    return df


def column_kind(series):
    if is_numeric_dtype(series) and not is_bool_dtype(series):
        return "numeric"
    return "categorical"


def column_display_kind(series):
    """More specific display grouping without changing model preprocessing kinds."""
    if is_numeric_dtype(series) and not is_bool_dtype(series):
        return "numeric"
    if is_bool_dtype(series) or is_categorical_dtype(series.dtype):
        return "categorical"
    if is_string_dtype(series.dtype) or series.dtype == object:
        return "categorical" if series.nunique(dropna=True) <= config.MAX_CATEGORIES else "string"
    return "categorical"


def _is_id_like(series):
    values = series.dropna()
    if values.empty:
        return False
    if values.nunique() / len(values) < config.ID_UNIQUE_RATIO:
        return False
    return is_integer_dtype(series) or not is_numeric_dtype(series)


def detect_flagged_columns(df, target=None):
    flagged = {"constant": [], "id_like": [], "high_cardinality": []}
    for name in df.columns:
        if name == target:
            continue
        series = df[name]
        unique = series.nunique(dropna=True)
        if unique <= 1:
            flagged["constant"].append(name)
        elif _is_id_like(series):
            flagged["id_like"].append(name)
        elif column_kind(series) == "categorical" and unique > config.MAX_CATEGORIES:
            flagged["high_cardinality"].append(name)
    return flagged


def profile_dataframe(df, target=None):
    flagged = detect_flagged_columns(df, target)
    columns = []
    for name in df.columns:
        series = df[name]
        columns.append(
            {
                "name": name,
                "kind": column_kind(series),
                "display_kind": column_display_kind(series),
                "dtype": str(series.dtype),
                "missing_pct": round(float(series.isna().mean() * 100), 2),
                "unique": int(series.nunique(dropna=True)),
            }
        )

    duplicate_rows = int(df.duplicated().sum())
    warnings = []

    if duplicate_rows:
        warnings.append(f"{duplicate_rows} duplicate rows found. They are kept unless you choose to remove them.")
    for column in columns:
        if column["missing_pct"] >= config.HIGH_MISSING_PCT:
            warnings.append(f"Column '{column['name']}' is {column['missing_pct']}% missing.")
    if flagged["constant"]:
        warnings.append(f"Constant columns carry no information: {flagged['constant']}")
    if flagged["id_like"]:
        warnings.append(f"ID-like columns are not useful for learning: {flagged['id_like']}")
    if flagged["high_cardinality"]:
        warnings.append(f"Columns with too many categories: {flagged['high_cardinality']}")

    return {
        "n_rows": int(df.shape[0]),
        "n_columns": int(df.shape[1]),
        "duplicate_rows": duplicate_rows,
        "missing_cells": int(df.isna().sum().sum()),
        "columns": columns,
        "flagged": flagged,
        "warnings": warnings,
    }


def validate_target(df, target, task):
    if task not in config.SUPPORTED_TASKS:
        raise DataValidationError(f"Task must be one of {config.SUPPORTED_TASKS}.")
    if target not in df.columns:
        raise DataValidationError(f"Target column '{target}' was not found.")

    series = df[target]
    if series.isna().any():
        raise DataValidationError(
            f"Target column '{target}' has {int(series.isna().sum())} missing values. Fix or remove those rows first."
        )

    if task == "classification":
        counts = series.value_counts()
        if len(counts) < 2:
            raise DataValidationError("Classification needs at least 2 classes in the target.")
        if len(counts) > config.MAX_CLASSES:
            raise DataValidationError(
                f"Target has {len(counts)} classes. Use regression or pick a different target."
            )
        if counts.min() < config.MIN_CLASS_COUNT:
            raise DataValidationError(
                f"Every class needs at least {config.MIN_CLASS_COUNT} rows. Smallest class has {int(counts.min())}."
            )
    else:
        if column_kind(series) != "numeric":
            raise DataValidationError("Regression needs a numeric target column.")
        if series.nunique() < 3:
            raise DataValidationError("Target has too few distinct values for regression.")


def split_column_types(df, target, exclude=()):
    features = [name for name in df.columns if name != target and name not in set(exclude)]
    if not features:
        raise DataValidationError("No input columns left after exclusions.")
    numeric = [name for name in features if column_kind(df[name]) == "numeric"]
    categorical = [name for name in features if column_kind(df[name]) == "categorical"]
    return numeric, categorical
