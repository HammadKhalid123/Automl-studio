import json
import platform
import time
from datetime import datetime, timezone
from uuid import uuid4

import joblib
import numpy as np
import pandas as pd
import sklearn
from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
from sklearn.ensemble import GradientBoostingClassifier, GradientBoostingRegressor
from sklearn.neighbors import KNeighborsClassifier, KNeighborsRegressor
from sklearn.linear_model import LinearRegression, LogisticRegression
from sklearn.model_selection import KFold, StratifiedKFold, cross_val_score, train_test_split
from sklearn.svm import SVC, SVR
from sklearn.tree import DecisionTreeClassifier, DecisionTreeRegressor

from app.core import config
from app.services.data_profile import DataValidationError, split_column_types, validate_target
from app.services.evaluation import (
    build_eval_charts,
    compute_metrics,
    get_cv_scoring,
    is_higher_better,
    normalize_cv_score,
    predict_scores,
)

PARAM_KEYS = (
    "max_depth",
    "n_estimators",
    "n_neighbors",
    "max_iter",
    "C",
    "kernel",
    "random_state",
    "n_jobs",
)


def compact_params(estimator):
    raw = estimator.get_params(deep=False)
    params = {}
    for key in PARAM_KEYS:
        if key not in raw:
            continue
        value = raw[key]
        if isinstance(value, (str, int, float, bool)) or value is None:
            params[key] = value
    return params
from app.services.preprocessing import build_pipeline, build_preprocessor, resolve_options


def get_models(task):
    seed = config.RANDOM_SEED
    if task == "classification":
        return {
            "Logistic Regression": LogisticRegression(max_iter=1000, random_state=seed),
            "Decision Tree": DecisionTreeClassifier(max_depth=8, random_state=seed),
            "Random Forest": RandomForestClassifier(n_estimators=200, random_state=seed, n_jobs=-1),
            "Gradient Boosting": GradientBoostingClassifier(random_state=seed),
            "KNN": KNeighborsClassifier(n_neighbors=5),
            "SVM": SVC(),
        }
    if task == "regression":
        return {
            "Linear Regression": LinearRegression(),
            "Decision Tree": DecisionTreeRegressor(max_depth=8, random_state=seed),
            "Random Forest": RandomForestRegressor(n_estimators=200, random_state=seed, n_jobs=-1),
            "Gradient Boosting": GradientBoostingRegressor(random_state=seed),
            "KNN": KNeighborsRegressor(n_neighbors=5),
            "SVR": SVR(),
        }
    raise ValueError(f"Task must be one of {config.SUPPORTED_TASKS}.")


def split_data(df, target, task, exclude=()):
    X = df.drop(columns=[target, *exclude])
    y = df[target]
    stratify = None
    if task == "classification":
        counts = y.value_counts()
        n_test = int(round(len(df) * config.TEST_SIZE))
        if counts.min() >= 2 and n_test >= len(counts):
            stratify = y
    return train_test_split(
        X, y, test_size=config.TEST_SIZE, random_state=config.RANDOM_SEED, stratify=stratify
    )


def make_cv(task, y_train):
    if task == "classification":
        folds = min(config.CV_FOLDS, int(y_train.value_counts().min()))
        if folds < 2:
            raise DataValidationError("Not enough rows per class in the training data for cross-validation.")
        return StratifiedKFold(n_splits=folds, shuffle=True, random_state=config.RANDOM_SEED)
    folds = min(config.CV_FOLDS, len(y_train))
    return KFold(n_splits=folds, shuffle=True, random_state=config.RANDOM_SEED)


