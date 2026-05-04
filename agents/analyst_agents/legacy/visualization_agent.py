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
        plan=None,
        dataset_context=None
    ):
        charts = []

        if target not in df.columns:
            return charts

        working_df = self._prepare_dataframe(df.copy(), target)
        working_df = working_df.dropna(subset=[target])

        if len(working_df) == 0:
            return charts

        # Only use actual datetime64 columns for time charts (FIX for 1970 bug)
        numeric_cols = working_df.select_dtypes(include=["int64", "float64", "int32", "float32"]).columns.tolist()
        categorical_cols = working_df.select_dtypes(include=["object"]).columns.tolist()
        datetime_cols = [
            col for col in working_df.columns
            if pd.api.types.is_datetime64_any_dtype(working_df[col])
        ]

        q = (question or "").lower().strip()
        drivers = drivers or []
        aggregation = normalize_aggregation(aggregation)
        plan = plan or {}
        dataset_context = dataset_context or {}

        # Resolve time column — only from actual datetime columns
        if time_column not in datetime_cols:
            time_column = resolve_best_time_column(
                df=working_df,
                datetime_cols=datetime_cols,
                drivers=drivers,
                question=q
            )

        # Guard: skip time column if it only has epoch dates (1970)
        if time_column and time_column in working_df.columns:
            try:
                valid_dates = working_df[time_column].dropna()
                if len(valid_dates) > 0 and valid_dates.min().year == 1970 and valid_dates.max().year == 1970:
                    time_column = None
            except Exception:
                time_column = None

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
            dataset_context=dataset_context
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

                elif chart_type == "grouped_bar":
                    option = self._build_grouped_bar_option(
                        working_df,
                        category_col=item["category_col"],
                        group_col=item.get("group_col"),
                        target=target,
                        agg=item.get("agg", aggregation),
                        limit=item.get("limit", 8)
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

        # Dynamic chart count — up to 6 for complex questions, minimum 3
        max_charts = self._resolve_max_charts(intent, q)
        return charts[:max_charts]

    def _resolve_max_charts(self, intent, question):
        """
        Return more charts for multi-dimensional questions, fewer for simple ones.
        Previously hard-capped at 4 regardless of question complexity.
        """
        complex_intents = {"trend_analysis", "distribution_analysis", "relationship_analysis"}
        complex_keywords = ["compare", "breakdown", "segment", "vs", "versus", "across", "by", "each", "all", "full", "complete", "deep", "detailed"]

        if intent in complex_intents:
            return 6
        if any(kw in question for kw in complex_keywords):
            return 6
        return 4

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
        dataset_context
    ):
        plans = []

        # Get column selections — scored against the QUESTION not just schema
        best_cat = choose_best_category_column(
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
            target=target
        )

        third_cat = choose_third_category_column(
            df=df,
            categorical_cols=categorical_cols,
            question=question,
            drivers=drivers,
            used_choices=[best_cat, second_cat],
            target=target
        )

        # FIX: score numeric driver against question tokens with high weight
        # Previously picked any high-variance numeric — now must relate to the question
        best_num = choose_best_numeric_driver(
            df=df,
            numeric_cols=numeric_cols,
            target=target,
            question=question,
            drivers=drivers
        )

        second_num = choose_second_numeric_driver(
            df=df,
            numeric_cols=numeric_cols,
            target=target,
            question=question,
            drivers=drivers,
            first_choice=best_num
        )

        has_time = bool(time_column and time_column in df.columns)
        freq = infer_frequency_from_question(question, df, time_column)

        # Detect what the question is asking for
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
            token in question for token in ["relationship", "correlation", "impact", "influence", "driver", "association", "help explain", "explain"]
        )
        wants_contribution = intent == "contribution_analysis" or any(
            token in question for token in ["contribution", "share", "composition", "mix", "portion", "breakdown"]
        )
        wants_comparison = intent == "comparison" or any(
            token in question for token in ["compare", "vs", "versus", "difference", "gap", "rank", "top", "bottom"]
        )

        planner_primary = normalize_chart_type(preferred_chart)

        # ─────────────────────────────────────────────
        # PRIMARY CHART — answers the question directly
        # ─────────────────────────────────────────────

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
            plans.append({
                "type": "line",
                "date_col": time_column,
                "freq": freq,
                "agg": aggregation,
                "title": f"{format_label(target)} over time",
                "description": "This is the primary answer chart based on the planner recommendation.",
                "role": "primary"
            })

        elif planner_primary == "scatter" and best_num:
            plans.append({
                "type": "scatter",
                "x_col": best_num,
                "title": f"{format_label(best_num)} vs {format_label(target)}",
                "description": "This is the primary answer chart based on the planner recommendation.",
                "role": "primary"
            })

        elif planner_primary == "histogram":
            plans.append({
                "type": "histogram",
                "title": f"Distribution of {format_label(target)}",
                "description": "This is the primary answer chart based on the planner recommendation.",
                "role": "primary"
            })

        elif best_cat:
            plans.append({
                "type": "bar",
                "category_col": best_cat,
                "agg": aggregation if aggregation in {"sum", "mean", "median", "count"} else "sum",
                "limit": 10,
                "title": f"{format_label(target)} by {format_label(best_cat)}",
                "description": f"This is the primary answer chart. It shows how {format_label(target).lower()} differs across the most relevant grouping dimension.",
                "role": "primary"
            })

        else:
            plans.append({
                "type": "histogram",
                "title": f"Distribution of {format_label(target)}",
                "description": f"This is the primary answer chart. It gives a safe overview of how {format_label(target).lower()} is distributed.",
                "role": "primary"
            })

        # ─────────────────────────────────────────────
        # SUPPORTING CHARTS — each covers a DIFFERENT analytical angle
        # FIX: Supporting charts are now explicitly assigned to different
        # analytical angles (time, segmentation, distribution, correlation,
        # contribution) rather than just picking the next available column.
        # This prevents showing the same chart type or same dimension twice.
        # ─────────────────────────────────────────────

        used_angles = set()
        if "line" in [p["type"] for p in plans]:
            used_angles.add("time")
        if "scatter" in [p["type"] for p in plans]:
            used_angles.add("correlation")
        if "histogram" in [p["type"] for p in plans]:
            used_angles.add("distribution")
        if "bar" in [p["type"] for p in plans]:
            used_angles.add("segmentation")
        if "donut" in [p["type"] for p in plans]:
            used_angles.add("contribution")

        used_cat_cols = {p.get("category_col") for p in plans if p.get("category_col")}
        used_num_cols = {p.get("x_col") for p in plans if p.get("x_col")}

        def can_add(angle, col=None, col_set=None):
            if angle in used_angles:
                return False
            if col and col_set and col in col_set:
                return False
            return True

        # ── ANGLE: Time trend (if not already primary and time exists)
        if can_add("time") and has_time:
            plans.append({
                "type": "line",
                "date_col": time_column,
                "freq": freq,
                "agg": aggregation,
                "title": f"Trend of {format_label(target)} over time",
                "description": f"This supporting chart adds time context and helps reveal whether the pattern is stable, improving, declining, or driven by spikes.",
                "role": "supporting"
            })
            used_angles.add("time")

        # ── ANGLE: Primary segmentation breakdown
        if can_add("segmentation", best_cat, used_cat_cols) and best_cat:
            plans.append({
                "type": "bar",
                "category_col": best_cat,
                "agg": aggregation,
                "limit": 10,
                "title": f"{format_label(target)} by {format_label(best_cat)}",
                "description": f"This supporting chart shows how {format_label(target).lower()} differs across {format_label(best_cat).lower()} — the most discriminating segment dimension.",
                "role": "supporting"
            })
            used_cat_cols.add(best_cat)
            used_angles.add("segmentation")

        # ── ANGLE: Correlation / relationship with most relevant numeric driver
        if can_add("correlation", best_num, used_num_cols) and best_num:
            plans.append({
                "type": "scatter",
                "x_col": best_num,
                "title": f"{format_label(best_num)} compared with {format_label(target)}",
                "description": f"This supporting chart checks whether {format_label(best_num).lower()} moves with {format_label(target).lower()} — indicating a potential driver relationship.",
                "role": "supporting"
            })
            used_num_cols.add(best_num)
            used_angles.add("correlation")

        # ── ANGLE: Contribution share / composition
        if can_add("contribution", best_cat, None) and best_cat:
            plans.append({
                "type": "donut",
                "category_col": best_cat,
                "agg": "sum" if aggregation not in {"count", "mean", "median"} else aggregation,
                "limit": 6,
                "title": f"Share of {format_label(target)} by {format_label(best_cat)}",
                "description": f"This supporting chart shows what share of total {format_label(target).lower()} each {format_label(best_cat).lower()} segment contributes.",
                "role": "supporting"
            })
            used_angles.add("contribution")

        # ── ANGLE: Second segmentation dimension (different from first)
        if second_cat and second_cat not in used_cat_cols:
            plans.append({
                "type": "bar",
                "category_col": second_cat,
                "agg": aggregation,
                "limit": 8,
                "title": f"{format_label(target)} by {format_label(second_cat)}",
                "description": f"This supporting chart adds a second segmentation angle — how {format_label(target).lower()} varies across {format_label(second_cat).lower()}.",
                "role": "supporting"
            })
            used_cat_cols.add(second_cat)

        # ── ANGLE: Distribution (always useful as a trust check)
        if can_add("distribution") and not wants_distribution:
            plans.append({
                "type": "histogram",
                "title": f"Distribution of {format_label(target)}",
                "description": f"This diagnostic chart helps assess spread, skew, and possible outliers in {format_label(target).lower()} — a useful trust check on the main result.",
                "role": "diagnostic"
            })
            used_angles.add("distribution")

        # ── EXTRA: Second correlation (for relationship questions)
        if wants_relationship and second_num and second_num not in used_num_cols:
            plans.append({
                "type": "scatter",
                "x_col": second_num,
                "title": f"{format_label(second_num)} vs {format_label(target)}",
                "description": f"This additional chart checks whether {format_label(second_num).lower()} also has a meaningful relationship with {format_label(target).lower()}.",
                "role": "supporting"
            })
            used_num_cols.add(second_num)

        # ── EXTRA: Third segmentation (for comparison/breakdown questions)
        if (wants_comparison or wants_contribution) and third_cat and third_cat not in used_cat_cols:
            plans.append({
                "type": "bar",
                "category_col": third_cat,
                "agg": aggregation,
                "limit": 8,
                "title": f"{format_label(target)} by {format_label(third_cat)}",
                "description": f"This additional segmentation view shows how {format_label(target).lower()} varies across {format_label(third_cat).lower()} for a more complete picture.",
                "role": "supporting"
            })
            used_cat_cols.add(third_cat)

        # Deduplicate
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

        return deduped

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

    def _build_grouped_bar_option(self, df, category_col, group_col, target, agg="mean", limit=8):
        """Multi-series bar chart — one series per group_col value."""
        if not group_col or group_col not in df.columns:
            return self._build_bar_option(df, category_col, target, agg, limit)

        top_cats = (
            df.groupby(category_col, dropna=False)[target]
            .agg(agg)
            .sort_values(ascending=False)
            .head(limit)
            .index.tolist()
        )

        top_groups = (
            df[group_col].value_counts().head(5).index.tolist()
        )

        filtered = df[df[category_col].isin(top_cats) & df[group_col].isin(top_groups)]
        pivot = filtered.groupby([category_col, group_col])[target].agg(agg).unstack(fill_value=0)

        categories = [safe_label(v) for v in pivot.index.tolist()]
        series = []
        for grp in pivot.columns:
            series.append({
                "name": safe_label(grp),
                "type": "bar",
                "data": [round(float(v), 2) for v in pivot[grp].tolist()],
                "barMaxWidth": 32
            })

        return {
            "tooltip": {"trigger": "axis"},
            "legend": {"bottom": 0, "type": "scroll"},
            "grid": {"left": 70, "right": 30, "top": 50, "bottom": 95},
            "xAxis": {
                "type": "category",
                "data": categories,
                "axisLabel": {
                    "interval": 0,
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
            "series": series
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

        if len(working) > 500:
            working = working.sample(500, random_state=42)

        # For low-cardinality numeric columns (like children: 0,1,2,3),
        # add jitter so the scatter isn't just a few vertical lines
        x_series = pd.to_numeric(working[x_col], errors="coerce")
        unique_x = int(x_series.nunique())
        if unique_x <= 10:
            # Use box-style aggregation instead of raw scatter
            x_labels = sorted(x_series.dropna().unique().tolist())
            y_data = []
            for xval in x_labels:
                y_vals = pd.to_numeric(
                    working[working[x_col] == xval][y_col], errors="coerce"
                ).dropna()
                if len(y_vals) > 0:
                    y_data.append(round(float(y_vals.mean()), 2))
                else:
                    y_data.append(0)
            return {
                "tooltip": {"trigger": "axis"},
                "grid": {"left": 70, "right": 30, "top": 50, "bottom": 75},
                "xAxis": {
                    "type": "category",
                    "data": [str(v) for v in x_labels],
                    "name": format_label(x_col),
                    "nameLocation": "middle",
                    "nameGap": 30
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
                    "type": "bar",
                    "data": y_data,
                    "barMaxWidth": 48,
                    "itemStyle": {"borderRadius": [6, 6, 0, 0]}
                }]
            }

        points = [
            [round(float(x), 2), round(float(y), 2)]
            for x, y in zip(
                pd.to_numeric(working[x_col], errors="coerce"),
                pd.to_numeric(working[y_col], errors="coerce")
            )
            if pd.notna(x) and pd.notna(y)
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
                "symbolSize": 8,
                "itemStyle": {"opacity": 0.6}
            }]
        }

    def _build_histogram_option(self, df, target):
        series = pd.to_numeric(df[target], errors="coerce").dropna()

        if len(series) == 0:
            return None

        bins = min(12, max(5, int(math.sqrt(len(series)))))
        bucketed = pd.cut(series, bins=bins, duplicates="drop")
        bucket_counts = bucketed.value_counts(sort=False)

        labels = []
        values = []

        for interval, count in bucket_counts.items():
            labels.append(f"{round(interval.left, 1)} – {round(interval.right, 1)}")
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


