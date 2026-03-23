import pandas as pd
from typing import Dict, Any

class DatasetProfilerAgent:
    def __init__(self, csv_path: str):
        self.csv_path = csv_path

    def run(self) -> Dict[str, Any]:
        df = pd.read_csv(self.csv_path)

        profile = {
            "row_count": len(df),
            "column_count": len(df.columns),
            "columns": []
        }

        for col in df.columns:
            series = df[col]

            col_profile = {
                "name": col,
                "dtype": str(series.dtype),
                "null_count": int(series.isna().sum()),
                "null_pct": float(series.isna().mean() * 100),
                "unique_count": int(series.nunique(dropna=True)),
            }

            # Numeric stats
            if pd.api.types.is_numeric_dtype(series):
                if not series.isna().all():
                    col_profile["min"] = float(series.min())
                    col_profile["max"] = float(series.max())
                    col_profile["mean"] = float(series.mean())
                else:
                    col_profile["min"] = None
                    col_profile["max"] = None
                    col_profile["mean"] = None
            else:
                col_profile["min"] = None
                col_profile["max"] = None
                col_profile["mean"] = None

            # Candidate primary key heuristic
            col_profile["is_candidate_key"] = (
                col_profile["null_count"] == 0 and col_profile["unique_count"] == len(df)
            )

            # Simple PII heuristic
            pii_keywords = ["name", "email", "phone", "ssn", "address"]
            col_lower = col.lower()
            col_profile["possible_pii"] = any(k in col_lower for k in pii_keywords)

            profile["columns"].append(col_profile)

        markdown = self._to_markdown(profile)

        return {
            "profile": profile,
            "markdown": markdown
        }

    def _to_markdown(self, profile: Dict[str, Any]) -> str:
        lines = []
        lines.append("# 📊 Dataset Profile Report\n")
        lines.append(f"- **Rows:** {profile['row_count']}")
        lines.append(f"- **Columns:** {profile['column_count']}\n")

        lines.append("## Columns Overview\n")

        for col in profile["columns"]:
            lines.append(f"### `{col['name']}`")
            lines.append(f"- Type: `{col['dtype']}`")
            lines.append(f"- Nulls: {col['null_count']} ({col['null_pct']:.2f}%)")
            lines.append(f"- Unique values: {col['unique_count']}")
            if col["min"] is not None:
                lines.append(f"- Min: {col['min']}")
                lines.append(f"- Max: {col['max']}")
                lines.append(f"- Mean: {col['mean']}")
            lines.append(f"- Candidate Key: {'✅' if col['is_candidate_key'] else '❌'}")
            lines.append(f"- Possible PII: {'⚠️ Yes' if col['possible_pii'] else 'No'}")
            lines.append("")

        return "\n".join(lines)