import math
import pandas as pd


def build_phase1_product_layer(
    df,
    question,
    intent,
    target,
    drivers,
    kpis,
    analysis,
    charts,
    question_category=None,
    question_goal=None
):
    dataset_summary = build_dataset_summary(
        df=df,
        intent=intent,
        target=target,
        drivers=drivers,
        question_category=question_category,
        question_goal=question_goal
    )

    top_insights = build_top_insights(
        df=df,
        target=target,
        kpis=kpis,
        analysis=analysis,
        charts=charts
    )

    follow_up_questions = build_follow_up_questions(
        df=df,
        question=question,
        intent=intent,
        target=target,
        drivers=drivers,
        analysis=analysis
    )

    data_quality_summary = build_data_quality_summary(
        df=df,
        target=target
    )

    return {
        "dataset_summary": dataset_summary,
        "top_insights": top_insights,
        "follow_up_questions": follow_up_questions,
        "data_quality_summary": data_quality_summary
    }


def build_dataset_summary(df, intent, target, drivers, question_category=None, question_goal=None):
    numeric_cols = df.select_dtypes(include=["number"]).columns.tolist()
    categorical_cols = df.select_dtypes(include=["object"]).columns.tolist()
    datetime_cols = df.select_dtypes(include=["datetime64[ns]"]).columns.tolist()

    summary = {
        "row_count": int(len(df)),
        "column_count": int(len(df.columns)),
        "numeric_column_count": int(len(numeric_cols)),
        "categorical_column_count": int(len(categorical_cols)),
        "datetime_column_count": int(len(datetime_cols)),
        "target_metric": target,
        "analysis_type": question_category or intent,
        "question_goal": question_goal or "Understand the most important pattern in the uploaded dataset.",
        "driver_columns": drivers[:4] if drivers else [],
        "numeric_columns_preview": numeric_cols[:6],
        "categorical_columns_preview": categorical_cols[:6],
        "datetime_columns_preview": datetime_cols[:3]
    }

    if datetime_cols:
        date_col = datetime_cols[0]
        valid_dates = df[date_col].dropna()
        if len(valid_dates) > 0:
            summary["date_range_start"] = str(valid_dates.min().date())
            summary["date_range_end"] = str(valid_dates.max().date())

    return summary


def build_top_insights(df, target, kpis, analysis, charts):
    insights = []

    if kpis.get("top_dimension_name") and kpis.get("top_dimension_value"):
        insights.append({
            "title": "Top performer",
            "value": str(kpis["top_dimension_value"]),
            "detail": (
                f"The leading {str(kpis['top_dimension_name']).lower()} contributes "
                f"{format_number(kpis.get('top_dimension_metric'))} to {format_label(target).lower()}."
            ),
            "type": "positive"
        })

    correlations = analysis.get("correlations", {}) or {}
    if correlations:
        top_corr = sorted(correlations.items(), key=lambda x: abs(x[1]), reverse=True)[0]
        direction = "positive" if top_corr[1] > 0 else "negative"
        insights.append({
            "title": "Strongest numeric signal",
            "value": format_label(top_corr[0]),
            "detail": (
                f"This field shows the strongest {direction} relationship with "
                f"{format_label(target).lower()} (correlation: {top_corr[1]})."
            ),
            "type": "signal"
        })

    categorical_drivers = analysis.get("categorical_drivers", {}) or {}
    if categorical_drivers:
        top_cat = sorted(categorical_drivers.items(), key=lambda x: x[1], reverse=True)[0]
        insights.append({
            "title": "Biggest group variation",
            "value": format_label(top_cat[0]),
            "detail": (
                f"This is the clearest grouping dimension where performance differences are visible."
            ),
            "type": "pattern"
        })

    target_risk = compute_target_risk(df, target)
    insights.append({
        "title": "Main data caveat",
        "value": target_risk["label"],
        "detail": target_risk["detail"],
        "type": "risk"
    })

    if len(insights) < 4:
        insights.append({
            "title": "Chart coverage",
            "value": f"{len(charts)} visuals",
            "detail": "The answer includes a primary view plus supporting context for interpretation.",
            "type": "info"
        })

    return insights[:4]


def build_follow_up_questions(df, question, intent, target, drivers, analysis):
    suggestions = []
    target_label = format_label(target).lower() if target else "the target metric"

    categorical_cols = df.select_dtypes(include=["object"]).columns.tolist()
    datetime_cols = df.select_dtypes(include=["datetime64[ns]"]).columns.tolist()
    numeric_cols = df.select_dtypes(include=["number"]).columns.tolist()

    top_group = None
    if categorical_cols:
        top_group = choose_best_grouping(categorical_cols, drivers)

    strongest_signal = None
    correlations = analysis.get("correlations", {}) or {}
    if correlations:
        strongest_signal = sorted(correlations.items(), key=lambda x: abs(x[1]), reverse=True)[0][0]

    if datetime_cols:
        suggestions.append(f"How has {target_label} changed over time?")

    if top_group:
        suggestions.append(f"Which {format_label(top_group).lower()} segments are driving the highest {target_label}?")
        suggestions.append(f"Is {target_label} concentrated in a few {format_label(top_group).lower()} groups or broadly distributed?")

    if strongest_signal:
        suggestions.append(f"How does {format_label(strongest_signal).lower()} influence or move with {target_label}?")

    if intent in ["comparison", "ranking_analysis", "summary_analysis"]:
        suggestions.append(f"What explains the gap between the top and bottom performers for {target_label}?")

    if len(numeric_cols) > 1:
        suggestions.append(f"Are there outliers in {target_label} that are affecting the overall result?")

    deduped = []
    seen = set()
    for s in suggestions:
        key = s.lower().strip()
        if key not in seen:
            deduped.append(s)
            seen.add(key)

    return deduped[:5]