def compare_models(X_train, y_train, task, numeric_cols, categorical_cols, options=None, selected_models=None):
    cv = make_cv(task, y_train)
    scoring = get_cv_scoring(task)
    leaderboard = []

    models = get_models(task)
    if selected_models:
        unknown = [name for name in selected_models if name not in models]
        if unknown:
            raise DataValidationError(f"Unsupported models for {task}: {unknown}")
        models = {name: models[name] for name in selected_models}
    if not models:
        raise DataValidationError("Select at least one model.")
    for name, estimator in models.items():
        pipeline = build_pipeline(build_preprocessor(numeric_cols, categorical_cols, options), estimator)
        started = time.perf_counter()
        try:
            scores = cross_val_score(pipeline, X_train, y_train, cv=cv, scoring=scoring)
        except Exception as exc:
            leaderboard.append(
                {
                    "model": name,
                    "cv_mean": None,
                    "cv_std": None,
                    "seconds": None,
                    "error": str(exc),
                    "params": compact_params(estimator),
                }
            )
            continue
        leaderboard.append(
            {
                "model": name,
                "cv_mean": normalize_cv_score(task, scores.mean()),
                "cv_std": round(float(scores.std()), 4),
                "seconds": round(time.perf_counter() - started, 2),
                "error": None,
                "params": compact_params(estimator),
            }
        )

    ranked = [row for row in leaderboard if row["cv_mean"] is not None]
    if not ranked:
        raise RuntimeError("All models failed during cross-validation.")
    ranked.sort(key=lambda row: row["cv_mean"], reverse=is_higher_better(task))
    failed = [row for row in leaderboard if row["cv_mean"] is None]
    return ranked + failed, cv.get_n_splits()


def train_and_evaluate(df, target, task, exclude=(), options=None, selected_models=None):
    exclude = list(exclude)
    unknown = [name for name in exclude if name not in df.columns]
    if unknown:
        raise DataValidationError(f"Excluded columns not found: {unknown}")
    if target in exclude:
        raise DataValidationError("The target column cannot be excluded.")

    validate_target(df, target, task)
    options = resolve_options(options)
    numeric_cols, categorical_cols = split_column_types(df, target, exclude)

    X_train, X_test, y_train, y_test = split_data(df, target, task, exclude)
    leaderboard, cv_folds = compare_models(X_train, y_train, task, numeric_cols, categorical_cols, options, selected_models)

    best_name = leaderboard[0]["model"]
    pipeline = None
    available_models = get_models(task)
    for row in leaderboard:
        if row["cv_mean"] is None:
            continue
        candidate = build_pipeline(build_preprocessor(numeric_cols, categorical_cols, options), available_models[row["model"]])
        try:
            candidate.fit(X_train, y_train)
            row["evaluation_metrics"] = compute_metrics(task, y_test, candidate.predict(X_test))
            row["evaluation_split"] = "test"
            if row["model"] == best_name:
                pipeline = candidate
        except Exception as exc:
            row["evaluation_error"] = str(exc)
    if pipeline is None:
        raise RuntimeError("The selected best model could not be fitted for evaluation.")

    predictions = pipeline.predict(X_test)
    test_metrics = compute_metrics(task, y_test, predictions)
    charts = build_eval_charts(task, y_test, predictions, predict_scores(pipeline, X_test), pipeline)
    charts["leaderboard"] = [{"model": row["model"], "score": row["cv_mean"]} for row in leaderboard if row["cv_mean"] is not None]

    return {
        "pipeline": pipeline,
        "task": task,
        "target": target,
        "best_model": best_name,
        "leaderboard": leaderboard,
        "test_metrics": test_metrics,
        "charts": charts,
        "numeric_columns": numeric_cols,
        "categorical_columns": categorical_cols,
        "feature_columns": [*numeric_cols, *categorical_cols],
        "excluded_columns": exclude,
        "options": options,
        "random_seed": config.RANDOM_SEED,
        "test_size": config.TEST_SIZE,
        "cv_folds": cv_folds,
        "n_train": int(len(X_train)),
        "n_test": int(len(X_test)),
        "n_validation": 0,
        "split_mode": "random",
    }


