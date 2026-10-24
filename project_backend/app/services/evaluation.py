import numpy as np
from sklearn.metrics import (
    accuracy_score,
    confusion_matrix,
    mean_absolute_error,
    mean_squared_error,
    precision_recall_fscore_support,
    r2_score,
    roc_auc_score,
    roc_curve,
)

from app.core import config

CV_SCORING = {
    "classification": "f1_weighted",
    "regression": "neg_root_mean_squared_error",
}

PRIMARY_METRIC = {
    "classification": "f1",
    "regression": "rmse",
}


def _check_task(task):
    if task not in config.SUPPORTED_TASKS:
        raise ValueError(f"Task must be one of {config.SUPPORTED_TASKS}.")


def classification_metrics(y_true, y_pred):
    y_true = np.asarray(y_true)
    y_pred = np.asarray(y_pred)
    labels = np.unique(np.concatenate([y_true, y_pred]))

    precision, recall, f1, _ = precision_recall_fscore_support(
        y_true, y_pred, average="weighted", zero_division=0
    )
    _, _, f1_macro, _ = precision_recall_fscore_support(
        y_true, y_pred, average="macro", zero_division=0
    )

    return {
        "accuracy": round(float(accuracy_score(y_true, y_pred)), 4),
        "precision": round(float(precision), 4),
        "recall": round(float(recall), 4),
        "f1": round(float(f1), 4),
        "f1_macro": round(float(f1_macro), 4),
        "labels": labels.tolist(),
        "confusion_matrix": confusion_matrix(y_true, y_pred, labels=labels).tolist(),
    }


def regression_metrics(y_true, y_pred):
    y_true = np.asarray(y_true, dtype=float)
    y_pred = np.asarray(y_pred, dtype=float)
    return {
        "mae": round(float(mean_absolute_error(y_true, y_pred)), 4),
        "rmse": round(float(np.sqrt(mean_squared_error(y_true, y_pred))), 4),
        "r2": round(float(r2_score(y_true, y_pred)), 4),
    }


def compute_metrics(task, y_true, y_pred):
    _check_task(task)
    if task == "classification":
        return classification_metrics(y_true, y_pred)
    return regression_metrics(y_true, y_pred)


def get_cv_scoring(task):
    _check_task(task)
    return CV_SCORING[task]


def normalize_cv_score(task, score):
    _check_task(task)
    value = float(score)
    return round(-value if task == "regression" else value, 4)


def is_higher_better(task):
    _check_task(task)
    return task == "classification"


def _downsample(xs, ys, n=48):
    xs = np.asarray(xs, dtype=float)
    ys = np.asarray(ys, dtype=float)
    if len(xs) <= n:
        return xs.tolist(), ys.tolist()
    idx = np.linspace(0, len(xs) - 1, n).astype(int)
    return xs[idx].tolist(), ys[idx].tolist()


def predict_scores(pipeline, X):
    if hasattr(pipeline, "predict_proba"):
        try:
            proba = pipeline.predict_proba(X)
            if getattr(proba, "ndim", 1) == 2 and proba.shape[1] == 2:
                return proba[:, 1]
            return proba
        except Exception:
            pass
    if hasattr(pipeline, "decision_function"):
        try:
            return pipeline.decision_function(X)
        except Exception:
            pass
    return None


def feature_importance(pipeline, limit=18):
    try:
        model = pipeline.named_steps["model"]
        preprocess = pipeline.named_steps["preprocess"]
        names = [str(name).replace("numeric__", "").replace("categorical__", "") for name in preprocess.get_feature_names_out()]
        if hasattr(model, "feature_importances_"):
            values = np.asarray(model.feature_importances_, dtype=float)
        elif hasattr(model, "coef_"):
            coef = np.asarray(model.coef_, dtype=float)
            values = np.abs(coef).mean(axis=0) if coef.ndim > 1 else np.abs(coef)
        else:
            return []
        items = [
            {"feature": names[index] if index < len(names) else f"f{index}", "importance": round(float(values[index]), 4)}
            for index in range(min(len(values), len(names) or len(values)))
        ]
        items.sort(key=lambda item: item["importance"], reverse=True)
        return items[:limit]
    except Exception:
        return []


def build_eval_charts(task, y_true, y_pred, y_score=None, pipeline=None):
    charts = {
        "leaderboard": [],
        "confusion_matrix": None,
        "roc": None,
        "residuals": None,
        "prediction_scatter": None,
        "feature_importance": feature_importance(pipeline) if pipeline is not None else [],
    }
    if y_true is None:
        return charts
    y_true = np.asarray(y_true)
    y_pred = np.asarray(y_pred)
    if task == "classification":
        metrics = classification_metrics(y_true, y_pred)
        charts["confusion_matrix"] = {"labels": [str(item) for item in metrics["labels"]], "matrix": metrics["confusion_matrix"]}
        if y_score is not None:
            try:
                classes = np.unique(y_true)
                scores = np.asarray(y_score)
                if len(classes) == 2:
                    positive = classes[-1]
                    y_bin = (y_true == positive).astype(int)
                    if scores.ndim > 1:
                        scores = scores[:, -1]
                    fpr, tpr, _ = roc_curve(y_bin, scores)
                    fpr, tpr = _downsample(fpr, tpr)
                    charts["roc"] = {
                        "fpr": [round(float(item), 4) for item in fpr],
                        "tpr": [round(float(item), 4) for item in tpr],
                        "auc": round(float(roc_auc_score(y_bin, scores)), 4),
                        "positive_label": str(positive),
                    }
            except Exception:
                charts["roc"] = None
    else:
        y_true_f = y_true.astype(float)
        y_pred_f = y_pred.astype(float)
        residuals = y_true_f - y_pred_f
        xs, ys = _downsample(y_pred_f, residuals, n=80)
        px, py = _downsample(y_true_f, y_pred_f, n=80)
        charts["residuals"] = {"predicted": [round(float(item), 4) for item in xs], "residual": [round(float(item), 4) for item in ys]}
        charts["prediction_scatter"] = {"actual": [round(float(item), 4) for item in px], "predicted": [round(float(item), 4) for item in py]}
    return charts