# ─────────────────────────────────────────────────────────────────────────────
# Column selection helpers — all question-aware
# ─────────────────────────────────────────────────────────────────────────────

def choose_best_category_column(df, categorical_cols, question, drivers, target=None):
    if not categorical_cols:
        return None

    question = (question or "").lower().strip()
    target = str(target or "").lower().strip()
    driver_set = set(drivers or [])

    scored = []

    for col in categorical_cols:
        col_lower = col.lower()
        nunique = int(df[col].nunique(dropna=True))
        non_null_pct = float(df[col].notna().mean())

        score = 0.0

        # Being in the planner's driver list is a strong signal
        if col in driver_set:
            score += 8.0

        if is_bad_category_column(col, df[col]):
            score -= 100.0

        if 2 <= nunique <= 12:
            score += 4.0
        elif 13 <= nunique <= 20:
            score += 2.5
        elif nunique == 1:
            score -= 5.0
        elif nunique > 40:
            score -= 4.0

        # FIX: heavily weight question token overlap for relevant columns
        question_tokens = set(question.replace("_", " ").split())
        col_tokens = set(col_lower.replace("_", " ").split())
        overlap = len(question_tokens.intersection(col_tokens))
        score += 3.0 * overlap  # Was 0.75 — now much higher weight

        preferred = [
            "region", "country", "state", "city", "category", "segment",
            "channel", "market", "brand", "status", "product", "ship mode",
            "sub-category", "sub category"
        ]
        for pref in preferred:
            if pref in col_lower:
                score += 2.0
            if pref in question and pref in col_lower:
                score += 3.0

        if target and target in col_lower:
            score -= 2.0

        score += non_null_pct

        scored.append((col, score))

    scored.sort(key=lambda x: x[1], reverse=True)
    return scored[0][0] if scored and scored[0][1] > 0 else None