def train_and_evaluate_splits(train_df, validation_df, test_df, target, task, exclude=(), options=None, selected_models=None):
    exclude = list(exclude)
    for frame_name, frame in (("train", train_df), ("validation", validation_df), ("test", test_df)):
        if target not in frame.columns:
            raise DataValidationError(f"Target column '{target}' was not found in {frame_name}.")
        validate_target(frame, target, task)

    if list(train_df.columns) != list(validation_df.columns) or list(train_df.columns) != list(test_df.columns):
        raise DataValidationError("Train, validation, and test columns must match in the same order.")
    unknown = [name for name in exclude if name not in train_df.columns]
    if unknown:
        raise DataValidationError(f"Excluded columns not found: {unknown}")
    if target in exclude:
        raise DataValidationError("The target column cannot be excluded.")

    options = resolve_options(options)
    numeric_cols, categorical_cols = split_column_types(train_df, target, exclude)
    X_train = train_df.drop(columns=[target, *exclude])
    y_train = train_df[target]
    X_validation = validation_df.drop(columns=[target, *exclude])
    y_validation = validation_df[target]
    X_test = test_df.drop(columns=[target, *exclude])
    y_test = test_df[target]
    leaderboard = []

    models = get_models(task)
    if selected_models:
        unknown = [name for name in selected_models if name not in models]
        if unknown:
            raise DataValidationError(f"Unsupported models for {task}: {unknown}")
        models = {name: models[name] for name in selected_models}
    if not models:
        raise DataValidationError("Select at least one model.")
    for name, estimator in models.items():
        pipeline = build_pipeline(build_preprocessor(numeric_cols, categorical_cols, options), estimator)
        started = time.perf_counter()
        try:
            pipeline.fit(X_train, y_train)
            validation_metrics = compute_metrics(task, y_validation, pipeline.predict(X_validation))
            evaluation_metrics = validation_metrics
            evaluation_split = "validation"
            if target in test_df.columns:
                evaluation_metrics = compute_metrics(task, y_test, pipeline.predict(X_test))
                evaluation_split = "test"
            score = validation_metrics["f1"] if task == "classification" else -validation_metrics["rmse"]
            leaderboard.append(
                {
                    "model": name,
                    "cv_mean": round(float(score if task == "classification" else -score), 4),
                    "cv_std": None,
                    "seconds": round(time.perf_counter() - started, 2),
                    "error": None,
                    "params": compact_params(estimator),
                    "evaluation_metrics": evaluation_metrics,
                    "evaluation_split": evaluation_split,
                }
            )
        except Exception as exc:
            leaderboard.append(
                {
                    "model": name,
                    "cv_mean": None,
                    "cv_std": None,
                    "seconds": None,
                    "error": str(exc),
                    "params": compact_params(estimator),
                    "evaluation_metrics": {},
                    "evaluation_split": None,
                    "evaluation_error": str(exc),
                }
            )

    ranked = [row for row in leaderboard if row["cv_mean"] is not None]
    if not ranked:
        raise RuntimeError("All models failed on the validation split.")
    ranked.sort(key=lambda row: row["cv_mean"], reverse=is_higher_better(task))
    failed = [row for row in leaderboard if row["cv_mean"] is None]
    best_name = ranked[0]["model"]
    best_pipeline = build_pipeline(
        build_preprocessor(numeric_cols, categorical_cols, options),
        get_models(task)[best_name],
    )
    best_pipeline.fit(X_train, y_train)
    test_pred = best_pipeline.predict(X_test)
    test_metrics = compute_metrics(task, y_test, test_pred)
    charts = build_eval_charts(task, y_test, test_pred, predict_scores(best_pipeline, X_test), best_pipeline)
    ranked_failed = ranked + failed
    charts["leaderboard"] = [{"model": row["model"], "score": row["cv_mean"]} for row in ranked_failed if row["cv_mean"] is not None]

    return {
        "pipeline": best_pipeline,
        "task": task,
        "target": target,
        "best_model": best_name,
        "leaderboard": ranked_failed,
        "test_metrics": test_metrics,
        "charts": charts,
        "numeric_columns": numeric_cols,
        "categorical_columns": categorical_cols,
        "feature_columns": [*numeric_cols, *categorical_cols],
        "excluded_columns": exclude,
        "options": options,
        "random_seed": config.RANDOM_SEED,
        "test_size": None,
        "cv_folds": 0,
        "n_train": int(len(train_df)),
        "n_test": int(len(test_df)),
        "n_validation": int(len(validation_df)),
        "split_mode": "provided",
    }


