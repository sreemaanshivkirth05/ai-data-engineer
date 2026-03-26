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
        plan = plan or {}

        resolved_time_column = time_column if time_column in working_df.columns else None
        if not resolved_time_column and datetime_cols:
            resolved_time_column = datetime_cols[0]

        chart_plan = self._plan_visuals(
            df=working_df,
            question=q,
            intent=intent,
            target=target,
            drivers=drivers,
            numeric_cols=numeric_cols,
            categorical_cols=categorical_cols,
            datetime_cols=datetime_cols,
            time_column=resolved_time_column,
            aggregation=aggregation,
            preferred_chart=preferred_chart,
            plan=plan
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
                        agg=item.get("agg", "sum"),
                        limit=item.get("limit", 10),
                        sort_desc=item.get("sort_desc", True)
                    )

                elif chart_type == "line":
                    option = self._build_time_series_option(
                        working_df,
                        date_col=item["date_col"],
                        target=target,
                        freq=item.get("freq", "M"),
                        agg=item.get("agg", "sum")
                    )

                elif chart_type == "donut":
                    option = self._build_donut_option(
                        working_df,
                        category_col=item["category_col"],
                        target=target,
                        agg=item.get("agg", "sum"),
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

                elif chart_type == "box":
                    option = self._build_box_option(
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

        planner_chart = str(preferred_chart or "").strip().lower()
        planner_agg = normalize_aggregation(aggregation)
        has_time = bool(time_column)

        wants_trend = intent == "trend_analysis"
        wants_compare = intent in ["comparison", "ranking_analysis", "segment_analysis", "contribution_analysis"]
        wants_distribution = intent == "distribution_analysis"
        wants_relationship = intent == "relationship_analysis"

        # PRIMARY: obey planner first
        if planner_chart == "line" and has_time:
            plans.append({
                "type": "line",
                "date_col": time_column,
                "freq": infer_time_frequency(df, time_column),
                "agg": planner_agg,
                "title": f"{format_label(target)} over time",
                "description": f"This primary chart follows the planner decision and shows how {format_label(target).lower()} changes over time.",
                "role": "primary"
            })
        elif planner_chart == "scatter" and best_num:
            plans.append({
                "type": "scatter",
                "x_col": best_num,
                "title": f"{format_label(best_num)} vs {format_label(target)}",
                "description": f"This primary chart follows the planner decision and checks whether {format_label(best_num).lower()} visibly moves with {format_label(target).lower()}.",
                "role": "primary"
            })
        elif planner_chart == "histogram":
            plans.append({
                "type": "histogram",
                "title": f"Distribution of {format_label(target)}",
                "description": f"This primary chart follows the planner decision and shows the distribution of {format_label(target).lower()}.",
                "role": "primary"
            })
        elif planner_chart == "box":
            plans.append({
                "type": "box",
                "title": f"Box view of {format_label(target)}",
                "description": f"This primary chart follows the planner decision and highlights spread, skew, and outliers in {format_label(target).lower()}.",
                "role": "primary"
            })
        elif planner_chart == "bar" and best_cat:
            plans.append({
                "type": "bar",
                "category_col": best_cat,
                "agg": planner_agg,
                "limit": 10,
                "title": f"{format_label(target)} by {format_label(best_cat)}",
                "description": f"This primary chart follows the planner decision and compares {format_label(target).lower()} across the most relevant grouping.",
                "role": "primary"
            })

        # fallback primary if planner chart not usable
        if not plans:
            if wants_trend and has_time:
                plans.append({
                    "type": "line",
                    "date_col": time_column,
                    "freq": infer_time_frequency(df, time_column),
                    "agg": planner_agg,
                    "title": f"{format_label(target)} over time",
                    "description": f"This is the primary answer chart. It shows how {format_label(target).lower()} changes over time.",
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
            elif wants_distribution:
                plans.append({
                    "type": "histogram",
                    "title": f"Distribution of {format_label(target)}",
                    "description": f"This is the primary answer chart. It shows the spread of {format_label(target).lower()} across the dataset.",
                    "role": "primary"
                })
            elif best_cat:
                plans.append({
                    "type": "bar",
                    "category_col": best_cat,
                    "agg": planner_agg,
                    "limit": 10,
                    "title": f"{format_label(target)} by {format_label(best_cat)}",
                    "description": f"This is the primary answer chart. It shows how {format_label(target).lower()} differs across the most relevant grouping.",
                    "role": "primary"
                })
            else:
                plans.append({
                    "type": "histogram",
                    "title": f"Distribution of {format_label(target)}",
                    "description": f"This is the primary answer chart. It shows the overall distribution of {format_label(target).lower()}.",
                    "role": "primary"
                })

        # SUPPORTING 1
        if has_time and not any(p["type"] == "line" for p in plans):
            plans.append({
                "type": "line",
                "date_col": time_column,
                "freq": infer_time_frequency(df, time_column),
                "agg": planner_agg,
                "title": f"Trend of {format_label(target)} over time",
                "description": f"This supporting chart adds time context so you can see whether the pattern is stable, rising, falling, or driven by spikes.",
                "role": "supporting"
            })
        elif best_cat and not any(p["type"] == "bar" and p.get("category_col") == best_cat for p in plans):
            plans.append({
                "type": "bar",
                "category_col": best_cat,
                "agg": planner_agg,
                "limit": 8,
                "title": f"{format_label(target)} by {format_label(best_cat)}",
                "description": f"This supporting chart gives another grouped view of {format_label(target).lower()}.",
                "role": "supporting"
            })
        elif second_cat:
            plans.append({
                "type": "bar",
                "category_col": second_cat,
                "agg": planner_agg,
                "limit": 8,
                "title": f"{format_label(target)} by {format_label(second_cat)}",
                "description": f"This supporting chart provides a second grouping view to explain where performance is concentrated.",
                "role": "supporting"
            })

        # SUPPORTING 2
        if best_cat and not wants_distribution and not any(p["type"] == "donut" for p in plans):
            plans.append({
                "type": "donut",
                "category_col": best_cat,
                "agg": planner_agg,
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
        if wants_distribution or not any(p["type"] in ["histogram", "box"] for p in plans):
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
                plan_item.get("agg")
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

    def _build_bar_option(self, df, category_col, target, agg="sum", limit=10, sort_desc=True):
        grouped_df = (
            df.groupby(category_col, dropna=False)[target]
            .agg(resolve_pandas_agg(agg))
            .sort_values(ascending=sort_desc)
            .head(limit)
        )

        categories = [safe_label(v) for v in grouped_df.index.tolist()]
        values = [round(float(v), 2) for v in grouped_df.values.tolist()]

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

        if freq == "Y":
            working["_period"] = working[date_col].dt.to_period("Y").astype(str)
        elif freq == "Q":
            working["_period"] = working[date_col].dt.to_period("Q").astype(str)
        elif freq == "W":
            working["_period"] = working[date_col].dt.to_period("W").astype(str)
        elif freq == "D":
            working["_period"] = working[date_col].dt.to_period("D").astype(str)
        else:
            working["_period"] = working[date_col].dt.to_period("M").astype(str)

        grouped = (
            working.groupby("_period")[target]
            .agg(resolve_pandas_agg(agg))
            .reset_index()
            .sort_values("_period")
        )

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
            .agg(resolve_pandas_agg(agg))
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
            "yAxis": {"type": "value"},
            "series": [{
                "type": "bar",
                "data": values,
                "barMaxWidth": 42,
                "itemStyle": {"borderRadius": [6, 6, 0, 0]}
            }]
        }

    def _build_box_option(self, df, target):
        series = pd.to_numeric(df[target], errors="coerce").dropna()
        if len(series) == 0:
            return None

        values = [round(float(v), 2) for v in series.tolist()]

        return {
            "tooltip": {"trigger": "item"},
            "grid": {"left": 70, "right": 30, "top": 50, "bottom": 60},
            "xAxis": {"type": "category", "data": [format_label(target)]},
            "yAxis": {
                "type": "value",
                "axisLabel": {
                    "formatter": {"function": "function(value){ return compactAxis(value); }"}
                }
            },
            "series": [{
                "type": "boxplot",
                "data": [compute_box_stats(values)]
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


def normalize_aggregation(agg):
    agg = str(agg or "").strip().lower()
    mapping = {
        "avg": "mean",
        "average": "mean",
        "mean": "mean",
        "sum": "sum",
        "median": "median",
        "count": "count",
        "count_distinct": "count",
        "none": "sum",
    }
    return mapping.get(agg, "sum")


def resolve_pandas_agg(agg):
    normalized = normalize_aggregation(agg)
    if normalized in {"sum", "mean", "median", "count"}:
        return normalized
    return "sum"


def infer_time_frequency(df, date_col):
    series = df[date_col].dropna().sort_values()
    if len(series) < 2:
        return "M"

    try:
        median_diff = series.diff().dropna().dt.days.median()
        if median_diff is None:
            return "M"
        if median_diff <= 2:
            return "D"
        if median_diff <= 10:
            return "W"
        if median_diff <= 45:
            return "M"
        if median_diff <= 120:
            return "Q"
        return "Y"
    except Exception:
        return "M"


def compute_box_stats(values):
    clean = sorted([float(v) for v in values if v is not None])
    if not clean:
        return [0, 0, 0, 0, 0]

    q1 = pd.Series(clean).quantile(0.25)
    median = pd.Series(clean).quantile(0.5)
    q3 = pd.Series(clean).quantile(0.75)
    low = min(clean)
    high = max(clean)

    return [
        round(float(low), 2),
        round(float(q1), 2),
        round(float(median), 2),
        round(float(q3), 2),
        round(float(high), 2),
    ]


def format_label(value):
    return str(value).replace("_", " ").strip()


def safe_label(value):
    if pd.isna(value):
        return "Unknown"
    return str(value)


def truncate_label(value, max_len=16):
    value = str(value)
    return value if len(value) <= max_len else value[:max_len - 1] + "…"