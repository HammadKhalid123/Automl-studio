import numpy as np
import pandas as pd

from app.services.data_profile import column_display_kind, column_kind


def _safe_float(value):
    if value is None or (isinstance(value, float) and (np.isnan(value) or np.isinf(value))):
        return 0.0
    return round(float(value), 4)


def _histogram(series, bins=12):
    values = pd.to_numeric(series.dropna(), errors="coerce").dropna()
    if values.empty:
        return {"bins": [], "counts": []}
    counts, edges = np.histogram(values.to_numpy(dtype=float), bins=min(bins, max(len(values), 1)))
    labels = [f"{_safe_float(edges[i])}–{_safe_float(edges[i + 1])}" for i in range(len(counts))]
    return {
        "bins": labels,
        "counts": [int(item) for item in counts],
        "min": _safe_float(values.min()),
        "max": _safe_float(values.max()),
    }


def _histogram_pair(before, after, bins=12):
    before_values = pd.to_numeric(before.dropna(), errors="coerce").dropna().to_numpy(dtype=float)
    after_values = pd.to_numeric(after.dropna(), errors="coerce").dropna().to_numpy(dtype=float)
    combined = np.concatenate((before_values, after_values))
    if not len(combined):
        return {"bins": [], "before": [], "after": []}
    minimum, maximum = float(combined.min()), float(combined.max())
    if minimum == maximum:
        minimum, maximum = minimum - 0.5, maximum + 0.5
    edges = np.linspace(minimum, maximum, min(bins, max(len(combined), 1)) + 1)
    labels = [f"{_safe_float(edges[i])}–{_safe_float(edges[i + 1])}" for i in range(len(edges) - 1)]
    return {
        "bins": labels,
        "before": [int(x) for x in np.histogram(before_values, bins=edges)[0]],
        "after": [int(x) for x in np.histogram(after_values, bins=edges)[0]],
    }


def _value_counts(series, top=8):
    all_counts = series.fillna("(missing)").astype(str).value_counts()
    counts = all_counts.head(top)
    items = [{"label": str(index)[:40], "value": int(value)} for index, value in counts.items()]
    other = int(all_counts.iloc[top:].sum())
    if other:
        items.append({"label": "Other", "value": other})
    return items


def dataset_charts(df, target=None, numeric_impute="median", categorical_impute="most_frequent"):
    numeric_cols = [name for name in df.columns if column_kind(df[name]) == "numeric"]
    categorical_cols = [name for name in df.columns if column_kind(df[name]) == "categorical"]
    display_categories = [name for name in df.columns if column_display_kind(df[name]) == "categorical"]
    string_cols = [name for name in df.columns if column_display_kind(df[name]) == "string"]
    missing = [
        {
            "name": name,
            "missing_pct": _safe_float(df[name].isna().mean() * 100),
            "missing_count": int(df[name].isna().sum()),
        }
        for name in df.columns
    ]
    kinds = [
        {"label": "Numeric", "value": len(numeric_cols)},
        {"label": "Categorical", "value": len(categorical_cols)},
    ]
    histograms = [{"name": name, **_histogram(df[name])} for name in numeric_cols[:6]]
    categories = [{"name": name, "counts": _value_counts(df[name])} for name in display_categories[:8]]
    strings = [{"name": name, "counts": _value_counts(df[name], top=10)} for name in string_cols[:8]]
    numeric_summaries = []
    for name in numeric_cols[:8]:
        values = pd.to_numeric(df[name], errors="coerce").dropna()
        if not values.empty:
            numeric_summaries.append({
                "name": name,
                "min": _safe_float(values.min()),
                "q1": _safe_float(values.quantile(.25)),
                "median": _safe_float(values.median()),
                "q3": _safe_float(values.quantile(.75)),
                "max": _safe_float(values.max()),
                "mean": _safe_float(values.mean()),
            })
    numeric_correlations = []
    corr_cols = numeric_cols[:8]
    if len(corr_cols) > 1:
        corr = df[corr_cols].corr(numeric_only=True).fillna(0)
        numeric_correlations = [{"x": row, "y": col, "value": _safe_float(corr.loc[row, col])} for row in corr_cols for col in corr_cols]
    target_chart = None
    if target and target in df.columns:
        series = df[target]
        if column_kind(series) == "numeric":
            target_chart = {"kind": "numeric", "name": target, **_histogram(series)}
        else:
            target_chart = {"kind": "categorical", "name": target, "counts": _value_counts(series, top=12)}

    after = df.copy()
    for name in numeric_cols:
        if numeric_impute == "median":
            fill = after[name].median()
        elif numeric_impute == "mean":
            fill = after[name].mean()
        elif numeric_impute == "most_frequent":
            mode = after[name].mode(dropna=True)
            fill = mode.iloc[0] if not mode.empty else 0
        else:
            fill = 0
        after[name] = after[name].fillna(fill)
    for name in categorical_cols:
        mode = after[name].mode(dropna=True)
        fill = (mode.iloc[0] if not mode.empty else "(missing)") if categorical_impute == "most_frequent" else "Missing"
        after[name] = after[name].fillna(fill)

    missing_after = [
        {
            "name": name,
            "before": _safe_float(df[name].isna().mean() * 100),
            "after": _safe_float(after[name].isna().mean() * 100),
        }
        for name in df.columns
        if df[name].isna().any()
    ]
    after_histograms = [
        {"name": name, **_histogram_pair(df[name], after[name])}
        for name in numeric_cols[:4]
        if df[name].isna().any()
    ]

    return {
        "explore": {
            "missing": missing,
            "kinds": kinds,
            "histograms": histograms,
            "categories": categories,
            "strings": strings,
            "numeric_summaries": numeric_summaries,
            "numeric_correlations": numeric_correlations,
            "target": target_chart,
            "duplicates": int(df.duplicated().sum()),
            "n_rows": int(len(df)),
        },
        "clean": {
            "missing_before_after": missing_after,
            "histograms_before_after": after_histograms,
            "numeric_impute": numeric_impute,
            "duplicate_rows": int(df.duplicated().sum()),
        },
    }