def choose_second_category_column(df, categorical_cols, question, drivers, first_choice, target=None):
    remaining = [c for c in categorical_cols if c != first_choice]
    if not remaining:
        return None
    return choose_best_category_column(df, remaining, question, drivers, target=target)


def choose_third_category_column(df, categorical_cols, question, drivers, used_choices, target=None):
    remaining = [c for c in categorical_cols if c not in used_choices]
    if not remaining:
        return None
    return choose_best_category_column(df, remaining, question, drivers, target=target)


def choose_best_numeric_driver(df, numeric_cols, target, question="", drivers=None):
    """
    FIX: Now heavily weights question relevance and driver list membership.
    Previously picked any high-variance numeric column, causing irrelevant
    supporting charts like "stays_in_weekend_nights vs adr" on every question.
    """
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

        # Being in the planner driver list means the LLM said this is relevant
        if col in driver_set:
            score += 10.0

        # FIX: heavy question token overlap — if the user asked about "children"
        # the scatter should show "children vs adr", not random numeric column
        question_tokens = set(question.replace("_", " ").split())
        col_tokens = set(col_lower.replace("_", " ").split())
        overlap = len(question_tokens.intersection(col_tokens))
        score += 5.0 * overlap

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
            score += 1.0

        keywords = [
            "sales", "revenue", "profit", "cost", "price", "amount",
            "quantity", "discount", "margin", "score", "rate", "value",
            
        ]
        for kw in keywords:
            if kw in col_lower:
                score += 1.5
            if kw in question and kw in col_lower:
                score += 3.0

        usable.append((col, score))

    usable.sort(key=lambda x: x[1], reverse=True)
    return usable[0][0] if usable else None


