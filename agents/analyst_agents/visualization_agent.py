import math
import pandas as pd


class VisualizationAgent:

    def run(
        self,
        df,
        target,
        question="",
        intent="general_analysis",
        drivers=None,
        time_column=None,
        aggregation="sum",
        preferred_chart="table",
        plan=None
    ):
        charts = []

        if target not in df.columns:
            return charts

        working_df = self._prepare_dataframe(df.copy(), target)
        working_df = working_df.dropna(subset=[target])

        if len(working_df) == 0:
            return charts

        numeric_cols = working_df.select_dtypes(include=["int64", "float64", "int32", "float32"]).columns.tolist()
        categorical_cols = working_df.select_dtypes(include=["object"]).columns.tolist()
        datetime_cols = working_df.select_dtypes(include=["datetime64[ns]"]).columns.tolist()

        q = (question or "").lower().strip()
        drivers = drivers or []
        aggregation = normalize_aggregation(aggregation)

        if time_column not in working_df.columns or time_column not in datetime_cols:
            time_column = datetime_cols[0] if datetime_cols else None

        chart_plan = self._plan_visuals(
            df=working_df,
            question=q,
            intent=intent,
            target=target,
            drivers=drivers,
            numeric_cols=numeric_cols,
            categorical_cols=categorical_cols,
            datetime_cols=datetime_cols,
            time_column=time_column,
            aggregation=aggregation,
            preferred_chart=preferred_chart,
            plan=plan or {}
        )

        for idx, item in enumerate(chart_plan):
            try:
                option = None
                chart_type = item["type"]
                title = item["title"]
                description = item["description"]
                role = item.get("role", "supporting")

                if chart_type == "bar":
                    option = self._build_bar_option(
                        working_df,
                        category_col=item["category_col"],
                        target=target,
                        agg=item.get("agg", aggregation),
                        limit=item.get("limit", 10)
                    )

                elif chart_type == "line":
                    option = self._build_time_series_option(
                        working_df,
                        date_col=item["date_col"],
                        target=target,
                        freq=item.get("freq", "M"),
                        agg=item.get("agg", aggregation)
                    )

                elif chart_type == "donut":
                    option = self._build_donut_option(
                        working_df,
                        category_col=item["category_col"],
                        target=target,
                        agg=item.get("agg", aggregation),
                        limit=item.get("limit", 6)
                    )

                elif chart_type == "scatter":
                    option = self._build_scatter_option(
                        working_df,
                        x_col=item["x_col"],
                        y_col=target
                    )

                elif chart_type == "histogram":
                    option = self._build_histogram_option(
                        working_df,
                        target=target
                    )

                if option is None:
                    continue

                charts.append({
                    "type": chart_type,
                    "title": title,
                    "description": description,
                    "role": role,
                    "primary": role == "primary" or idx == 0,
                    "option": option
                })

            except Exception as e:
                print(f"Visualization error for {item}: {e}")

        return charts[:4]

    def _plan_visuals(
        self,
        df,
        question,
        intent,
        target,
        drivers,
        numeric_cols,
        categorical_cols,
        datetime_cols,
        time_column,
        aggregation,
        preferred_chart,
        plan
    ):
        plans = []

        best_cat = choose_best_category_column(df, categorical_cols, question, drivers)
        second_cat = choose_second_category_column(df, categorical_cols, question, drivers, best_cat)
        best_num = choose_best_numeric_driver(df, numeric_cols, target)

        has_time = bool(time_column)
        freq = infer_frequency_from_question(question, df, time_column)

        wants_trend = intent == "trend_analysis" or any(
            token in question for token in ["trend", "over time", "monthly", "weekly", "daily", "timeline", "growth", "quarterly", "yearly"]
        )
        wants_compare = intent == "comparison" or any(
            token in question for token in ["compare", "comparison", "versus", "vs", "higher", "lower"]
        )
        wants_distribution = intent == "distribution_analysis" or any(
            token in question for token in ["distribution", "spread", "outlier", "variance", "range", "histogram"]
        )
        wants_relationship = intent == "relationship_analysis" or any(
            token in question for token in ["relationship", "correlation", "impact", "influence", "driver"]
        )
        wants_ranking = intent == "ranking_analysis" or any(
            token in question for token in ["top", "best", "highest", "lowest", "rank", "ranking", "bottom"]
        )

        planner_primary = normalize_chart_type(preferred_chart)

        # PRIMARY
        if wants_trend and has_time:
            plans.append({
                "type": "line",
                "date_col": time_column,
                "freq": freq,
                "agg": aggregation,
                "title": f"{format_label(target)} over time",
                "description": f"This is the primary answer chart. It shows how {format_label(target).lower()} changes over time so the overall direction is immediately clear.",
                "role": "primary"
            })

        elif planner_primary == "scatter" and best_num:
            plans.append({
                "type": "scatter",
                "x_col": best_num,
                "title": f"{format_label(best_num)} vs {format_label(target)}",
                "description": f"This is the primary answer chart. It tests whether {format_label(best_num).lower()} visibly moves with {format_label(target).lower()}.",
                "role": "primary"
            })

        elif planner_primary == "histogram":
            plans.append({
                "type": "histogram",
                "title": f"Distribution of {format_label(target)}",
                "description": f"This is the primary answer chart. It shows the overall distribution of {format_label(target).lower()} across the dataset.",
                "role": "primary"
            })

        elif wants_relationship and best_num:
            plans.append({
                "type": "scatter",
                "x_col": best_num,
                "title": f"{format_label(best_num)} vs {format_label(target)}",
                "description": f"This is the primary answer chart. It tests whether {format_label(best_num).lower()} visibly moves with {format_label(target).lower()}.",
                "role": "primary"
            })

        elif best_cat:
            primary_agg = aggregation if aggregation in {"sum", "mean", "median", "count"} else "sum"

            plans.append({
                "type": "bar",
                "category_col": best_cat,
                "agg": primary_agg,
                "limit": 10,
                "title": f"{format_label(target)} by {format_label(best_cat)}",
                "description": f"This is the primary answer chart. It shows how {format_label(target).lower()} differs across the most relevant grouping.",
                "role": "primary"
            })

        else:
            plans.append({
                "type": "histogram",
                "title": f"Distribution of {format_label(target)}",
                "description": f"This is the primary answer chart. It shows the overall distribution of {format_label(target).lower()} across the dataset.",
                "role": "primary"
            })

        # SUPPORTING 1
        if has_time and not any(p["type"] == "line" for p in plans):
            plans.append({
                "type": "line",
                "date_col": time_column,
                "freq": freq,
                "agg": aggregation,
                "title": f"Trend of {format_label(target)} over time",
                "description": f"This supporting chart adds time context so you can see whether the pattern is stable, rising, falling, or driven by spikes.",
                "role": "supporting"
            })
        elif best_cat and not any(p["type"] == "bar" and p.get("category_col") == best_cat for p in plans):
            plans.append({
                "type": "bar",
                "category_col": best_cat,
                "agg": aggregation,
                "limit": 8,
                "title": f"Top {format_label(best_cat)} contributors",
                "description": f"This supporting chart highlights the leading groups contributing most to {format_label(target).lower()}.",
                "role": "supporting"
            })
        elif second_cat:
            plans.append({
                "type": "bar",
                "category_col": second_cat,
                "agg": aggregation,
                "limit": 8,
                "title": f"{format_label(target)} by {format_label(second_cat)}",
                "description": f"This supporting chart provides a second grouping view to explain where performance is concentrated.",
                "role": "supporting"
            })

        # SUPPORTING 2
        if best_cat and not wants_distribution:
            plans.append({
                "type": "donut",
                "category_col": best_cat,
                "agg": "sum" if aggregation not in {"count", "mean", "median"} else aggregation,
                "limit": 6,
                "title": f"Share of {format_label(target)} by {format_label(best_cat)}",
                "description": f"This supporting chart shows how concentrated {format_label(target).lower()} is across the main grouping dimension.",
                "role": "supporting"
            })
        elif best_num and not any(p["type"] == "scatter" for p in plans):
            plans.append({
                "type": "scatter",
                "x_col": best_num,
                "title": f"{format_label(best_num)} compared with {format_label(target)}",
                "description": f"This supporting chart checks whether the strongest numeric field appears to move with the target metric.",
                "role": "supporting"
            })
        else:
            plans.append({
                "type": "histogram",
                "title": f"Distribution view of {format_label(target)}",
                "description": f"This supporting chart shows spread, concentration, and value clustering in the target metric.",
                "role": "supporting"
            })

        # DIAGNOSTIC
        if wants_distribution or not any(p["type"] == "histogram" for p in plans):
            plans.append({
                "type": "histogram",
                "title": f"Diagnostic distribution of {format_label(target)}",
                "description": f"This diagnostic chart helps assess spread, skew, and possible outliers in {format_label(target).lower()}.",
                "role": "diagnostic"
            })
        elif best_num and not any(p["type"] == "scatter" for p in plans):
            plans.append({
                "type": "scatter",
                "x_col": best_num,
                "title": f"Diagnostic view: {format_label(best_num)} vs {format_label(target)}",
                "description": f"This diagnostic chart helps validate whether the strongest numeric field has a visible relationship with the target.",
                "role": "diagnostic"
            })

        deduped = []
        seen = set()

        for plan_item in plans:
            key = (
                plan_item["type"],
                plan_item.get("category_col"),
                plan_item.get("date_col"),
                plan_item.get("x_col"),
                plan_item.get("agg"),
                plan_item.get("freq")
            )
            if key not in seen:
                deduped.append(plan_item)
                seen.add(key)

        while len(deduped) < 4:
            deduped.append({
                "type": "histogram",
                "title": f"Additional diagnostic view of {format_label(target)}",
                "description": f"This additional chart helps confirm the overall shape of {format_label(target).lower()} across the dataset.",
                "role": "supporting"
            })

        return deduped[:4]

    def _prepare_dataframe(self, df, target):
        if target in df.columns and not pd.api.types.is_numeric_dtype(df[target]):
            df[target] = pd.to_numeric(df[target], errors="coerce")
        return df

    def _build_bar_option(self, df, category_col, target, agg="sum", limit=10):
        grouped_series = (
            df.groupby(category_col, dropna=False)[target]
            .agg(agg)
            .sort_values(ascending=False)
            .head(limit)
        )

        categories = [safe_label(v) for v in grouped_series.index.tolist()]
        values = [round(float(v), 2) for v in grouped_series.values.tolist()]

        return {
            "tooltip": {"trigger": "axis"},
            "grid": {"left": 70, "right": 30, "top": 50, "bottom": 95},
            "xAxis": {
                "type": "category",
                "data": categories,
                "axisLabel": {
                    "interval": 0,
                    "rotate": 25,
                    "formatter": {"function": "function(value){ return truncateLabel(value, 16); }"}
                }
            },
            "yAxis": {
                "type": "value",
                "axisLabel": {
                    "formatter": {"function": "function(value){ return compactAxis(value); }"}
                }
            },
            "series": [{
                "type": "bar",
                "data": values,
                "barMaxWidth": 48,
                "itemStyle": {"borderRadius": [6, 6, 0, 0]}
            }]
        }

    def _build_time_series_option(self, df, date_col, target, freq="M", agg="sum"):
        working = df.dropna(subset=[date_col, target]).copy()

        if working.empty:
            return None

        period_code = freq if freq in {"D", "W", "M", "Q", "Y"} else "M"
        working["_period"] = working[date_col].dt.to_period(period_code).astype(str)

        agg = normalize_aggregation(agg)
        if agg == "mean":
            grouped = working.groupby("_period")[target].mean().reset_index()
        elif agg == "median":
            grouped = working.groupby("_period")[target].median().reset_index()
        elif agg == "count":
            grouped = working.groupby("_period")[target].count().reset_index()
        else:
            grouped = working.groupby("_period")[target].sum().reset_index()

        grouped = grouped.sort_values("_period")

        return {
            "tooltip": {"trigger": "axis"},
            "grid": {"left": 70, "right": 30, "top": 50, "bottom": 75},
            "xAxis": {
                "type": "category",
                "data": grouped["_period"].tolist(),
                "axisLabel": {
                    "rotate": 25,
                    "formatter": {"function": "function(value){ return truncateLabel(value, 14); }"}
                }
            },
            "yAxis": {
                "type": "value",
                "axisLabel": {
                    "formatter": {"function": "function(value){ return compactAxis(value); }"}
                }
            },
            "series": [{
                "type": "line",
                "data": [round(float(v), 2) for v in grouped[target].tolist()],
                "smooth": True,
                "symbol": "circle",
                "symbolSize": 7,
                "lineStyle": {"width": 3},
                "areaStyle": {"opacity": 0.08}
            }]
        }

    def _build_donut_option(self, df, category_col, target, agg="sum", limit=6):
        grouped = (
            df.groupby(category_col, dropna=False)[target]
            .agg(agg)
            .sort_values(ascending=False)
            .head(limit)
        )

        series_data = [
            {"name": safe_label(idx), "value": round(float(val), 2)}
            for idx, val in grouped.items()
        ]

        return {
            "tooltip": {"trigger": "item"},
            "legend": {
                "bottom": 0,
                "type": "scroll"
            },
            "series": [{
                "type": "pie",
                "radius": ["45%", "70%"],
                "avoidLabelOverlap": True,
                "data": series_data,
                "label": {"formatter": "{b}: {d}%"}
            }]
        }

    def _build_scatter_option(self, df, x_col, y_col):
        working = df.dropna(subset=[x_col, y_col]).copy()

        if len(working) == 0:
            return None

        if len(working) > 300:
            working = working.sample(300, random_state=42)

        points = [
            [round(float(x), 2), round(float(y), 2)]
            for x, y in zip(working[x_col], working[y_col])
        ]

        return {
            "tooltip": {"trigger": "item"},
            "grid": {"left": 70, "right": 30, "top": 50, "bottom": 75},
            "xAxis": {
                "type": "value",
                "name": format_label(x_col),
                "nameLocation": "middle",
                "nameGap": 30,
                "axisLabel": {
                    "formatter": {"function": "function(value){ return compactAxis(value); }"}
                }
            },
            "yAxis": {
                "type": "value",
                "name": format_label(y_col),
                "nameLocation": "middle",
                "nameGap": 45,
                "axisLabel": {
                    "formatter": {"function": "function(value){ return compactAxis(value); }"}
                }
            },
            "series": [{
                "type": "scatter",
                "data": points,
                "symbolSize": 10
            }]
        }

    def _build_histogram_option(self, df, target):
        series = pd.to_numeric(df[target], errors="coerce").dropna()

        if len(series) == 0:
            return None

        bins = min(10, max(5, int(math.sqrt(len(series)))))
        bucketed = pd.cut(series, bins=bins, duplicates="drop")
        bucket_counts = bucketed.value_counts(sort=False)

        labels = []
        values = []

        for interval, count in bucket_counts.items():
            labels.append(f"{round(interval.left, 2)} to {round(interval.right, 2)}")
            values.append(int(count))

        return {
            "tooltip": {"trigger": "axis"},
            "grid": {"left": 70, "right": 30, "top": 50, "bottom": 105},
            "xAxis": {
                "type": "category",
                "data": labels,
                "axisLabel": {
                    "interval": 0,
                    "rotate": 30,
                    "formatter": {"function": "function(value){ return truncateLabel(value, 18); }"}
                }
            },
            "yAxis": {
                "type": "value"
            },
            "series": [{
                "type": "bar",
                "data": values,
                "barMaxWidth": 42,
                "itemStyle": {"borderRadius": [6, 6, 0, 0]}
            }]
        }


