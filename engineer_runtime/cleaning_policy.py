"""Conservative, deterministic guardrails for proposed data-cleaning operations.

The LLM may propose actions, but it cannot override these safety checks.
"""
import re
import pandas as pd

PROTECTED_TOKENS = {"id", "uuid", "guid", "key", "zip", "zipcode", "postal", "postcode", "ssn", "iban", "account", "sku", "code", "phone", "passport", "vin"}
RISKY_ACTIONS = {"remove_duplicates", "clip_outliers"}
SUPPORTED_ACTIONS = {"replace_invalid_values", "fill_missing", "cast_type", "standardize_text", "standardize_date", *RISKY_ACTIONS}


def is_identifier(column, series=None):
    tokens = set(filter(None, re.split(r"[^a-z0-9]+", str(column).lower())))
    if tokens & PROTECTED_TOKENS or str(column).lower().endswith("_id"):
        return True
    if series is not None and (pd.api.types.is_bool_dtype(series) or pd.api.types.is_datetime64_any_dtype(series)):
        return False
    return False


def assess_step(df, step):
    """Return (allowed, reason). Defaults to no destructive changes."""
    action, col = step.get("action"), step.get("column")
    params = step.get("parameters") or {}
    if action not in SUPPORTED_ACTIONS:
        return False, "Unknown cleaning action"
    if action == "remove_duplicates":
        return False, "Row deletion requires explicit review of business keys and event semantics"
    if col not in df.columns:
        return False, "Column not found"
    series = df[col]
    if is_identifier(col, series):
        return False, "Identifier/code field protected from automatic changes"
    if action == "clip_outliers":
        return False, "Outlier clipping requires domain-approved limits"
    if action == "fill_missing":
        return False, "Imputation requires explicit business approval and a documented strategy"
    if action == "replace_invalid_values":
        return False, "Placeholder values may be legitimate categories; review before replacing"
    if action == "standardize_text":
        return False, "Text normalization can change names, codes, and categories; review before applying"
    if action == "standardize_date":
        return False, "Date normalization requires an explicit source format and timezone policy"
    if action == "cast_type":
        target = str(params.get("target_type", "")).lower()
        if target == "number":
            if pd.api.types.is_bool_dtype(series):
                return False, "Boolean data cannot be cast to numeric automatically"
            converted = pd.to_numeric(series, errors="coerce")
            lost = series.notna() & converted.isna()
            if lost.any():
                return False, f"Numeric conversion would lose {int(lost.sum())} values"
            return True, "Lossless numeric conversion"
        return False, "Datetime/string casting requires explicit review"
    return False, "Action requires review"
