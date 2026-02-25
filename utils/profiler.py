import pandas as pd

def profile_dataset(csv_path: str) -> dict:
    df = pd.read_csv(csv_path)

    profile = {
        "row_count": int(len(df)),
        "column_count": int(len(df.columns)),
        "columns": [],
    }

    for col in df.columns:
        profile["columns"].append({
            "name": col,
            "dtype": str(df[col].dtype),
            "null_count": int(df[col].isna().sum()),
            "unique_count": int(df[col].nunique()),
        })

    return profile


def profile_to_text(profile: dict) -> str:
    lines = []
    lines.append(f"Dataset has {profile['row_count']} rows and {profile['column_count']} columns.")
    lines.append("Columns:")

    for col in profile["columns"]:
        lines.append(
            f"- {col['name']} (type={col['dtype']}, nulls={col['null_count']}, unique={col['unique_count']})"
        )

    return "\n".join(lines)