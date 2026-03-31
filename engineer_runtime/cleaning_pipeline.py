import os
import pandas as pd

from agents.engineer_agents.dataset_profiler import DatasetProfilerAgent
from agents.engineer_agents.cleaning_planner_agent import CleaningPlannerAgent


SENTINEL_VALUES = {"ERROR", "UNKNOWN", "N/A", "NULL", "?", ""}


def replace_sentinel_values(df: pd.DataFrame) -> pd.DataFrame:
    """Replace common placeholder strings with NaN before profiling."""
    cleaned = df.copy()
    for col in cleaned.columns:
        cleaned[col] = cleaned[col].apply(
            lambda x: None if str(x).strip().upper() in SENTINEL_VALUES else x
        )
    return cleaned


def safe_missing_pct(df: pd.DataFrame) -> float:
    if len(df) == 0 or len(df.columns) == 0:
        return 0.0
    value = float(df.isna().mean().mean() * 100)
    return 0.0 if pd.isna(value) else round(value, 2)


def smart_title(value):
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    value = str(value).strip()
    if not value or value.upper() in SENTINEL_VALUES:
        return None
    # Preserve all-caps short codes (e.g. "US", "CA")
    if value.upper() == value and len(value) <= 4:
        return value
    return value.title()


def _parse_date_series(series: pd.Series) -> pd.Series:
    """
    Robustly parse a date column that may contain mixed formats.
    Tries dayfirst=False first, then dayfirst=True for any failures.
    """
    # First pass: standard ISO / US format
    parsed = pd.to_datetime(series, errors="coerce", dayfirst=False)
    # Second pass: for values that still failed, try dayfirst
    failed_mask = parsed.isna() & series.notna() & (series.astype(str).str.strip() != "")
    if failed_mask.any():
        retry = pd.to_datetime(series[failed_mask], errors="coerce", dayfirst=True)
        parsed = parsed.copy()
        parsed[failed_mask] = retry
    return parsed


def apply_cleaning_steps(df: pd.DataFrame, steps: list):
    cleaned = df.copy()
    execution_log = []

    for step in steps:
        action = step.get("action")
        col    = step.get("column")
        params = step.get("parameters", {}) or {}

        try:
            if action == "replace_invalid_values" and col in cleaned.columns:
                invalid_values = {
                    str(v).strip().upper()
                    for v in params.get("invalid_values", ["ERROR", "UNKNOWN", "N/A", "NULL", "?", ""])
                }
                cleaned[col] = cleaned[col].apply(
                    lambda x: None if str(x).strip().upper() in invalid_values else x
                )
                execution_log.append({
                    "action": action, "column": col,
                    "status": "applied", "reason": step.get("reason", "")
                })

            elif action == "fill_missing" and col in cleaned.columns:
                strategy = str(params.get("strategy", "mode")).lower().strip()

                if pd.api.types.is_datetime64_any_dtype(cleaned[col]):
                    mode_val = cleaned[col].dropna().mode()
                    if len(mode_val) > 0:
                        cleaned[col] = cleaned[col].fillna(mode_val.iloc[0])
                else:
                    numeric_version  = pd.to_numeric(cleaned[col], errors="coerce")
                    non_null_count   = int(cleaned[col].notna().sum())
                    numeric_hit_rate = numeric_version.notna().sum() / max(non_null_count, 1)
                    is_numeric_like  = non_null_count > 0 and numeric_hit_rate >= 0.5

                    if strategy == "median" and is_numeric_like:
                        cleaned[col] = numeric_version.fillna(numeric_version.median())
                    elif strategy == "mean" and is_numeric_like:
                        cleaned[col] = numeric_version.fillna(numeric_version.mean())
                    else:
                        mode_val = cleaned[col].dropna().mode()
                        if len(mode_val) > 0:
                            cleaned[col] = cleaned[col].fillna(mode_val.iloc[0])

                execution_log.append({
                    "action": action, "column": col,
                    "status": "applied", "reason": step.get("reason", "")
                })

            elif action == "cast_type" and col in cleaned.columns:
                target_type = str(params.get("target_type", "string")).lower().strip()

                if target_type == "number":
                    cleaned[col] = pd.to_numeric(cleaned[col], errors="coerce")
                elif target_type == "datetime":
                    cleaned[col] = _parse_date_series(cleaned[col])
                else:
                    cleaned[col] = cleaned[col].astype(str)

                execution_log.append({
                    "action": action, "column": col,
                    "status": "applied", "reason": step.get("reason", "")
                })

            elif action == "standardize_text" and col in cleaned.columns:
                # Strip + collapse whitespace first
                cleaned[col] = (
                    cleaned[col]
                    .astype(str)
                    .str.strip()
                    .str.replace(r"\s+", " ", regex=True)
                )
                style = str(params.get("style", "title")).lower().strip()
                if style == "lower":
                    cleaned[col] = cleaned[col].str.lower()
                elif style == "upper":
                    cleaned[col] = cleaned[col].str.upper()
                else:
                    cleaned[col] = cleaned[col].apply(smart_title)

                # Replace sentinel strings that survived as strings
                cleaned[col] = cleaned[col].replace(
                    {"Nan": None, "None": None, "nan": None, "": None,
                     "N/A": None, "Null": None, "NULL": None}
                )
                execution_log.append({
                    "action": action, "column": col,
                    "status": "applied", "reason": step.get("reason", "")
                })

            elif action == "standardize_date" and col in cleaned.columns:
                output_format = str(params.get("format", "%Y-%m-%d")).strip() or "%Y-%m-%d"
                # Use robust parser so mixed-format dates don't silently become NaT
                dt_series = _parse_date_series(cleaned[col])
                cleaned[col] = dt_series.dt.strftime(output_format)
                # Where the original was null/NaT, put None back rather than "NaT"
                cleaned[col] = cleaned[col].where(dt_series.notna(), None)
                execution_log.append({
                    "action": action, "column": col,
                    "status": "applied", "reason": step.get("reason", "")
                })

            elif action == "remove_duplicates":
                before_rows = len(cleaned)
                subset = params.get("subset")
                cleaned = cleaned.drop_duplicates(subset=subset if subset else None)
                execution_log.append({
                    "action": action, "column": col,
                    "status": "applied",
                    "rows_removed": int(before_rows - len(cleaned)),
                    "reason": step.get("reason", "")
                })

            elif action == "clip_outliers" and col in cleaned.columns:
                numeric_series = pd.to_numeric(cleaned[col], errors="coerce")
                valid = numeric_series.dropna()
                if len(valid) > 0:
                    q1    = valid.quantile(0.25)
                    q3    = valid.quantile(0.75)
                    iqr   = q3 - q1
                    lower = q1 - 1.5 * iqr
                    upper = q3 + 1.5 * iqr
                    cleaned[col] = numeric_series.clip(lower=lower, upper=upper)
                execution_log.append({
                    "action": action, "column": col,
                    "status": "applied", "reason": step.get("reason", "")
                })

            else:
                execution_log.append({
                    "action": action, "column": col,
                    "status": "skipped",
                    "reason": f"Unsupported action or column not found: {action} / {col}"
                })

        except Exception as e:
            execution_log.append({
                "action": action, "column": col,
                "status": "failed", "error": str(e)
            })

    return cleaned, execution_log


