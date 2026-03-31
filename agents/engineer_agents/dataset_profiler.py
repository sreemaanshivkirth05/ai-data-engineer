import pandas as pd
from typing import Dict, Any, Optional


class DatasetProfilerAgent:
    def __init__(self, dataset_path: Optional[str] = None, df: Optional[pd.DataFrame] = None):
        self.dataset_path = dataset_path
        self.df = df

    def run(self) -> Dict[str, Any]:
        df = self._load_dataset().copy()
        total_rows = max(len(df), 1)

        # ── Column-level profiles ─────────────────────────────────
        col_profiles = []
        for col in df.columns:
            series = df[col]
            non_null = series.dropna()
            unique_count = int(series.nunique(dropna=True))
            unique_ratio = round(float(unique_count / total_rows), 4)

            col_profile = {
                "name": str(col),
                "dtype": str(series.dtype),
                "null_count": int(series.isna().sum()),
                "null_pct": round(float(series.isna().mean() * 100), 2) if len(df) > 0 else 0.0,
                "non_null_pct": round(float(series.notna().mean() * 100), 2) if len(df) > 0 else 0.0,
                "unique_count": unique_count,
                "unique_ratio": unique_ratio,
                "sample_values": [self._safe_value(v) for v in non_null.head(5).tolist()],
                "is_candidate_key": False,
                "possible_pii": False,
                "semantic_type": "unknown",
                "stats": {
                    "min": None,
                    "max": None,
                    "mean": None,
                    "median": None
                }
            }

            col_profile["is_candidate_key"] = (
                col_profile["null_count"] == 0 and col_profile["unique_count"] == len(df)
            )

            pii_keywords = ["name", "email", "phone", "ssn", "address"]
            col_lower = str(col).lower().strip()
            col_profile["possible_pii"] = any(k in col_lower for k in pii_keywords)

            col_profile["semantic_type"] = self._infer_semantic_type(
                col_name=col_lower,
                dtype=str(series.dtype),
                is_candidate_key=col_profile["is_candidate_key"],
                unique_ratio=unique_ratio,
            )

            numeric_series = pd.to_numeric(series, errors="coerce").dropna()
            if len(numeric_series) > 0:
                col_profile["stats"]["min"] = round(float(numeric_series.min()), 4)
                col_profile["stats"]["max"] = round(float(numeric_series.max()), 4)
                col_profile["stats"]["mean"] = round(float(numeric_series.mean()), 4)
                col_profile["stats"]["median"] = round(float(numeric_series.median()), 4)

            col_profiles.append(col_profile)

        # ── Aggregate counts by semantic type ─────────────────────
        numeric_cols  = [c for c in col_profiles if c["semantic_type"] in ("metric", "numeric")]
        cat_cols      = [c for c in col_profiles if c["semantic_type"] == "categorical"]
        datetime_cols_list = [c for c in col_profiles if c["semantic_type"] == "datetime"]
        id_cols       = [c for c in col_profiles if c["semantic_type"] == "id"]

        # ── Date range from actual datetime columns ────────────────
        date_range_start = None
        date_range_end   = None
        datetime_dtype_cols = df.select_dtypes(
            include=["datetime64[ns]", "datetime64[ns, UTC]"]
        ).columns.tolist()
        if not datetime_dtype_cols:
            # try to detect from column names
            for c in df.columns:
                if any(k in str(c).lower() for k in ["date", "time", "timestamp"]):
                    parsed = pd.to_datetime(df[c], errors="coerce")
                    if parsed.notna().sum() > 0:
                        datetime_dtype_cols.append(c)
                        break
        if datetime_dtype_cols:
            try:
                primary_dt = pd.to_datetime(df[datetime_dtype_cols[0]], errors="coerce").dropna()
                if len(primary_dt) > 0:
                    date_range_start = str(primary_dt.min().date())
                    date_range_end   = str(primary_dt.max().date())
            except Exception:
                pass

        # ── Business metric candidates ─────────────────────────────
        METRIC_KEYWORDS = [
            "sales", "revenue", "profit", "amount", "cost", "price",
            "income", "margin", "quantity", "qty", "units", "discount",
            "value", "score", "rate", "total", "spend", "count"
        ]
        metric_candidates = []
        for c in col_profiles:
            if c["semantic_type"] in ("metric", "numeric"):
                col_lower_name = c["name"].lower().replace("_", " ")
                if any(kw in col_lower_name for kw in METRIC_KEYWORDS):
                    metric_candidates.append(c["name"])
        # Fallback: first 3 numeric cols if no keyword match
        if not metric_candidates:
            metric_candidates = [c["name"] for c in numeric_cols[:3]]

        # ── Assemble final profile ─────────────────────────────────
        profile = {
            "row_count":           int(len(df)),
            "column_count":        int(len(df.columns)),
            "duplicate_rows":      int(df.duplicated().sum()),
            "overall_missing_pct": self._safe_missing_pct(df),
            # NEW — used by engineer.html Dataset Intelligence section
            "numeric_column_count":     len(numeric_cols),
            "categorical_column_count": len(cat_cols),
            "datetime_column_count":    len(datetime_cols_list),
            "id_column_count":          len(id_cols),
            "date_range_start":         date_range_start,
            "date_range_end":           date_range_end,
            "metric_candidates":        metric_candidates[:6],
            # column_profiles is the same data as columns but renamed so the
            # template can reference result.dataset_profile.column_profiles
            "column_profiles":          col_profiles,
            # keep "columns" for backward compat with cleaning_planner_agent.py
            "columns":                  col_profiles,
        }

        return {
            "profile": profile,
            "markdown": self._to_markdown(profile)
        }

    def _load_dataset(self) -> pd.DataFrame:
        if self.df is not None:
            return self.df
        if not self.dataset_path:
            raise ValueError("Either dataset_path or df must be provided.")
        if self.dataset_path.endswith(".csv"):
            return pd.read_csv(self.dataset_path)
        if self.dataset_path.endswith(".xlsx"):
            return pd.read_excel(self.dataset_path)
        raise ValueError("Unsupported dataset format. Use CSV or XLSX.")

    def _infer_semantic_type(
        self,
        col_name: str,
        dtype: str,
        is_candidate_key: bool,
        unique_ratio: float = 0.0,
    ) -> str:
        # IDs: named like an id OR nearly unique non-datetime column
        id_keywords = [
            "id", "uuid", "key", "row number", "rownum",
            "transaction id", "order id", "customer id", "product id",
            "postal", "zip", "zipcode", "row id"
        ]
        if is_candidate_key:
            return "id"
        if any(k in col_name for k in id_keywords):
            return "id"
        # Near-unique string column = probably an identifier
        if unique_ratio >= 0.95 and "int" not in dtype and "float" not in dtype and "datetime" not in dtype:
            return "id"

        if any(x in col_name for x in ["date", "time", "timestamp", "month", "year", "quarter"]):
            return "datetime"
        if "datetime" in dtype.lower():
            return "datetime"

        if any(x in col_name for x in [
            "sales", "revenue", "profit", "cost", "price", "amount",
            "discount", "quantity", "qty", "total", "salary", "age",
            "score", "rate", "count", "spend", "margin"
        ]):
            return "metric"

        if any(x in col_name for x in [
            "region", "country", "state", "city", "category", "segment",
            "product", "channel", "customer", "department", "status",
            "location", "payment", "method", "item", "ship mode",
            "sub-category", "sub category"
        ]):
            return "categorical"

        lower_dtype = dtype.lower()
        if "int" in lower_dtype or "float" in lower_dtype:
            return "numeric"
        if "object" in lower_dtype or "string" in lower_dtype:
            return "categorical"

        return "unknown"

    def _safe_missing_pct(self, df: pd.DataFrame) -> float:
        if len(df) == 0 or len(df.columns) == 0:
            return 0.0
        value = float(df.isna().mean().mean() * 100)
        return 0.0 if pd.isna(value) else round(value, 2)

    def _safe_value(self, value):
        if pd.isna(value):
            return None
        return str(value)

    def _to_markdown(self, profile: Dict[str, Any]) -> str:
        lines = []
        lines.append("# Dataset Profile Report\n")
        lines.append(f"- **Rows:** {profile['row_count']}")
        lines.append(f"- **Columns:** {profile['column_count']}")
        lines.append(f"- **Duplicate Rows:** {profile['duplicate_rows']}")
        lines.append(f"- **Overall Missing %:** {profile['overall_missing_pct']}")
        lines.append(f"- **Numeric columns:** {profile['numeric_column_count']}")
        lines.append(f"- **Categorical columns:** {profile['categorical_column_count']}")
        lines.append(f"- **Datetime columns:** {profile['datetime_column_count']}")
        if profile.get("date_range_start"):
            lines.append(f"- **Date range:** {profile['date_range_start']} → {profile['date_range_end']}")
        if profile.get("metric_candidates"):
            lines.append(f"- **Metric candidates:** {', '.join(profile['metric_candidates'])}")
        lines.append("\n## Columns Overview\n")

        for col in profile["columns"]:
            lines.append(f"### `{col['name']}`")
            lines.append(f"- Type: `{col['dtype']}`")
            lines.append(f"- Semantic Type: `{col['semantic_type']}`")
            lines.append(f"- Nulls: {col['null_count']} ({col['null_pct']:.2f}%)")
            lines.append(f"- Unique values: {col['unique_count']}")
            lines.append(f"- Candidate Key: {'Yes' if col['is_candidate_key'] else 'No'}")
            lines.append(f"- Possible PII: {'Yes' if col['possible_pii'] else 'No'}")

            stats = col.get("stats", {})
            if stats.get("min") is not None:
                lines.append(f"- Min: {stats['min']}")
                lines.append(f"- Max: {stats['max']}")
                lines.append(f"- Mean: {stats['mean']}")
                lines.append(f"- Median: {stats['median']}")

            if col.get("sample_values"):
                lines.append(f"- Sample Values: {', '.join(map(str, col['sample_values']))}")

            lines.append("")

        return "\n".join(lines)