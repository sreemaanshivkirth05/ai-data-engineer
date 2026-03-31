"""
selection_policy.py

Single authority for all column selection decisions across the pipeline.

Every agent reads from a SelectionResult produced here rather than
independently scoring columns. This makes selection logic:
  - testable in one place
  - explainable via the attached explanation object
  - consistent across KPI, Analysis, Viz, and Narrative agents
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional

import pandas as pd


# ─────────────────────────────────────────────────────────────────
# Constants
# ─────────────────────────────────────────────────────────────────

OVERVIEW_PHRASES = {
    "kpi overview", "kpi insights", "pki insights", "pki overview",
    "dataset overview", "business summary", "overall performance",
    "overview", "summary", "insights", "analysis", "show insights",
    "general overview", "full overview", "full summary",
    "what can you tell me", "tell me about", "explore this",
}

METRIC_KEYWORDS = [
    "sales", "revenue", "profit", "amount", "cost", "price",
    "income", "margin", "quantity", "qty", "units", "discount",
    "value", "score", "rate", "count", "total", "spend", "volume",
]

ID_KEYWORDS = [
    "id", "uuid", "key", "row number", "rownum",
    "transaction id", "order id", "customer id", "product id",
    "postal", "zip", "zipcode", "row id",
]

CATEGORY_KEYWORDS = [
    "region", "country", "state", "city", "category", "segment",
    "product", "sub category", "channel", "customer", "ship mode",
    "department", "type", "group", "class", "market", "brand",
    "status", "item", "location",
]

TEXT_KEYWORDS = [
    "comment", "comments", "note", "notes", "description",
    "message", "text", "address", "summary", "remark", "remarks",
]

REJECTION_REASONS = {
    "identifier": "Identifier-like column — row key, UUID, or high-cardinality code field.",
    "too_granular": "Too granular for grouping — almost unique values, no meaningful segments.",
    "too_sparse": "Heavy missingness — fewer than 50% of values present.",
    "text_field": "Free-text field — not suitable as a metric or grouping dimension.",
    "single_value": "Only one unique value — no variation to analyse.",
    "low_variance": "Very low cardinality for a metric — likely a flag or boolean.",
    "placeholder_dominated": "Dominated by placeholder values such as Unknown or N/A.",
    "datetime_as_metric": "Datetime column — valid for time axis, not a business metric.",
}


# ─────────────────────────────────────────────────────────────────
# Output dataclass
# ─────────────────────────────────────────────────────────────────

@dataclass
class ColumnEntry:
    name: str
    dtype: str
    semantic_type: str          # metric | category | datetime | id | text | unknown
    is_id: bool
    non_null_pct: float
    unique_count: int
    unique_ratio: float
    target_score: float
    headline_dim_score: float
    supporting_dim_score: float
    time_score: float
    rejected: bool
    rejection_reason: Optional[str]
    selection_note: str         # why selected (if applicable)


@dataclass
class SelectionResult:
    question_mode: str          # "overview" | "specific" | "trend" | "relationship" | "distribution"
    target: Optional[str]
    target_why: str
    headline_dimension: Optional[str]
    headline_dimension_why: str
    supporting_dimensions: list[str]
    supporting_dimensions_why: list[str]
    time_column: Optional[str]
    time_column_why: str
    rejected_columns: dict[str, str]   # col_name -> reason string
    row_filter_applied: bool
    row_filter_why: str
    confidence: str             # "high" | "medium" | "low"
    confidence_note: str
    registry: list[ColumnEntry] = field(default_factory=list)


# ─────────────────────────────────────────────────────────────────
# Public entry point
# ─────────────────────────────────────────────────────────────────

def build_selection(
    df: pd.DataFrame,
    question: str,
    planner_target: Optional[str] = None,
    planner_drivers: Optional[list[str]] = None,
    max_supporting_dims: int = 3,
) -> SelectionResult:
    """
    Main entry point. Call this once per pipeline run.

    Parameters
    ----------
    df                  Preprocessed DataFrame (dtypes already coerced).
    question            Raw user question string.
    planner_target      Optional override from PlannerAgent (LLM-selected).
    planner_drivers     Optional driver list from PlannerAgent.
    max_supporting_dims Maximum number of supporting dimensions to return.

    Returns
    -------
    SelectionResult     Fully populated explanation and selection object.
    """
    q = _normalize(question)

    # ── Step 1: question mode ──────────────────────────────────────
    question_mode = _detect_question_mode(q)

    # ── Step 2: build column registry ─────────────────────────────
    registry = _build_registry(df, q)

    # ── Step 3: apply rejection rules ─────────────────────────────
    rejected: dict[str, str] = {}
    for entry in registry:
        reason = _rejection_reason(entry, df)
        if reason:
            entry.rejected = True
            entry.rejection_reason = reason
            rejected[entry.name] = REJECTION_REASONS[reason]

    # ── Step 4: score by role ─────────────────────────────────────
    good = [e for e in registry if not e.rejected]
    _score_entries(good, q, planner_target, planner_drivers or [])

    # ── Step 5: select target ─────────────────────────────────────
    target, target_why = _select_target(good, q, planner_target)

    # ── Step 6: select dimensions ─────────────────────────────────
    headline_dim, headline_why, supporting, supporting_why = _select_dimensions(
        good, target, q, question_mode,
        planner_drivers or [],
        max_supporting_dims,
    )

    # ── Step 7: select time column ────────────────────────────────
    time_col, time_why = _select_time_column(registry, q)

    # ── Step 8: row filter ────────────────────────────────────────
    row_filter, row_why = _row_filter_explanation(df, target)

    # ── Step 9: confidence ────────────────────────────────────────
    confidence, confidence_note = _assess_confidence(
        target, headline_dim, good, df, question_mode
    )

    return SelectionResult(
        question_mode=question_mode,
        target=target,
        target_why=target_why,
        headline_dimension=headline_dim,
        headline_dimension_why=headline_why,
        supporting_dimensions=supporting,
        supporting_dimensions_why=supporting_why,
        time_column=time_col,
        time_column_why=time_why,
        rejected_columns=rejected,
        row_filter_applied=row_filter,
        row_filter_why=row_why,
        confidence=confidence,
        confidence_note=confidence_note,
        registry=registry,
    )


# ─────────────────────────────────────────────────────────────────
# Step 1: question mode detection
# ─────────────────────────────────────────────────────────────────

def _detect_question_mode(q: str) -> str:
    """
    Classify the question into a mode that controls answer framing.

    overview     — broad/exploratory, no specific metric named
    trend        — temporal question
    relationship — correlation / driver question
    distribution — spread / histogram question
    specific     — targeted question with a named metric or dimension
    """
    token_count = len(q.split())

    # Exact overview phrases
    if q in OVERVIEW_PHRASES:
        return "overview"

    # Very short + vague
    if token_count <= 4:
        has_metric = any(kw in q for kw in METRIC_KEYWORDS)
        if not has_metric:
            return "overview"

    # Explicit overview language
    overview_fragments = [
        "overview", "overall", "summary", "big picture",
        "kpi", "performance", "dashboard", "snapshot",
        "tell me about", "what can you", "show me the data",
    ]
    if any(f in q for f in overview_fragments) and not any(kw in q for kw in METRIC_KEYWORDS):
        return "overview"

    # Trend
    trend_fragments = [
        "trend", "over time", "monthly", "weekly", "yearly",
        "quarterly", "timeline", "growth", "decline", "change over time",
    ]
    if any(f in q for f in trend_fragments):
        return "trend"

    # Relationship
    relationship_fragments = [
        "relationship", "correlation", "impact", "influence", "driver",
        "associated with", "linked to", "related to",
    ]
    if any(f in q for f in relationship_fragments):
        return "relationship"

    # Distribution
    distribution_fragments = [
        "distribution", "spread", "outlier", "histogram",
        "variance", "range", "dispersion",
    ]
    if any(f in q for f in distribution_fragments):
        return "distribution"

    return "specific"


# ─────────────────────────────────────────────────────────────────
# Step 2: build column registry
# ─────────────────────────────────────────────────────────────────

def _build_registry(df: pd.DataFrame, q: str) -> list[ColumnEntry]:
    total = max(len(df), 1)
    entries = []

    for col in df.columns:
        series = df[col]
        dtype = str(series.dtype)
        non_null_pct = float(series.notna().mean())
        unique_count = int(series.nunique(dropna=True))
        unique_ratio = float(unique_count / total)

        semantic_type = _infer_semantic_type(col, series, unique_ratio)
        is_id = _is_id_column(col, unique_ratio)

        entries.append(ColumnEntry(
            name=col,
            dtype=dtype,
            semantic_type=semantic_type,
            is_id=is_id,
            non_null_pct=non_null_pct,
            unique_count=unique_count,
            unique_ratio=unique_ratio,
            target_score=0.0,
            headline_dim_score=0.0,
            supporting_dim_score=0.0,
            time_score=0.0,
            rejected=False,
            rejection_reason=None,
            selection_note="",
        ))

    return entries


def _infer_semantic_type(col: str, series: pd.Series, unique_ratio: float) -> str:
    norm = _normalize(col)

    if _is_id_column(col, unique_ratio):
        return "id"

    if pd.api.types.is_datetime64_any_dtype(series):
        return "datetime"

    if any(k in norm for k in ["date", "time", "timestamp", "year", "month", "quarter", "week", "day"]):
        return "datetime"

    if pd.api.types.is_bool_dtype(series):
        return "boolean"

    if pd.api.types.is_numeric_dtype(series):
        return "metric"

    if pd.api.types.is_object_dtype(series):
        if any(k in norm for k in TEXT_KEYWORDS):
            return "text"
        if unique_ratio >= 0.95:
            return "text"
        if any(k in norm for k in CATEGORY_KEYWORDS):
            return "categorical"
        return "categorical"

    return "unknown"


def _is_id_column(col: str, unique_ratio: float) -> bool:
    norm = _normalize(col)
    if any(k in norm for k in ID_KEYWORDS):
        return True
    # Near-unique non-datetime string columns are almost always identifiers
    if unique_ratio >= 0.98:
        return True
    return False


# ─────────────────────────────────────────────────────────────────
# Step 3: rejection rules
# ─────────────────────────────────────────────────────────────────

def _rejection_reason(entry: ColumnEntry, df: pd.DataFrame) -> Optional[str]:
    """Return a rejection reason key or None if the column is acceptable."""

    if entry.is_id or entry.semantic_type == "id":
        return "identifier"

    if entry.semantic_type == "text":
        return "text_field"

    if entry.non_null_pct < 0.50:
        return "too_sparse"

    if entry.unique_count <= 1:
        return "single_value"

    if entry.semantic_type == "categorical" and entry.unique_ratio > 0.80:
        return "too_granular"

    # Check placeholder domination for categorical columns
    if entry.semantic_type == "categorical":
        series = df[entry.name]
        try:
            cleaned = series.dropna().astype(str).str.strip().str.lower()
            placeholder_ratio = float(
                cleaned.isin({"unknown", "error", "n/a", "na", "null", "none", ""}).mean()
            )
            if placeholder_ratio > 0.50:
                return "placeholder_dominated"
        except Exception:
            pass

    return None


# ─────────────────────────────────────────────────────────────────
# Step 4: score entries by role
# ─────────────────────────────────────────────────────────────────

def _score_entries(
    entries: list[ColumnEntry],
    q: str,
    planner_target: Optional[str],
    planner_drivers: list[str],
) -> None:
    """Mutates entries in-place. All four role scores are set here."""

    for e in entries:
        norm = _normalize(e.name)

        # ── Target score ──
        ts = 0.0
        if e.semantic_type == "metric":
            ts += 8.0
        elif e.semantic_type in ("categorical", "unknown"):
            ts += 1.0

        for kw in METRIC_KEYWORDS:
            if kw in norm:
                ts += 2.0
            if kw in q and kw in norm:
                ts += 3.0

        ts += e.non_null_pct * 2.0

        if e.name == planner_target:
            ts += 5.0

        e.target_score = ts

        # ── Headline dimension score ──
        hd = 0.0
        if e.semantic_type == "categorical":
            hd += 6.0

            nuniq = e.unique_count
            if 2 <= nuniq <= 10:
                hd += 4.0
            elif 11 <= nuniq <= 20:
                hd += 2.0
            elif nuniq > 40:
                hd -= 4.0

            for kw in CATEGORY_KEYWORDS:
                if kw in norm:
                    hd += 2.0
                if kw in q and kw in norm:
                    hd += 2.5

            if e.name in planner_drivers:
                hd += 3.0

        hd += e.non_null_pct
        e.headline_dim_score = hd

        # ── Supporting dimension score ──
        # Same as headline but with a slight penalty for already being headline
        # (actual dedup happens in step 6)
        sd = hd * 0.85
        if e.name in planner_drivers:
            sd += 1.5
        e.supporting_dim_score = sd

        # ── Time column score ──
        tc = 0.0
        if e.semantic_type == "datetime":
            tc += 8.0

        for kw in ["order date", "sale date", "transaction date", "date", "time", "timestamp"]:
            if kw in norm:
                tc += 2.0

        for kw in ["year", "month", "quarter", "week", "day"]:
            if kw in q and kw in norm:
                tc += 2.0

        tc += e.non_null_pct
        e.time_score = tc


# ─────────────────────────────────────────────────────────────────
# Step 5: target selection
# ─────────────────────────────────────────────────────────────────

def _select_target(
    entries: list[ColumnEntry],
    q: str,
    planner_target: Optional[str],
) -> tuple[Optional[str], str]:

    # Planner already named a valid column
    if planner_target:
        match = next((e for e in entries if e.name == planner_target and not e.rejected), None)
        if match:
            return match.name, (
                f"Selected by PlannerAgent (LLM) and validated by selection policy. "
                f"Semantic type: {match.semantic_type}. Non-null: {match.non_null_pct:.0%}."
            )

    # Score-based fallback
    candidates = [e for e in entries if e.semantic_type == "metric" and not e.rejected]
    if not candidates:
        candidates = [e for e in entries if not e.rejected]

    if not candidates:
        return None, "No suitable target metric found in the dataset after applying rejection rules."

    best = max(candidates, key=lambda e: e.target_score)

    reason_parts = [f"Highest target score ({best.target_score:.1f}) among {len(candidates)} candidates."]
    if any(kw in _normalize(best.name) for kw in METRIC_KEYWORDS):
        reason_parts.append("Column name matches known business metric keywords.")
    if best.non_null_pct >= 0.95:
        reason_parts.append(f"High data completeness ({best.non_null_pct:.0%} non-null).")

    return best.name, " ".join(reason_parts)


# ─────────────────────────────────────────────────────────────────
# Step 6: dimension selection
# ─────────────────────────────────────────────────────────────────

def _select_dimensions(
    entries: list[ColumnEntry],
    target: Optional[str],
    q: str,
    question_mode: str,
    planner_drivers: list[str],
    max_supporting: int,
) -> tuple[Optional[str], str, list[str], list[str]]:

    candidates = [
        e for e in entries
        if e.semantic_type == "categorical"
        and not e.rejected
        and e.name != target
    ]

    if not candidates:
        return None, "No categorical columns available for grouping.", [], []

    # Sort by headline score
    ranked = sorted(candidates, key=lambda e: e.headline_dim_score, reverse=True)

    headline = ranked[0]
    headline_parts = [
        f"Highest headline dimension score ({headline.headline_dim_score:.1f}) "
        f"among {len(candidates)} categorical columns.",
    ]
    if headline.unique_count <= 10:
        headline_parts.append(f"Low cardinality ({headline.unique_count} groups) — good for primary comparison.")
    if headline.name in planner_drivers:
        headline_parts.append("Also nominated by PlannerAgent.")
    if question_mode == "overview" and any(kw in _normalize(headline.name) for kw in CATEGORY_KEYWORDS):
        headline_parts.append("Recognised business dimension for overview context.")

    headline_why = " ".join(headline_parts)

    # Supporting dimensions: next ranked, excluding headline, capped at max_supporting
    supporting = []
    supporting_why = []

    for e in ranked[1:]:
        if len(supporting) >= max_supporting:
            break
        supporting.append(e.name)

        parts = [f"Supporting dimension score: {e.supporting_dim_score:.1f}."]
        if e.name in planner_drivers:
            parts.append("Nominated by PlannerAgent.")
        if any(kw in _normalize(e.name) for kw in CATEGORY_KEYWORDS):
            parts.append("Recognised business dimension keyword.")
        supporting_why.append(" ".join(parts))

    return headline.name, headline_why, supporting, supporting_why


# ─────────────────────────────────────────────────────────────────
# Step 7: time column selection
# ─────────────────────────────────────────────────────────────────

def _select_time_column(
    registry: list[ColumnEntry],
    q: str,
) -> tuple[Optional[str], str]:

    candidates = [e for e in registry if e.semantic_type == "datetime" and not e.rejected]

    if not candidates:
        return None, "No datetime columns detected in the dataset."

    best = max(candidates, key=lambda e: e.time_score)

    why_parts = [f"Highest time column score ({best.time_score:.1f})."]
    if "date" in _normalize(best.name):
        why_parts.append("Column name explicitly contains 'date'.")
    if best.non_null_pct >= 0.95:
        why_parts.append(f"High completeness ({best.non_null_pct:.0%} non-null).")

    return best.name, " ".join(why_parts)


# ─────────────────────────────────────────────────────────────────
# Step 8: row filter explanation
# ─────────────────────────────────────────────────────────────────

def _row_filter_explanation(
    df: pd.DataFrame,
    target: Optional[str],
) -> tuple[bool, str]:

    if not target or target not in df.columns:
        return False, "No row filtering applied — target column not confirmed."

    null_count = int(df[target].isna().sum())
    total = len(df)

    if null_count == 0:
        return False, f"No row filtering needed — {target} has complete coverage ({total:,} rows)."

    pct = null_count / total * 100
    return True, (
        f"Rows where {target} is null are excluded from aggregation ({null_count:,} rows, "
        f"{pct:.1f}% of total). These rows remain in profile counts."
    )


# ─────────────────────────────────────────────────────────────────
# Step 9: confidence assessment
# ─────────────────────────────────────────────────────────────────

def _assess_confidence(
    target: Optional[str],
    headline_dim: Optional[str],
    good_entries: list[ColumnEntry],
    df: pd.DataFrame,
    question_mode: str,
) -> tuple[str, str]:

    penalties = 0

    if not target:
        penalties += 3
    else:
        target_entry = next((e for e in good_entries if e.name == target), None)
        if target_entry:
            if target_entry.non_null_pct < 0.70:
                penalties += 2
            if target_entry.semantic_type != "metric":
                penalties += 1

    if not headline_dim:
        penalties += 2

    if question_mode == "overview":
        penalties += 1  # overview inherently lower single-answer confidence

    usable_metrics = sum(1 for e in good_entries if e.semantic_type == "metric")
    if usable_metrics < 2:
        penalties += 1

    if penalties == 0:
        return "high", "Target and headline dimension are both well-supported by the data."
    if penalties <= 2:
        return "medium", "Analysis is solid for directional insight but some constraints apply — see explanation."
    return "low", "Multiple data-quality or schema gaps reduce confidence. Treat output as exploratory."


# ─────────────────────────────────────────────────────────────────
# Convenience helpers for downstream consumers
# ─────────────────────────────────────────────────────────────────

def get_all_selected_columns(result: SelectionResult) -> list[str]:
    """Return all columns that were positively selected (for chart/KPI use)."""
    cols = []
    if result.target:
        cols.append(result.target)
    if result.headline_dimension:
        cols.append(result.headline_dimension)
    cols.extend(result.supporting_dimensions)
    if result.time_column:
        cols.append(result.time_column)
    return list(dict.fromkeys(cols))  # dedupe, preserve order


def is_overview_mode(result: SelectionResult) -> bool:
    return result.question_mode == "overview"


def format_explanation_for_ui(result: SelectionResult) -> dict:
    """
    Returns a dict ready to be embedded in the pipeline output
    for display in the frontend explanation panel.
    """
    return {
        "question_mode": result.question_mode,
        "target": {
            "column": result.target,
            "reason": result.target_why,
        },
        "headline_dimension": {
            "column": result.headline_dimension,
            "reason": result.headline_dimension_why,
        },
        "supporting_dimensions": [
            {"column": col, "reason": why}
            for col, why in zip(result.supporting_dimensions, result.supporting_dimensions_why)
        ],
        "time_column": {
            "column": result.time_column,
            "reason": result.time_column_why,
        },
        "rejected_columns": [
            {"column": col, "reason": reason}
            for col, reason in result.rejected_columns.items()
        ],
        "row_filter": {
            "applied": result.row_filter_applied,
            "reason": result.row_filter_why,
        },
        "confidence": result.confidence,
        "confidence_note": result.confidence_note,
    }


# ─────────────────────────────────────────────────────────────────
# Internal utilities
# ─────────────────────────────────────────────────────────────────

def _normalize(text: str) -> str:
    text = str(text or "").strip().lower()
    text = re.sub(r"[_\-/]+", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text