def train_and_evaluate_train_test(train_df, test_df, target, task, exclude=(), options=None, selected_models=None):
    exclude = list(exclude)
    if target not in train_df.columns:
        raise DataValidationError(f"Target column '{target}' was not found in train.csv.")
    validate_target(train_df, target, task)
    if target in test_df.columns:
        validate_target(test_df, target, task)
    train_features = [name for name in train_df.columns if name != target and name not in exclude]
    test_features = [name for name in test_df.columns if name != target and name not in exclude]
    if train_features != test_features:
        raise DataValidationError("Train and test feature columns must match in the same order.")
    unknown = [name for name in exclude if name not in train_df.columns]
    if unknown:
        raise DataValidationError(f"Excluded columns not found: {unknown}")
    if target in exclude:
        raise DataValidationError("The target column cannot be excluded.")

    options = resolve_options(options)
    numeric_cols, categorical_cols = split_column_types(train_df, target, exclude)
    X_train = train_df[train_features]
    y_train = train_df[target]
    leaderboard, cv_folds = compare_models(
        X_train,
        y_train,
        task,
        numeric_cols,
        categorical_cols,
        options,
        selected_models,
    )
    best_name = leaderboard[0]["model"]
    pipeline = None
    available_models = get_models(task)
    for row in leaderboard:
        if row["cv_mean"] is None:
            continue
        candidate = build_pipeline(build_preprocessor(numeric_cols, categorical_cols, options), available_models[row["model"]])
        try:
            candidate.fit(X_train, y_train)
            if target in test_df.columns:
                row["evaluation_metrics"] = compute_metrics(task, test_df[target], candidate.predict(test_df[test_features]))
                row["evaluation_split"] = "test"
            if row["model"] == best_name:
                pipeline = candidate
        except Exception as exc:
            row["evaluation_error"] = str(exc)
    if pipeline is None:
        raise RuntimeError("The selected best model could not be fitted for prediction.")
    predictions = pipeline.predict(test_df[test_features])
    if target in test_df.columns:
        test_metrics = compute_metrics(task, test_df[target], predictions)
        charts = build_eval_charts(
            task,
            test_df[target],
            predictions,
            predict_scores(pipeline, test_df[test_features]),
            pipeline,
        )
    else:
        test_metrics = {
            "status": "unscored",
            "reason": "This test.csv is an unlabeled prediction file. It has features only, so accuracy cannot be calculated. Add the true target column to test.csv for final scoring.",
        }
        charts = build_eval_charts(task, None, None, None, pipeline)
    charts["leaderboard"] = [{"model": row["model"], "score": row["cv_mean"]} for row in leaderboard if row["cv_mean"] is not None]

    return {
        "pipeline": pipeline,
        "task": task,
        "target": target,
        "best_model": best_name,
        "leaderboard": leaderboard,
        "test_metrics": test_metrics,
        "charts": charts,
        "numeric_columns": numeric_cols,
        "categorical_columns": categorical_cols,
        "feature_columns": [*numeric_cols, *categorical_cols],
        "excluded_columns": exclude,
        "options": options,
        "random_seed": config.RANDOM_SEED,
        "test_size": None,
        "cv_folds": cv_folds,
        "n_train": int(len(train_df)),
        "n_test": int(len(test_df)),
        "n_validation": 0,
        "split_mode": "train_test",
        "test_evaluation_available": target in test_df.columns,
    }


def save_artifacts(result):
    config.ensure_dirs()
    model_id = uuid4().hex[:12]
    folder = config.ARTIFACTS_DIR / model_id
    folder.mkdir(parents=True)

    joblib.dump(result["pipeline"], folder / "pipeline.joblib")

    report = {key: value for key, value in result.items() if key != "pipeline"}
    report["model_id"] = model_id
    report["created_at"] = datetime.now(timezone.utc).isoformat()
    report["versions"] = {
        "python": platform.python_version(),
        "scikit_learn": sklearn.__version__,
        "pandas": pd.__version__,
        "numpy": np.__version__,
    }
    (folder / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    return model_id, folder


def load_pipeline(model_id):
    path = config.ARTIFACTS_DIR / model_id / "pipeline.joblib"
    if not path.is_file():
        raise FileNotFoundError(f"No saved model with id '{model_id}'.")
    return joblib.load(path)


def load_report(model_id):
    path = config.ARTIFACTS_DIR / model_id / "report.json"
    if not path.is_file():
        raise FileNotFoundError(f"No report for model id '{model_id}'.")
    return json.loads(path.read_text(encoding="utf-8"))


def required_columns(pipeline):
    preprocessor = pipeline.named_steps["preprocess"]
    return [
        column
        for name, _, columns in preprocessor.transformers_
        if name != "remainder"
        for column in columns
    ]


def predict(pipeline, rows):
    frame = rows if isinstance(rows, pd.DataFrame) else pd.DataFrame(rows)
    needed = required_columns(pipeline)
    missing = [column for column in needed if column not in frame.columns]
    if missing:
        raise DataValidationError(f"Missing input columns: {missing}")
    return pipeline.predict(frame[needed]).tolist()
