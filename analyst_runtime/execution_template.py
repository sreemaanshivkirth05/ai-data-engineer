from __future__ import annotations

from typing import Dict, Any, List, Tuple
import math

import pandas as pd
import numpy as np


def _safe_copy(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    return out


def _coerce_numeric(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce")


def _prepare_datetime(series: pd.Series) -> pd.Series:
    return pd.to_datetime(series, errors="coerce")


def _aggregate_series(grouped: pd.core.groupby.generic.DataFrameGroupBy, target: str, aggregation: str) -> pd.Series:
    if aggregation == "sum":
        return grouped[target].sum()
    if aggregation == "mean":
        return grouped[target].mean()
    if aggregation == "median":
        return grouped[target].median()
    if aggregation == "count":
        return grouped[target].count()
    return grouped[target].sum()


def _format_period(series: pd.Series, grain: str) -> pd.Series:
    if grain == "month":
        return series.dt.to_period("M").astype(str)
    if grain == "quarter":
        return series.dt.to_period("Q").astype(str)
    if grain == "year":
        return series.dt.to_period("Y").astype(str)
    if grain == "week":
        return series.dt.to_period("W").astype(str)
    return series.dt.date.astype(str)


def build_dataset_summary(df: pd.DataFrame, target_metric: str | None, question_type: str) -> Dict[str, Any]:
    numeric_columns = df.select_dtypes(include=[np.number]).columns.tolist()
    datetime_columns = df.select_dtypes(include=["datetime64[ns]", "datetime64[ns, UTC]"]).columns.tolist()
    categorical_columns = [c for c in df.columns if c not in numeric_columns and c not in datetime_columns]

    date_range_start = None
    date_range_end = None
    if datetime_columns:
        time_col = datetime_columns[0]
        if df[time_col].dropna().shape[0] > 0:
            date_range_start = str(df[time_col].dropna().min().date())
            date_range_end = str(df[time_col].dropna().max().date())

    return {
        "row_count": int(len(df)),
        "column_count": int(len(df.columns)),
        "target_metric": target_metric,
        "analysis_type": question_type,
        "numeric_column_count": len(numeric_columns),
        "categorical_column_count": len(categorical_columns),
        "datetime_column_count": len(datetime_columns),
        "date_range_start": date_range_start,
        "date_range_end": date_range_end,
        "driver_columns": categorical_columns[:5],
    }


def build_data_quality_summary(df: pd.DataFrame, target_metric: str | None) -> Dict[str, Any]:
    total_cells = max(1, df.shape[0] * df.shape[1])
    overall_missing_pct = round(float(df.isna().sum().sum()) / total_cells * 100, 2)
    duplicate_rows = int(df.duplicated().sum())

    target_null_pct = None
    if target_metric and target_metric in df.columns:
        target_null_pct = round(float(df[target_metric].isna().mean()) * 100, 2)

    confidence_level = "High"
    confidence_note = "The result is based on deterministic computation over the uploaded dataset."
    if overall_missing_pct > 10 or duplicate_rows > 0:
        confidence_level = "Medium"
        confidence_note = "Some missingness or duplicate presence may affect interpretation."
    if overall_missing_pct > 20:
        confidence_level = "Low"
        confidence_note = "High missingness reduces confidence in the computed output."

    high_cardinality_columns = []
    for col in df.columns:
        if df[col].dtype == object:
            unique_count = int(df[col].nunique(dropna=True))
            if unique_count > min(50, max(10, len(df) // 10)):
                high_cardinality_columns.append({
                    "column": col,
                    "unique_values": unique_count
                })

    date_range = None
    datetime_columns = df.select_dtypes(include=["datetime64[ns]", "datetime64[ns, UTC]"]).columns.tolist()
    if datetime_columns:
        col = datetime_columns[0]
        cleaned = df[col].dropna()
        if len(cleaned) > 0:
            date_range = {
                "start": str(cleaned.min().date()),
                "end": str(cleaned.max().date()),
            }

    return {
        "overall_missing_pct": overall_missing_pct,
        "duplicate_rows": duplicate_rows,
        "target_null_pct": target_null_pct,
        "confidence_level": confidence_level,
        "confidence_note": confidence_note,
        "high_cardinality_columns": high_cardinality_columns[:5],
        "date_range": date_range,
    }


def _make_bar_chart(title: str, x: List[Any], y: List[float], x_name: str, y_name: str) -> Dict[str, Any]:
    return {
        "title": title,
        "primary": True,
        "role": "primary",
        "description": f"{title} shown as a ranked bar chart.",
        "option": {
            "tooltip": {"trigger": "axis"},
            "xAxis": {
                "type": "category",
                "data": [str(v) for v in x],
                "axisLabel": {"rotate": 25}
            },
            "yAxis": {
                "type": "value",
                "name": y_name
            },
            "series": [{
                "type": "bar",
                "data": [None if pd.isna(v) else float(v) for v in y],
                "name": y_name
            }]
        }
    }


def _make_line_chart(title: str, x: List[Any], y: List[float], x_name: str, y_name: str) -> Dict[str, Any]:
    return {
        "title": title,
        "primary": True,
        "role": "primary",
        "description": f"{title} shown as a time-series line chart.",
        "option": {
            "tooltip": {"trigger": "axis"},
            "xAxis": {"type": "category", "data": [str(v) for v in x]},
            "yAxis": {"type": "value", "name": y_name},
            "series": [{
                "type": "line",
                "data": [None if pd.isna(v) else float(v) for v in y],
                "name": y_name,
                "smooth": True
            }]
        }
    }


def _make_donut_chart(title: str, labels: List[Any], values: List[float]) -> Dict[str, Any]:
    return {
        "title": title,
        "primary": True,
        "role": "primary",
        "description": f"{title} shown as a contribution chart.",
        "option": {
            "tooltip": {"trigger": "item"},
            "legend": {"top": "bottom"},
            "series": [{
                "type": "pie",
                "radius": ["45%", "70%"],
                "data": [
                    {"name": str(label), "value": 0 if pd.isna(val) else float(val)}
                    for label, val in zip(labels, values)
                ]
            }]
        }
    }


def execute_ranking(df: pd.DataFrame, target: str, group_by: str, aggregation: str, limit: int, sort: str) -> Dict[str, Any]:
    work = _safe_copy(df)
    work[target] = _coerce_numeric(work[target])
    work = work.dropna(subset=[target, group_by])

    grouped = work.groupby(group_by, dropna=False)
    agg_series = _aggregate_series(grouped, target, aggregation).sort_values(ascending=(sort == "asc"))

    result_df = agg_series.head(limit).reset_index()
    result_df.columns = [group_by, target]

    charts = [
        _make_bar_chart(
            title=f"{'Bottom' if sort == 'asc' else 'Top'} {limit} {group_by} by {aggregation} of {target}",
            x=result_df[group_by].tolist(),
            y=result_df[target].tolist(),
            x_name=group_by,
            y_name=target,
        )
    ]

    return {
        "result_table": result_df.to_dict(orient="records"),
        "top_results": result_df.to_dict(orient="records"),
        "top_entity": result_df.iloc[0][group_by] if len(result_df) else None,
        "top_value": float(result_df.iloc[0][target]) if len(result_df) else None,
        "charts": charts,
    }


def execute_trend(df: pd.DataFrame, target: str, time_column: str, aggregation: str, grain: str) -> Dict[str, Any]:
    work = _safe_copy(df)
    work[target] = _coerce_numeric(work[target])
    work[time_column] = _prepare_datetime(work[time_column])
    work = work.dropna(subset=[target, time_column])

    work["_period"] = _format_period(work[time_column], grain)
    grouped = work.groupby("_period", dropna=False)
    agg_series = _aggregate_series(grouped, target, aggregation).sort_index()

    result_df = agg_series.reset_index()
    result_df.columns = ["period", target]

    best_idx = result_df[target].idxmax() if len(result_df) else None
    worst_idx = result_df[target].idxmin() if len(result_df) else None

    first_val = float(result_df.iloc[0][target]) if len(result_df) else None
    last_val = float(result_df.iloc[-1][target]) if len(result_df) else None
    period_change_pct = None
    if first_val not in (None, 0) and last_val is not None:
        period_change_pct = round(((last_val - first_val) / first_val) * 100, 2)

    charts = [
        _make_line_chart(
            title=f"{grain.title()} trend of {aggregation} {target}",
            x=result_df["period"].tolist(),
            y=result_df[target].tolist(),
            x_name="period",
            y_name=target,
        )
    ]

    return {
        "result_table": result_df.to_dict(orient="records"),
        "time_series": result_df.to_dict(orient="records"),
        "best_period": result_df.iloc[best_idx]["period"] if best_idx is not None else None,
        "worst_period": result_df.iloc[worst_idx]["period"] if worst_idx is not None else None,
        "period_change_pct": period_change_pct,
        "charts": charts,
    }


def execute_comparison(df: pd.DataFrame, target: str, group_by: str, aggregation: str, sort: str, limit: int) -> Dict[str, Any]:
    work = _safe_copy(df)
    work[target] = _coerce_numeric(work[target])
    work = work.dropna(subset=[target, group_by])

    grouped = work.groupby(group_by, dropna=False)
    agg_series = _aggregate_series(grouped, target, aggregation).sort_values(ascending=(sort == "asc"))
    result_df = agg_series.head(limit).reset_index()
    result_df.columns = [group_by, target]

    difference = None
    if len(result_df) >= 2:
        difference = float(result_df.iloc[0][target]) - float(result_df.iloc[1][target])

    charts = [
        _make_bar_chart(
            title=f"Comparison of {group_by} by {aggregation} {target}",
            x=result_df[group_by].tolist(),
            y=result_df[target].tolist(),
            x_name=group_by,
            y_name=target,
        )
    ]

    return {
        "result_table": result_df.to_dict(orient="records"),
        "comparison_rows": result_df.to_dict(orient="records"),
        "difference_top_2": difference,
        "charts": charts,
    }


def execute_summary(df: pd.DataFrame, target: str | None) -> Dict[str, Any]:
    result: Dict[str, Any] = {
        "result_table": [],
        "charts": [],
    }

    if target and target in df.columns:
        work = _safe_copy(df)
        work[target] = _coerce_numeric(work[target])

        total_target = float(work[target].sum()) if work[target].notna().any() else None
        average_target = float(work[target].mean()) if work[target].notna().any() else None
        median_target = float(work[target].median()) if work[target].notna().any() else None
    else:
        total_target = None
        average_target = None
        median_target = None

    categorical_cols = [c for c in df.columns if df[c].dtype == object]
    top_dimension_name = None
    top_dimension_value = None
    top_dimension_metric = None

    if target and categorical_cols and target in df.columns:
        work = _safe_copy(df)
        work[target] = _coerce_numeric(work[target])
        valid_cats = [c for c in categorical_cols if df[c].nunique(dropna=True) <= max(20, len(df) // 2)]
        if valid_cats:
            best_col = valid_cats[0]
            grouped = work.groupby(best_col)[target].sum().sort_values(ascending=False)
            if len(grouped):
                top_dimension_name = best_col
                top_dimension_value = grouped.index[0]
                top_dimension_metric = float(grouped.iloc[0])

                plot_df = grouped.head(8).reset_index()
                plot_df.columns = [best_col, target]
                result["charts"] = [
                    _make_bar_chart(
                        title=f"Top {best_col} by total {target}",
                        x=plot_df[best_col].tolist(),
                        y=plot_df[target].tolist(),
                        x_name=best_col,
                        y_name=target,
                    )
                ]

    result["summary_stats"] = {
        "total_target": total_target,
        "average_target": average_target,
        "median_target": median_target,
        "top_dimension_name": top_dimension_name,
        "top_dimension_value": top_dimension_value,
        "top_dimension_metric": top_dimension_metric,
    }
    return result


def execute_contribution(df: pd.DataFrame, target: str, group_by: str, aggregation: str, limit: int) -> Dict[str, Any]:
    work = _safe_copy(df)
    work[target] = _coerce_numeric(work[target])
    work = work.dropna(subset=[target, group_by])

    grouped = _aggregate_series(work.groupby(group_by), target, aggregation).sort_values(ascending=False)
    total = float(grouped.sum()) if len(grouped) else 0.0

    result_df = grouped.head(limit).reset_index()
    result_df.columns = [group_by, target]
    result_df["share_pct"] = result_df[target].apply(lambda x: round((float(x) / total) * 100, 2) if total else 0.0)

    charts = [
        _make_donut_chart(
            title=f"Contribution of {group_by} to {target}",
            labels=result_df[group_by].tolist(),
            values=result_df[target].tolist(),
        )
    ]

    return {
        "result_table": result_df.to_dict(orient="records"),
        "contribution_rows": result_df.to_dict(orient="records"),
        "top_entity": result_df.iloc[0][group_by] if len(result_df) else None,
        "top_share_pct": float(result_df.iloc[0]["share_pct"]) if len(result_df) else None,
        "charts": charts,
    }


def execute_distribution(df: pd.DataFrame, target: str | None, group_by: str | None) -> Dict[str, Any]:
    if target and target in df.columns:
        work = _safe_copy(df)
        work[target] = _coerce_numeric(work[target])
        clean = work[target].dropna()

        stats = {
            "count": int(clean.shape[0]),
            "min": float(clean.min()) if len(clean) else None,
            "max": float(clean.max()) if len(clean) else None,
            "mean": float(clean.mean()) if len(clean) else None,
            "median": float(clean.median()) if len(clean) else None,
            "std": float(clean.std()) if len(clean) else None,
        }

        hist, bin_edges = np.histogram(clean, bins=min(10, max(5, int(math.sqrt(len(clean)))))) if len(clean) else ([], [])
        labels = []
        values = []
        if len(hist):
            for i in range(len(hist)):
                labels.append(f"{round(bin_edges[i], 2)} - {round(bin_edges[i+1], 2)}")
                values.append(int(hist[i]))

        charts = [
            _make_bar_chart(
                title=f"Distribution of {target}",
                x=labels,
                y=values,
                x_name="bin",
                y_name="count",
            )
        ]

        return {
            "result_table": [{"stat": k, "value": v} for k, v in stats.items()],
            "distribution_stats": stats,
            "charts": charts,
        }

    if group_by and group_by in df.columns:
        counts = df[group_by].fillna("Unknown").value_counts().head(10).reset_index()
        counts.columns = [group_by, "count"]

        charts = [
            _make_bar_chart(
                title=f"Distribution of {group_by}",
                x=counts[group_by].tolist(),
                y=counts["count"].tolist(),
                x_name=group_by,
                y_name="count",
            )
        ]

        return {
            "result_table": counts.to_dict(orient="records"),
            "distribution_rows": counts.to_dict(orient="records"),
            "charts": charts,
        }

    return {
        "result_table": [],
        "charts": [],
    }