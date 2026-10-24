import argparse
import sys

from app.core import config
from app.services.data_profile import DataValidationError, load_csv, profile_dataframe
from app.services.preprocessing import SCALER_CHOICES
from app.services.training import (
    load_pipeline,
    predict,
    required_columns,
    save_artifacts,
    train_and_evaluate,
)


def parse_args():
    parser = argparse.ArgumentParser(description="Train and compare models on a CSV file.")
    parser.add_argument("--csv", required=True)
    parser.add_argument("--target", required=True)
    parser.add_argument("--task", required=True, choices=config.SUPPORTED_TASKS)
    parser.add_argument("--exclude", nargs="*", default=[])
    parser.add_argument("--exclude-flagged", action="store_true")
    parser.add_argument("--scaling", default="standard", choices=tuple(SCALER_CHOICES))
    parser.add_argument("--numeric-impute", default="median", choices=("median", "mean"))
    return parser.parse_args()


def print_profile(profile):
    print(f"Rows: {profile['n_rows']}  Columns: {profile['n_columns']}")
    print(f"Duplicate rows: {profile['duplicate_rows']}  Missing cells: {profile['missing_cells']}")
    for warning in profile["warnings"]:
        print(f"  Warning: {warning}")


def print_leaderboard(result):
    print(f"\nLeaderboard ({result['cv_folds']}-fold cross-validation on training data)")
    print(f"{'Model':<22}{'CV score':>10}{'Std':>9}{'Seconds':>10}")
    for row in result["leaderboard"]:
        if row["cv_mean"] is None:
            print(f"{row['model']:<22}{'failed':>10}  {row['error']}")
        else:
            print(f"{row['model']:<22}{row['cv_mean']:>10}{row['cv_std']:>9}{row['seconds']:>10}")


def print_test_metrics(result):
    print(f"\nBest model: {result['best_model']}")
    print(f"Test set results ({result['n_test']} rows, used once)")
    for key, value in result["test_metrics"].items():
        if key in ("labels", "confusion_matrix"):
            continue
        print(f"  {key}: {value}")
    if "confusion_matrix" in result["test_metrics"]:
        print(f"  labels: {result['test_metrics']['labels']}")
        for row in result["test_metrics"]["confusion_matrix"]:
            print(f"  {row}")


def main():
    args = parse_args()
    config.ensure_dirs()

    try:
        df = load_csv(args.csv)
        profile = profile_dataframe(df, args.target)
        print_profile(profile)

        exclude = list(args.exclude)
        if args.exclude_flagged:
            for names in profile["flagged"].values():
                exclude.extend(name for name in names if name not in exclude)
        if exclude:
            print(f"Excluded columns: {exclude}")

        options = {"scaling": args.scaling, "numeric_impute": args.numeric_impute}
        result = train_and_evaluate(df, args.target, args.task, exclude, options)
    except (DataValidationError, FileNotFoundError, RuntimeError) as exc:
        print(f"Error: {exc}")
        sys.exit(1)

    print_leaderboard(result)
    print_test_metrics(result)

    model_id, folder = save_artifacts(result)
    print(f"\nSaved model '{model_id}' to {folder}")

    loaded = load_pipeline(model_id)
    sample = df.head(5)
    expected = result["pipeline"].predict(sample[required_columns(result["pipeline"])]).tolist()
    reloaded = predict(loaded, sample)
    print(f"Reload check: {'OK' if expected == reloaded else 'FAILED'}")
    print(f"Sample predictions: {reloaded}")


if __name__ == "__main__":
    main()