def choose_best_category_column(df, categorical_cols, question, drivers):
    driver_candidates = [d for d in (drivers or []) if d in categorical_cols]

    filtered = []
    for col in categorical_cols:
        nunique = int(df[col].nunique(dropna=True))
        if 1 < nunique <= min(20, max(6, int(len(df) * 0.5))):
            filtered.append(col)

    candidate_cols = filtered if filtered else categorical_cols

    for d in driver_candidates:
        if d in candidate_cols:
            return d

    preferred = ["product", "country", "region", "category", "segment", "channel", "customer"]
    for pref in preferred:
        for col in candidate_cols:
            if pref in col.lower():
                return col

    return candidate_cols[0] if candidate_cols else None


def choose_second_category_column(df, categorical_cols, question, drivers, first_choice):
    filtered = [c for c in categorical_cols if c != first_choice]

    preferred = ["region", "category", "segment", "channel", "customer", "country", "product"]
    for pref in preferred:
        for col in filtered:
            if pref in col.lower():
                return col

    return filtered[0] if filtered else None


def choose_best_numeric_driver(df, numeric_cols, target):
    usable = []
    for col in numeric_cols:
        if col == target:
            continue
        non_null = int(df[col].notna().sum())
        if non_null >= max(5, int(len(df) * 0.2)):
            usable.append(col)

    return usable[0] if usable else None


