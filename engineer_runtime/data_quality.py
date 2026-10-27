"""Read-only, type-aware data quality diagnostics.

Never mutates source data or guesses that domain-specific values are invalid.
"""
import re
import pandas as pd
from pandas.api.types import is_bool_dtype, is_datetime64_any_dtype, is_numeric_dtype
from engineer_runtime.cleaning_policy import is_identifier

ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}(?:[T ]\d{2}:\d{2}(?::\d{2}(?:\.\d+)?)?(?:Z|[+-]\d{2}:?\d{2})?)?$")
AMBIGUOUS_DATE = re.compile(r"^(0?[1-9]|1[0-2])[/.-](0?[1-9]|1[0-2])[/.-]\d{2,4}$")
EMAIL = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


def diagnose_column(name, series):
    """Produce JSON-friendly diagnostics and review recommendations."""
    result = {"column": str(name), "physical_type": str(series.dtype), "semantic_hint": "unknown",
              "protected": False, "issues": [], "recommendations": []}
    non_null = series.dropna()
    if is_identifier(name, series):
        result["semantic_hint"] = "identifier"
        result["protected"] = True
        result["recommendations"].append("Preserve exact source values, including leading zeros")
        return result
    if is_bool_dtype(series):
        result["semantic_hint"] = "boolean"
        return result
    if is_datetime64_any_dtype(series):
        result["semantic_hint"] = "datetime"
        result["recommendations"].append("Preserve timezone and timestamp precision")
        return result
    if is_numeric_dtype(series):
        result["semantic_hint"] = "numeric"
        result["recommendations"].append("Review outliers against business rules; do not auto-clip")
        return result
    values = non_null.astype(str).str.strip()
    if values.empty:
        result["semantic_hint"] = "empty"
        result["issues"].append({"type": "all_missing", "count": int(series.isna().sum())})
        return result
    lower_name = str(name).lower()
    if "email" in lower_name:
        result["semantic_hint"] = "email"
        invalid = int((~values.map(lambda x: bool(EMAIL.fullmatch(x)))).sum())
        if invalid:
            result["issues"].append({"type": "invalid_email_format", "count": invalid})
        result["protected"] = True
        return result
    if any(token in lower_name for token in ("date", "timestamp", "datetime")):
        result["semantic_hint"] = "datetime_candidate"
        ambiguous = int(values.map(lambda x: bool(AMBIGUOUS_DATE.fullmatch(x))).sum())
        if ambiguous:
            result["issues"].append({"type": "ambiguous_date", "count": ambiguous})
            result["recommendations"].append("Require explicit source date format before parsing")
        iso = int(values.map(lambda x: bool(ISO_DATE.fullmatch(x))).sum())
        result["iso_format_count"] = iso
        return result
    result["semantic_hint"] = "text"
    blank = int((values == "").sum())
    if blank:
        result["issues"].append({"type": "blank_string", "count": blank})
    result["recommendations"].append("Review categorical casing and placeholder meaning before normalization")
    return result


def diagnose_dataframe(df):
    """Data quality summary, without exposing raw PII values."""
    if len(set(map(str, df.columns))) != len(df.columns):
        raise ValueError("Duplicate column labels require explicit resolution")
    columns = [diagnose_column(col, df[col]) for col in df.columns]
    return {"row_count": int(len(df)), "column_count": int(len(df.columns)),
            "columns": columns, "requires_review": any(c["issues"] for c in columns)}
