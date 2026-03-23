import pandas as pd
import os


def run_cleaning_pipeline(dataset_path, business_requirements=None):

    os.makedirs("outputs/engineer", exist_ok=True)

    df = pd.read_csv(dataset_path)

    report = {}

    # ----------------------------------
    # Basic dataset profile
    # ----------------------------------

    report["rows_before"] = len(df)
    report["columns"] = list(df.columns)

    # ----------------------------------
    # Missing value handling
    # ----------------------------------

    missing = df.isnull().sum()

    report["missing_values"] = missing.to_dict()

    for col in df.columns:

        if df[col].dtype in ["float64", "int64"]:
            df[col] = df[col].fillna(df[col].median())

        else:
            df[col] = df[col].fillna("Unknown")

    # ----------------------------------
    # Remove duplicate rows
    # ----------------------------------

    duplicates = df.duplicated().sum()

    report["duplicates_removed"] = int(duplicates)

    df = df.drop_duplicates()

    # ----------------------------------
    # Outlier clipping (simple)
    # ----------------------------------

    numeric_cols = df.select_dtypes(include="number").columns

    for col in numeric_cols:

        q1 = df[col].quantile(0.25)
        q3 = df[col].quantile(0.75)

        iqr = q3 - q1

        lower = q1 - 1.5 * iqr
        upper = q3 + 1.5 * iqr

        df[col] = df[col].clip(lower, upper)

    # ----------------------------------
    # Save cleaned dataset
    # ----------------------------------

    cleaned_path = "outputs/engineer/cleaned_dataset.csv"

    df.to_csv(cleaned_path, index=False)

    report["rows_after"] = len(df)
    report["cleaned_dataset"] = cleaned_path

    return {
        "status": "success",
        "report": report
    }