def choose_second_numeric_driver(df, numeric_cols, target, question="", drivers=None, first_choice=None):
    remaining = [c for c in numeric_cols if c != first_choice]
    return choose_best_numeric_driver(df, remaining, target, question=question, drivers=drivers)


def is_bad_numeric_driver_column(col_name, series):
    name = str(col_name).strip().lower()

    id_like_keywords = [
        "id", "row id", "row_id", "rowid",
        "postal code", "postal", "zip", "zipcode",
        "transaction id", "order id", "customer id", "product id"
    ]
    if any(token in name for token in id_like_keywords):
        return True

    # FIX: year/month integer columns should not be used as scatter numeric drivers
    date_like = ["year", "month", "quarter", "week", "day"]
    if any(k in name for k in date_like):
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
    """
    Select best time column from actual datetime64 dtype columns only.
    Strongly prefers full datetime columns (wide date range) over date-part
    component columns (year-only or month-only).
    """
    if not datetime_cols:
        return None

    question = (question or "").lower().strip()
    driver_set = set(drivers or [])
    scored = []

    for col in datetime_cols:
        col_lower = col.lower().strip().replace("_", " ")
        non_null_pct = float(df[col].notna().mean())

        score = 0.0

        if col in driver_set:
            score += 4.0

        # Wide date range = full datetime column (not just a month or year component).
        # Generic detection — no dataset-specific column names needed.
        try:
            valid = df[col].dropna()
            if len(valid) > 1:
                range_days = (valid.max() - valid.min()).days
                if range_days > 365:
                    score += 10.0   # multi-year: synthesised full date or real date col
                elif range_days > 90:
                    score += 5.0
                elif range_days > 30:
                    score += 2.0
                else:
                    score -= 5.0    # narrow range = date-part column, avoid for trends
        except Exception:
            pass

        # Full date column names (contain "date"/"timestamp" but NOT a date-part word)
        date_part_words = {"year", "month", "week", "day", "quarter"}
        col_tokens = set(col_lower.replace("_", " ").split())
        if "date" in col_lower and not col_tokens.intersection(date_part_words):
            score += 3.0
        if "timestamp" in col_lower:
            score += 2.0
        if "time" in col_lower:
            score += 1.0
        # Question-token overlap bonus
        q_tokens = set(question.split())
        score += 1.5 * len(q_tokens.intersection(col_tokens))

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