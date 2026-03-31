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
        datetime_cols = working_df.select_dtypes(include=["datetime64[ns]", "datetime64[ns, UTC]"]).columns.tolist()

        q = (question or "").lower().strip()
        drivers = drivers or []
        aggregation = normalize_aggregation(aggregation)
        plan = plan or {}
        ranking_direction = infer_ranking_direction(q, target=target)

        if time_column not in working_df.columns or time_column not in datetime_cols:
            time_column = resolve_best_time_column(
                df=working_df,
                datetime_cols=datetime_cols,
                drivers=drivers,
                question=q
            )

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
            plan=plan,
            ranking_direction=ranking_direction
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
                        limit=item.get("limit", 10),
                        sort_direction=item.get("sort_direction", ranking_direction)
                    )

                elif chart_type == "line":
                    option = self._build_time_series_option(
                        working_df,
                        date_col=item["date_col"],
                        target=target,
                        freq=item.get("freq", "M"),
                        agg=item.get("agg", aggregation)
                    )

                elif chart_type == "grouped_line":
                    option = self._build_grouped_time_series_option(
                        working_df,
                        date_col=item["date_col"],
                        category_col=item["category_col"],
                        target=target,
                        freq=item.get("freq", "M"),
                        agg=item.get("agg", aggregation),
                        limit=item.get("limit", 5),
                        sort_direction=item.get("sort_direction", "descending")
                    )

                elif chart_type == "donut":
                    option = self._build_donut_option(
                        working_df,
                        category_col=item["category_col"],
                        target=target,
                        agg=item.get("agg", aggregation),
                        limit=item.get("limit", 6),
                        sort_direction=item.get("sort_direction", "descending")
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
        plan,
        ranking_direction="descending"
    ):
        plans = []

        requested_group = detect_requested_grouping_dimension(
            df=df,
            categorical_cols=categorical_cols,
            question=question,
            drivers=drivers
        )

        best_cat = requested_group or choose_best_category_column(
            df=df,
            categorical_cols=categorical_cols,
            question=question,
            drivers=drivers,
            target=target
        )

        second_cat = choose_second_category_column(
            df=df,
            categorical_cols=categorical_cols,
            question=question,
            drivers=drivers,
            first_choice=best_cat,
            target=target,
            requested_group=requested_group
        )

        best_num = choose_best_numeric_driver(
            df=df,
            numeric_cols=numeric_cols,
            target=target,
            question=question,
            drivers=drivers
        )

        has_time = bool(time_column and time_column in df.columns)
        freq = infer_frequency_from_question(question, df, time_column)

        wants_trend = intent == "trend_analysis" or any(
            token in question for token in [
                "trend", "over time", "monthly", "weekly", "daily",
                "timeline", "growth", "quarterly", "yearly", "change over time"
            ]
        )
        wants_distribution = intent == "distribution_analysis" or any(
            token in question for token in ["distribution", "spread", "outlier", "variance", "range", "histogram"]
        )
        wants_relationship = intent == "relationship_analysis" or any(
            token in question for token in ["relationship", "correlation", "impact", "influence", "driver", "association", "related"]
        )
        wants_contribution = intent == "contribution_analysis" or any(
            token in question for token in ["contribution", "share", "composition", "mix", "portion"]
        )

        planner_primary = normalize_chart_type(preferred_chart)

        # PRIMARY CHART
        if wants_trend and has_time:
            should_compare_groups = best_cat is not None
            if should_compare_groups:
                plans.append({
                    "type": "grouped_line",
                    "date_col": time_column,
                    "category_col": best_cat,
                    "freq": freq,
                    "agg": aggregation,
                    "limit": 5,
                    "sort_direction": "descending",
                    "title": f"{format_label(target)} trend by {format_label(best_cat)}",
                    "description": f"This is the primary answer chart. It compares how {format_label(target).lower()} changes over time across the requested {format_label(best_cat).lower()} groups.",
                    "role": "primary"
                })
            else:
                plans.append({
                    "type": "line",
                    "date_col": time_column,
                    "freq": freq,
                    "agg": aggregation,
                    "title": f"{format_label(target)} over time",
                    "description": f"This is the primary answer chart. It shows how {format_label(target).lower()} changes over time so the overall direction is immediately clear.",
                    "role": "primary"
                })

        elif wants_relationship and best_num:
            plans.append({
                "type": "scatter",
                "x_col": best_num,
                "title": f"{format_label(best_num)} vs {format_label(target)}",
                "description": f"This is the primary answer chart. It shows whether {format_label(best_num).lower()} has a visible relationship with {format_label(target).lower()}.",
                "role": "primary"
            })

        elif wants_distribution:
            plans.append({
                "type": "histogram",
                "title": f"Distribution of {format_label(target)}",
                "description": f"This is the primary answer chart. It shows the spread and concentration of {format_label(target).lower()} across the dataset.",
                "role": "primary"
            })

        elif planner_primary == "line" and has_time:
            if best_cat:
                plans.append({
                    "type": "grouped_line",
                    "date_col": time_column,
                    "category_col": best_cat,
                    "freq": freq,
                    "agg": aggregation,
                    "limit": 5,
                    "sort_direction": "descending",
                    "title": f"{format_label(target)} trend by {format_label(best_cat)}",
                    "description": f"This is the primary answer chart based on the planner recommendation and requested grouping dimension.",
                    "role": "primary"
                })
            else:
                plans.append({
                    "type": "line",
                    "date_col": time_column,
                    "freq": freq,
                    "agg": aggregation,
                    "title": f"{format_label(target)} over time",
                    "description": f"This is the primary answer chart based on the planner recommendation and available time dimension.",
                    "role": "primary"
                })

        elif planner_primary == "scatter" and best_num:
            plans.append({
                "type": "scatter",
                "x_col": best_num,
                "title": f"{format_label(best_num)} vs {format_label(target)}",
                "description": f"This is the primary answer chart based on the planner recommendation and strongest numeric driver.",
                "role": "primary"
            })

        elif planner_primary == "histogram":
            plans.append({
                "type": "histogram",
                "title": f"Distribution of {format_label(target)}",
                "description": f"This is the primary answer chart based on the planner recommendation.",
                "role": "primary"
            })

        elif best_cat:
            title_prefix = (
                f"Lowest {format_label(target)} by {format_label(best_cat)}"
                if ranking_direction == "ascending"
                else f"{format_label(target)} by {format_label(best_cat)}"
            )
            plans.append({
                "type": "bar",
                "category_col": best_cat,
                "agg": aggregation if aggregation in {"sum", "mean", "median", "count"} else "sum",
                "limit": 10,
                "sort_direction": ranking_direction,
                "title": title_prefix,
                "description": f"This is the primary answer chart. It shows how {format_label(target).lower()} differs across the requested grouping dimension.",
                "role": "primary"
            })

        else:
            plans.append({
                "type": "histogram",
                "title": f"Distribution of {format_label(target)}",
                "description": f"This is the primary answer chart. It gives a safe overview of how {format_label(target).lower()} is distributed.",
                "role": "primary"
            })

        # SUPPORTING CHART 1
        if has_time and not any(p["type"] in {"line", "grouped_line"} for p in plans):
            plans.append({
                "type": "line",
                "date_col": time_column,
                "freq": freq,
                "agg": aggregation,
                "title": f"Trend of {format_label(target)} over time",
                "description": f"This supporting chart adds time context and helps reveal whether the pattern is stable, improving, declining, or driven by spikes.",
                "role": "supporting"
            })
        elif best_cat and not any(p["type"] == "bar" and p.get("category_col") == best_cat for p in plans):
            plans.append({
                "type": "bar",
                "category_col": best_cat,
                "agg": aggregation,
                "limit": 8,
                "sort_direction": ranking_direction,
                "title": (
                    f"Lowest {format_label(best_cat)} by {format_label(target)}"
                    if ranking_direction == "ascending"
                    else f"Top {format_label(best_cat)} contributors"
                ),
                "description": f"This supporting chart highlights the requested groups for {format_label(target).lower()}.",
                "role": "supporting"
            })
        elif second_cat:
            plans.append({
                "type": "bar",
                "category_col": second_cat,
                "agg": aggregation,
                "limit": 8,
                "sort_direction": "descending",
                "title": f"{format_label(target)} by {format_label(second_cat)}",
                "description": f"This supporting chart provides a second grouping perspective to explain where performance is concentrated.",
                "role": "supporting"
            })

        # SUPPORTING CHART 2
        if wants_contribution and best_cat:
            plans.append({
                "type": "donut",
                "category_col": best_cat,
                "agg": "sum" if aggregation not in {"count", "mean", "median"} else aggregation,
                "limit": 6,
                "sort_direction": "descending",
                "title": f"Share of {format_label(target)} by {format_label(best_cat)}",
                "description": f"This supporting chart shows how concentrated {format_label(target).lower()} is across the main grouping dimension.",
                "role": "supporting"
            })
        elif best_num and not any(p["type"] == "scatter" for p in plans):
            plans.append({
                "type": "scatter",
                "x_col": best_num,
                "title": f"{format_label(best_num)} compared with {format_label(target)}",
                "description": f"This supporting chart checks whether a meaningful numeric field appears to move with the target metric.",
                "role": "supporting"
            })
        elif best_cat and not any(p["type"] == "donut" for p in plans):
            plans.append({
                "type": "donut",
                "category_col": best_cat,
                "agg": "sum" if aggregation not in {"count", "mean", "median"} else aggregation,
                "limit": 6,
                "sort_direction": "descending",
                "title": f"Contribution share by {format_label(best_cat)}",
                "description": f"This supporting chart shows the composition of {format_label(target).lower()} across the main grouping dimension.",
                "role": "supporting"
            })
        else:
            plans.append({
                "type": "histogram",
                "title": f"Distribution view of {format_label(target)}",
                "description": f"This supporting chart shows spread, clustering, and possible imbalance in the target metric.",
                "role": "supporting"
            })

        # SUPPORTING / DIAGNOSTIC CHART 3
        if second_cat and not any(p["type"] == "bar" and p.get("category_col") == second_cat for p in plans):
            plans.append({
                "type": "bar",
                "category_col": second_cat,
                "agg": aggregation,
                "limit": 8,
                "sort_direction": "descending",
                "title": f"{format_label(target)} by {format_label(second_cat)}",
                "description": f"This chart adds another segmentation view so you can compare performance across an additional business dimension.",
                "role": "supporting"
            })
        elif wants_distribution or not any(p["type"] == "histogram" for p in plans):
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
                "description": f"This diagnostic chart helps validate whether a meaningful numeric field has a visible relationship with the target.",
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
                plan_item.get("freq"),
                plan_item.get("sort_direction")
            )
            if key not in seen:
                deduped.append(plan_item)
                seen.add(key)

        final_plan = self._ensure_chart_mix(
            deduped=deduped,
            df=df,
            target=target,
            best_cat=best_cat,
            second_cat=second_cat,
            best_num=best_num,
            time_column=time_column,
            aggregation=aggregation,
            freq=freq,
            ranking_direction=ranking_direction
        )

        return final_plan[:4]

    def _ensure_chart_mix(
        self,
        deduped,
        df,
        target,
        best_cat,
        second_cat,
        best_num,
        time_column,
        aggregation,
        freq,
        ranking_direction="descending"
    ):
        final_plan = list(deduped)

        existing_types = [p["type"] for p in final_plan]

        if len(final_plan) < 4 and best_cat and "bar" not in existing_types:
            final_plan.append({
                "type": "bar",
                "category_col": best_cat,
                "agg": aggregation,
                "limit": 8,
                "sort_direction": ranking_direction,
                "title": f"{format_label(target)} by {format_label(best_cat)}",
                "description": f"This chart shows how {format_label(target).lower()} varies across a leading grouping dimension.",
                "role": "supporting"
            })
            existing_types.append("bar")

        if len(final_plan) < 4 and time_column and not any(t in existing_types for t in ["line", "grouped_line"]):
            final_plan.append({
                "type": "line",
                "date_col": time_column,
                "freq": freq,
                "agg": aggregation,
                "title": f"Trend of {format_label(target)} over time",
                "description": f"This chart adds time context to show changes in {format_label(target).lower()} over time.",
                "role": "supporting"
            })
            existing_types.append("line")

        if len(final_plan) < 4 and best_num and "scatter" not in existing_types:
            final_plan.append({
                "type": "scatter",
                "x_col": best_num,
                "title": f"{format_label(best_num)} vs {format_label(target)}",
                "description": f"This chart helps assess whether a meaningful numeric driver moves with the target.",
                "role": "supporting"
            })
            existing_types.append("scatter")

        if len(final_plan) < 4 and best_cat and "donut" not in existing_types:
            final_plan.append({
                "type": "donut",
                "category_col": best_cat,
                "agg": "sum" if aggregation not in {"count", "mean", "median"} else aggregation,
                "limit": 6,
                "sort_direction": "descending",
                "title": f"Contribution share by {format_label(best_cat)}",
                "description": f"This chart shows composition and concentration across the main grouping dimension.",
                "role": "supporting"
            })
            existing_types.append("donut")

        if len(final_plan) < 4 and "histogram" not in existing_types:
            final_plan.append({
                "type": "histogram",
                "title": f"Diagnostic distribution of {format_label(target)}",
                "description": f"This chart helps assess spread and possible outliers in the target metric.",
                "role": "diagnostic"
            })
            existing_types.append("histogram")

        cleaned = []
        seen = set()
        for plan_item in final_plan:
            key = (
                plan_item["type"],
                plan_item.get("category_col"),
                plan_item.get("date_col"),
                plan_item.get("x_col"),
                plan_item.get("agg"),
                plan_item.get("freq"),
                plan_item.get("sort_direction")
            )
            if key not in seen:
                cleaned.append(plan_item)
                seen.add(key)

        return cleaned[:4]

    def _prepare_dataframe(self, df, target):
        if target in df.columns and not pd.api.types.is_numeric_dtype(df[target]):
            df[target] = pd.to_numeric(df[target], errors="coerce")
        return df

    def _build_bar_option(self, df, category_col, target, agg="sum", limit=10, sort_direction="descending"):
        grouped_series = df.groupby(category_col, dropna=False)[target].agg(agg)

        ascending = sort_direction == "ascending"
        grouped_series = grouped_series.sort_values(ascending=ascending)

        if limit:
            grouped_series = grouped_series.head(limit)

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

    def _build_grouped_time_series_option(self, df, date_col, category_col, target, freq="M", agg="sum", limit=5, sort_direction="descending"):
        working = df.dropna(subset=[date_col, category_col, target]).copy()

        if working.empty:
            return None

        period_code = freq if freq in {"D", "W", "M", "Q", "Y"} else "M"
        working["_period"] = working[date_col].dt.to_period(period_code).astype(str)

        agg = normalize_aggregation(agg)
        if agg == "mean":
            group_totals = working.groupby(category_col)[target].mean()
        elif agg == "median":
            group_totals = working.groupby(category_col)[target].median()
        elif agg == "count":
            group_totals = working.groupby(category_col)[target].count()
        else:
            group_totals = working.groupby(category_col)[target].sum()

        # For grouped trend charts, always choose the largest groups so the comparison stays informative.
        group_totals = group_totals.sort_values(ascending=False)

        top_groups = group_totals.head(limit).index.tolist()
        working = working[working[category_col].isin(top_groups)]

        if working.empty:
            return None

        if agg == "mean":
            grouped = working.groupby(["_period", category_col])[target].mean().reset_index()
        elif agg == "median":
            grouped = working.groupby(["_period", category_col])[target].median().reset_index()
        elif agg == "count":
            grouped = working.groupby(["_period", category_col])[target].count().reset_index()
        else:
            grouped = working.groupby(["_period", category_col])[target].sum().reset_index()

        pivot = (
            grouped.pivot(index="_period", columns=category_col, values=target)
            .fillna(0)
            .sort_index()
        )

        return {
            "tooltip": {"trigger": "axis"},
            "legend": {
                "top": 8,
                "type": "scroll"
            },
            "grid": {"left": 70, "right": 30, "top": 80, "bottom": 75},
            "xAxis": {
                "type": "category",
                "data": pivot.index.tolist(),
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
            "series": [
                {
                    "name": safe_label(col),
                    "type": "line",
                    "data": [round(float(v), 2) for v in pivot[col].tolist()],
                    "smooth": True,
                    "showSymbol": False,
                    "lineStyle": {"width": 2}
                }
                for col in pivot.columns
            ]
        }

    def _build_donut_option(self, df, category_col, target, agg="sum", limit=6, sort_direction="descending"):
        grouped = df.groupby(category_col, dropna=False)[target].agg(agg)
        grouped = grouped.sort_values(ascending=False).head(limit)

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


def detect_requested_grouping_dimension(df, categorical_cols, question, drivers):
    if not categorical_cols:
        return None

    q = (question or "").lower().strip()
    driver_set = set(drivers or [])

    alias_map = [
        ("sub-category", {"sub-category", "sub category", "subcategory", "subcategories"}),
        ("category", {"category", "categories"}),
        ("segment", {"segment", "segments"}),
        ("region", {"region", "regions"}),
        ("country", {"country", "countries"}),
        ("state", {"state", "states"}),
        ("city", {"city", "cities"}),
        ("product", {"product", "products", "item", "items", "sku", "stockcode", "stock code"}),
        ("customer", {"customer", "customers", "client", "clients"}),
        ("ship mode", {"ship mode", "shipping mode"}),
        ("sales person", {"sales person", "salesperson", "seller", "rep", "representative"}),
    ]

    best = None
    best_score = -999

    for canonical, terms in alias_map:
        if not any(term in q for term in terms):
            continue

        for col in categorical_cols:
            col_lower = col.lower().strip()
            nunique = int(df[col].nunique(dropna=True))
            non_null_pct = float(df[col].notna().mean())

            score = 0.0

            if col in driver_set:
                score += 4.0

            if is_bad_category_column(col, df[col]):
                score -= 100.0

            if canonical in col_lower:
                score += 10.0

            if canonical == "sub-category" and any(term in col_lower for term in ["sub-category", "sub category"]):
                score += 10.0
            if canonical == "product" and any(term in col_lower for term in ["product", "item", "sku", "stockcode", "stock code"]):
                score += 8.0
            if canonical == "country" and "country" in col_lower:
                score += 8.0
            if canonical == "segment" and "segment" in col_lower:
                score += 8.0

            if 2 <= nunique <= 25:
                score += 2.0
            elif nunique > 40:
                score -= 3.0

            score += non_null_pct

            if score > best_score:
                best = col
                best_score = score

    return best if best_score > 0 else None


def choose_best_category_column(df, categorical_cols, question, drivers, target=None):
    if not categorical_cols:
        return None

    requested = detect_requested_grouping_dimension(df, categorical_cols, question, drivers)
    if requested:
        return requested

    question = (question or "").lower().strip()
    target = str(target or "").lower().strip()
    driver_set = set(drivers or [])

    alias_map = {
        "product": {"product", "products", "item", "items", "sku", "chocolate", "chocolates"},
        "country": {"country", "countries", "market", "markets", "region", "regions"},
        "sales person": {"sales person", "salesperson", "seller", "rep", "representative"},
        "category": {"category", "categories", "segment", "segments", "group", "groups"}
    }

    scored = []

    for col in categorical_cols:
        col_lower = col.lower()
        nunique = int(df[col].nunique(dropna=True))
        non_null_pct = float(df[col].notna().mean())

        score = 0.0

        if col in driver_set:
            score += 5.0

        if is_bad_category_column(col, df[col]):
            score -= 100.0

        if 2 <= nunique <= 12:
            score += 4.0
        elif 13 <= nunique <= 25:
            score += 3.0
        elif 26 <= nunique <= 40:
            score += 1.0
        elif nunique == 1:
            score -= 5.0
        elif nunique > 40:
            score -= 4.0

        preferred = ["region", "country", "state", "city", "category", "segment", "channel", "market", "brand", "status", "product", "ship mode", "sub-category", "sub category", "sales person"]
        for pref in preferred:
            if pref in col_lower:
                score += 2.0
            if pref in question and pref in col_lower:
                score += 2.5

        for canonical, terms in alias_map.items():
            if any(term in question for term in terms):
                if canonical in col_lower:
                    score += 10.0

        question_tokens = set(question.replace("-", " ").replace("_", " ").split())
        col_tokens = set(col_lower.replace("_", " ").replace("-", " ").split())
        score += 1.25 * len(question_tokens.intersection(col_tokens))

        if target and target in col_lower:
            score -= 2.0

        score += non_null_pct
        scored.append((col, score))

    scored.sort(key=lambda x: x[1], reverse=True)
    return scored[0][0] if scored and scored[0][1] > 0 else None


def choose_second_category_column(df, categorical_cols, question, drivers, first_choice, target=None, requested_group=None):
    remaining = [c for c in categorical_cols if c != first_choice]
    if not remaining:
        return None

    remaining = [c for c in remaining if c != requested_group]
    if not remaining:
        return None

    return choose_best_category_column(df, remaining, question, drivers, target=target)


def choose_best_numeric_driver(df, numeric_cols, target, question="", drivers=None):
    usable = []
    driver_set = set(drivers or [])
    question = (question or "").lower().strip()

    for col in numeric_cols:
        if col == target:
            continue

        if is_bad_numeric_driver_column(col, df[col]):
            continue

        col_lower = col.lower()
        non_null_pct = float(df[col].notna().mean())
        nunique = int(df[col].nunique(dropna=True))
        std_value = pd.to_numeric(df[col], errors="coerce").dropna().std()

        score = 0.0

        if col in driver_set:
            score += 5.0

        if non_null_pct >= 0.80:
            score += 3.0
        elif non_null_pct >= 0.50:
            score += 1.5
        else:
            score -= 2.0

        if nunique <= 1:
            score -= 5.0
        elif nunique >= 5:
            score += 2.0

        if pd.notna(std_value) and std_value > 0:
            score += 2.0

        keywords = ["sales", "revenue", "profit", "cost", "price", "amount", "quantity", "discount", "margin", "score", "rate", "value"]
        for kw in keywords:
            if kw in col_lower:
                score += 1.5
            if kw in question and kw in col_lower:
                score += 2.0

        question_tokens = set(question.split())
        col_tokens = set(col_lower.replace("_", " ").split())
        score += 0.75 * len(question_tokens.intersection(col_tokens))

        usable.append((col, score))

    usable.sort(key=lambda x: x[1], reverse=True)
    return usable[0][0] if usable else None


def infer_ranking_direction(question, target=None):
    q = str(question or "").lower().strip()
    target_lower = str(target or "").lower().strip()

    ascending_terms = {
        "least", "lowest", "bottom", "worst", "smallest", "minimum", "min",
        "least profitable", "least profit", "lowest profit", "lowest sales",
        "lowest revenue", "smallest contribution", "most negative"
    }
    descending_terms = {
        "most", "highest", "top", "leading", "largest", "biggest", "maximum", "max",
        "most profitable", "highest profit", "highest sales", "highest revenue"
    }

    if any(term in q for term in ascending_terms):
        return "ascending"
    if any(term in q for term in descending_terms):
        return "descending"

    if "profit" in target_lower and any(term in q for term in ["least", "lowest", "worst"]):
        return "ascending"

    return "descending"


def is_bad_numeric_driver_column(col_name, series):
    name = str(col_name).strip().lower()

    id_like_keywords = [
        "id", "row id", "row_id", "rowid",
        "postal code", "postal", "zip", "zipcode",
        "transaction id", "order id", "customer id", "product id"
    ]
    if any(token in name for token in id_like_keywords):
        return True

    try:
        non_null = series.dropna()
        if len(non_null) == 0:
            return True
        unique_ratio = float(non_null.nunique() / len(non_null))
        if unique_ratio >= 0.95:
            return True
    except Exception:
        pass

    return False


def is_bad_category_column(col_name, series):
    name = str(col_name).strip().lower()

    if any(token in name for token in ["id", "postal", "zip", "zipcode"]):
        return True

    try:
        cleaned = series.dropna().astype(str).str.strip().str.lower()
        if len(cleaned) == 0:
            return False
        placeholder_ratio = float(cleaned.isin({"unknown", "error", "n/a", "na", "null", "none", ""}).mean())
        if placeholder_ratio > 0.50:
            return True
    except Exception:
        pass

    return False


def resolve_best_time_column(df, datetime_cols, drivers, question):
    if not datetime_cols:
        return None

    question = (question or "").lower().strip()
    driver_set = set(drivers or [])
    scored = []

    for col in datetime_cols:
        col_lower = col.lower()
        non_null_pct = float(df[col].notna().mean())

        score = 0.0

        if col in driver_set:
            score += 4.0

        for kw in ["order date", "sale date", "transaction date", "date", "time", "timestamp", "month", "quarter", "year"]:
            if kw in col_lower:
                score += 2.0
            if kw in question and kw in col_lower:
                score += 2.0

        score += non_null_pct

        scored.append((col, score))

    scored.sort(key=lambda x: x[1], reverse=True)
    return scored[0][0] if scored else None


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
        "grouped_line": "grouped_line",
        "scatter": "scatter",
        "histogram": "histogram",
        "box": "histogram",
        "area": "line",
        "heatmap": "bar",
        "table": "bar",
        "donut": "donut",
        "pie": "donut"
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