def build_data_quality_summary(df, target):
    row_count = len(df)
    column_count = len(df.columns)

    missing_pct = round(float(df.isna().mean().mean() * 100), 1) if row_count and column_count else 0.0
    duplicate_rows = int(df.duplicated().sum())

    target_null_pct = None
    usable_target_rows = None
    if target in df.columns:
        target_null_pct = round(float(df[target].isna().mean() * 100), 1)
        usable_target_rows = int(df[target].notna().sum())

    datetime_cols = df.select_dtypes(include=["datetime64[ns]"]).columns.tolist()
    date_range = None
    if datetime_cols:
        date_col = datetime_cols[0]
        valid_dates = df[date_col].dropna()
        if len(valid_dates) > 0:
            date_range = {
                "column": date_col,
                "start": str(valid_dates.min().date()),
                "end": str(valid_dates.max().date())
            }

    object_cols = df.select_dtypes(include=["object"]).columns.tolist()
    high_cardinality = []
    for col in object_cols:
        nunique = int(df[col].nunique(dropna=True))
        if nunique > max(25, int(len(df) * 0.5)):
            high_cardinality.append({
                "column": col,
                "unique_values": nunique
            })

    confidence = compute_confidence_note(
        missing_pct=missing_pct,
        duplicate_rows=duplicate_rows,
        target_null_pct=target_null_pct,
        usable_target_rows=usable_target_rows
    )

    return {
        "row_count": int(row_count),
        "column_count": int(column_count),
        "overall_missing_pct": missing_pct,
        "duplicate_rows": duplicate_rows,
        "target_null_pct": target_null_pct,
        "usable_target_rows": usable_target_rows,
        "date_range": date_range,
        "high_cardinality_columns": high_cardinality[:4],
        "confidence_note": confidence["note"],
        "confidence_level": confidence["level"]
    }


def compute_target_risk(df, target):
    if target not in df.columns:
        return {
            "label": "Target unclear",
            "detail": "The selected target metric could not be fully validated against the uploaded dataset."
        }

    target_null_pct = round(float(df[target].isna().mean() * 100), 1)
    usable_rows = int(df[target].notna().sum())

    if target_null_pct > 20:
        return {
            "label": "High missingness",
            "detail": f"{target_null_pct}% of the target values are missing, which can reduce confidence in the result."
        }

    if usable_rows < 20:
        return {
            "label": "Small usable sample",
            "detail": "The usable number of rows for the target is small, so findings should be treated as directional."
        }

    duplicate_rows = int(df.duplicated().sum())
    if duplicate_rows > 0:
        return {
            "label": "Duplicate rows detected",
            "detail": f"{duplicate_rows} duplicate rows were found and may affect aggregate totals if they are not expected."
        }

    return {
        "label": "Good analytical coverage",
        "detail": "The target metric has enough usable data for a solid descriptive readout."
    }


def compute_confidence_note(missing_pct, duplicate_rows, target_null_pct, usable_target_rows):
    penalties = 0

    if missing_pct >= 20:
        penalties += 2
    elif missing_pct >= 10:
        penalties += 1

    if duplicate_rows > 0:
        penalties += 1

    if target_null_pct is not None:
        if target_null_pct >= 20:
            penalties += 2
        elif target_null_pct >= 10:
            penalties += 1

    if usable_target_rows is not None and usable_target_rows < 20:
        penalties += 2
    elif usable_target_rows is not None and usable_target_rows < 50:
        penalties += 1

    if penalties <= 1:
        return {
            "level": "High",
            "note": "The dataset looks strong enough for descriptive business analysis and the target metric has usable coverage."
        }
    if penalties <= 3:
        return {
            "level": "Medium",
            "note": "The analysis is usable for directional insight, but some data-quality issues should be considered before making important decisions."
        }
    return {
        "level": "Low",
        "note": "The current output is best treated as an exploratory readout because missingness, duplicates, or limited usable rows reduce confidence."
    }


def choose_best_grouping(categorical_cols, drivers):
    for driver in drivers or []:
        if driver in categorical_cols:
            return driver

    priorities = ["product", "country", "region", "category", "segment", "channel", "customer"]
    for pref in priorities:
        for col in categorical_cols:
            if pref in col.lower():
                return col

    return categorical_cols[0] if categorical_cols else None


def format_number(value):
    if value is None:
        return "N/A"
    try:
        value = float(value)
        abs_value = abs(value)

        if abs_value >= 1_000_000_000:
            return f"{value / 1_000_000_000:.2f}B"
        if abs_value >= 1_000_000:
            return f"{value / 1_000_000:.2f}M"
        if abs_value >= 1_000:
            return f"{value / 1_000:.2f}K"
        if float(value).is_integer():
            return f"{int(value):,}"
        return f"{value:,.2f}"
    except Exception:
        return str(value)


def format_label(value):
    return str(value).replace("_", " ").strip()