def run_cleaning_pipeline(dataset_path: str, business_requirements: str = ""):
    os.makedirs("outputs/cleaner/cleaned_files", exist_ok=True)

    # ── Load raw data ────────────────────────────────────────────
    if dataset_path.endswith(".csv"):
        raw_df = pd.read_csv(dataset_path)
    elif dataset_path.endswith(".xlsx"):
        raw_df = pd.read_excel(dataset_path)
    else:
        raise ValueError("Unsupported dataset format")

    # Replace obvious placeholder strings with NaN before profiling
    working_df = replace_sentinel_values(raw_df.copy())

    # ── Profile the working (pre-clean) dataframe ────────────────
    profiler        = DatasetProfilerAgent(df=working_df)
    profile_result  = profiler.run()
    dataset_profile = profile_result["profile"]   # full enriched dict
    dataset_markdown = profile_result["markdown"]

    # ── Generate cleaning plan ───────────────────────────────────
    planner = CleaningPlannerAgent()
    plan    = planner.run(dataset_profile, business_requirements)

    # ── Execute cleaning steps ───────────────────────────────────
    cleaned_df, execution_log = apply_cleaning_steps(
        working_df,
        plan.get("cleaning_steps", [])
    )

    # ── Save cleaned file ────────────────────────────────────────
    base_name   = os.path.basename(dataset_path)
    output_path = os.path.join("outputs/cleaner/cleaned_files", f"cleaned_{base_name}")

    if output_path.endswith(".csv"):
        cleaned_df.to_csv(output_path, index=False)
    elif output_path.endswith(".xlsx"):
        cleaned_df.to_excel(output_path, index=False)
    else:
        output_path += ".csv"
        cleaned_df.to_csv(output_path, index=False)

    # ── Cleaned profile summary ──────────────────────────────────
    cleaned_profile = {
        "row_count":           int(len(cleaned_df)),
        "column_count":        int(len(cleaned_df.columns)),
        "duplicate_rows":      int(cleaned_df.duplicated().sum()),
        "overall_missing_pct": safe_missing_pct(cleaned_df)
    }

    duplicates_removed = max(
        0,
        int(dataset_profile.get("duplicate_rows", 0)) - int(cleaned_profile.get("duplicate_rows", 0))
    )

    # ── Return full result dict ──────────────────────────────────
    # dataset_profile now contains all fields the engineer.html template
    # needs for the Dataset Intelligence section:
    #   row_count, column_count, duplicate_rows, overall_missing_pct
    #   numeric_column_count, categorical_column_count, datetime_column_count
    #   date_range_start, date_range_end
    #   metric_candidates (list[str])
    #   column_profiles   (list[dict])
    #   columns           (list[dict])  ← kept for planner compatibility
    return {
        "status":                  "success",
        "dataset_profile":         dataset_profile,
        "dataset_profile_markdown": dataset_markdown,
        "cleaning_plan":           plan,
        "execution_log":           execution_log,
        "cleaned_file_path":       output_path.replace("\\", "/"),
        "cleaned_profile":         cleaned_profile,
        "rows_before_cleaning":    int(len(working_df)),
        "rows_after_cleaning":     int(len(cleaned_df)),
        "duplicates_removed":      duplicates_removed,
        "preview_before":          working_df.head(10).fillna("").to_dict(orient="records"),
        "preview_after":           cleaned_df.head(10).fillna("").to_dict(orient="records"),
    }