def infer_frequency_from_question(question, df, time_column):
    q = (question or "").lower()

    if "daily" in q or "day" in q:
        return "D"
    if "weekly" in q or "week" in q:
        return "W"
    if "quarterly" in q or "quarter" in q:
        return "Q"
    if "yearly" in q or "year" in q:
        return "Y"
    if "monthly" in q or "month" in q:
        return "M"

    if not time_column or time_column not in df.columns:
        return "M"

    series = df[time_column].dropna().sort_values()
    if len(series) < 2:
        return "M"

    try:
        gaps = series.diff().dropna().dt.days
        if len(gaps) == 0:
            return "M"
        median_gap = gaps.median()
        if median_gap <= 2:
            return "D"
        if median_gap <= 10:
            return "W"
        if median_gap <= 45:
            return "M"
        if median_gap <= 120:
            return "Q"
        return "Y"
    except Exception:
        return "M"


def normalize_aggregation(aggregation):
    value = str(aggregation or "sum").lower().strip()
    mapping = {
        "avg": "mean",
        "average": "mean",
        "mean": "mean",
        "sum": "sum",
        "median": "median",
        "count": "count",
        "none": "sum"
    }
    return mapping.get(value, "sum")


def normalize_chart_type(chart_type):
    value = str(chart_type or "").lower().strip()
    mapping = {
        "line": "line",
        "bar": "bar",
        "scatter": "scatter",
        "histogram": "histogram",
        "box": "histogram",
        "area": "line",
        "heatmap": "bar",
        "table": "bar"
    }
    return mapping.get(value, "bar")

def format_label(value):
    return str(value).replace("_", " ").strip()


def safe_label(value):
    if pd.isna(value):
        return "Unknown"
    return str(value)


def truncate_label(value, max_len=16):
    value = str(value)
    return value if len(value) <= max_len else value[:max_len - 1] + "…"