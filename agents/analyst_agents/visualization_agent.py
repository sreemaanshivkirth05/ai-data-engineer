import math
import pandas as pd


class VisualizationAgent:

    def run(self, df, target, question="", intent="general_analysis", drivers=None):
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

        q = question.lower()
        drivers = drivers or []

        chart_plan = self._plan_visuals(
            df=working_df,
            question=q,
            intent=intent,
            target=target,
            drivers=drivers,
            numeric_cols=numeric_cols,
            categorical_cols=categorical_cols,
            datetime_cols=datetime_cols
        )

        for idx, item in enumerate(chart_plan):
            try:
                option = None
                chart_type = item["type"]
                title = item["title"]
                description = item["description"]

                if chart_type == "bar":
                    option = self._build_bar_option(
                        working_df,
                        category_col=item["category_col"],
                        target=target,
                        title=title
                    )

                elif chart_type == "line":
                    option = self._build_time_series_option(
                        working_df,
                        date_col=item["date_col"],
                        target=target,
                        title=title
                    )

                elif chart_type == "donut":
                    option = self._build_donut_option(
                        working_df,
                        category_col=item["category_col"],
                        target=target,
                        title=title
                    )

                elif chart_type == "scatter":
                    option = self._build_scatter_option(
                        working_df,
                        x_col=item["x_col"],
                        y_col=target,
                        title=title
                    )

                elif chart_type == "histogram":
                    option = self._build_histogram_option(
                        working_df,
                        target=target,
                        title=title
                    )

                if option is None:
                    continue

                charts.append({
                    "type": chart_type,
                    "title": title,
                    "description": description,
                    "primary": idx == 0,
                    "option": option
                })

            except Exception as e:
                print(f"Visualization error for {item}: {e}")

        return charts

    # -------------------------------------------------
    # HYBRID CHART PLANNER
    # -------------------------------------------------
    def _plan_visuals(
        self,
        df,
        question,
        intent,
        target,
        drivers,
        numeric_cols,
        categorical_cols,
        datetime_cols
    ):
        plans = []

        best_cat = choose_best_category_column(df, categorical_cols, question, drivers)
        best_num = choose_best_numeric_driver(numeric_cols, target)

        # Primary chart
        if ("trend" in question or "over time" in question or intent == "trend_analysis") and datetime_cols:
            plans.append({
                "type": "line",
                "date_col": datetime_cols[0],
                "title": f"{format_label(target)} over time",
                "description": f"Shows how {format_label(target).lower()} changes over time and highlights the overall performance direction."
            })
        elif (
            "compare" in question
            or "top" in question
            or "best" in question
            or "highest" in question
            or "country" in question
            or "product" in question
            or "sales person" in question
            or intent in ["comparison", "summary_analysis"]
        ) and best_cat:
            plans.append({
                "type": "bar",
                "category_col": best_cat,
                "title": f"Top {format_label(best_cat).lower()} by {format_label(target).lower()}",
                "description": f"Ranks the leading {format_label(best_cat).lower()} based on total {format_label(target).lower()}."
            })
        elif (
            "relationship" in question
            or "correlation" in question
            or "impact" in question
            or "affect" in question
            or "influence" in question
            or intent == "relationship_analysis"
        ) and best_num:
            plans.append({
                "type": "scatter",
                "x_col": best_num,
                "title": f"{format_label(best_num)} vs {format_label(target)}",
                "description": f"Shows whether changes in {format_label(best_num).lower()} are associated with changes in {format_label(target).lower()}."
            })
        else:
            if best_cat:
                plans.append({
                    "type": "bar",
                    "category_col": best_cat,
                    "title": f"{format_label(target)} by {format_label(best_cat)}",
                    "description": f"Provides the clearest category-level view of {format_label(target).lower()}."
                })
            elif datetime_cols:
                plans.append({
                    "type": "line",
                    "date_col": datetime_cols[0],
                    "title": f"{format_label(target)} over time",
                    "description": f"Shows the overall time trend for {format_label(target).lower()}."
                })
            else:
                plans.append({
                    "type": "histogram",
                    "title": f"Distribution of {format_label(target).lower()}",
                    "description": f"Shows how {format_label(target).lower()} values are distributed across the dataset."
                })

        # Support charts
        if best_cat and not any(p["type"] == "bar" for p in plans):
            plans.append({
                "type": "bar",
                "category_col": best_cat,
                "title": f"{format_label(target)} by {format_label(best_cat)}",
                "description": f"Compares total {format_label(target).lower()} across {format_label(best_cat).lower()}."
            })

        if datetime_cols and not any(p["type"] == "line" for p in plans):
            plans.append({
                "type": "line",
                "date_col": datetime_cols[0],
                "title": f"{format_label(target)} over time",
                "description": f"Shows how {format_label(target).lower()} moves across time."
            })

        if best_cat and df[best_cat].nunique(dropna=True) <= 6 and not any(p["type"] == "donut" for p in plans):
            plans.append({
                "type": "donut",
                "category_col": best_cat,
                "title": f"Share of {format_label(target).lower()} by {format_label(best_cat).lower()}",
                "description": f"Shows how total {format_label(target).lower()} is distributed across {format_label(best_cat).lower()}."
            })

        if best_num and not any(p["type"] == "scatter" for p in plans):
            plans.append({
                "type": "scatter",
                "x_col": best_num,
                "title": f"{format_label(best_num)} vs {format_label(target)}",
                "description": f"Explores the relationship between {format_label(best_num).lower()} and {format_label(target).lower()}."
            })

        if not any(p["type"] == "histogram" for p in plans):
            plans.append({
                "type": "histogram",
                "title": f"Distribution of {format_label(target).lower()}",
                "description": f"Shows the spread and concentration of {format_label(target).lower()} values."
            })

        # guarantee minimum 4 charts
        deduped = []
        seen = set()

        for p in plans:
            key = (
                p["type"],
                p.get("category_col"),
                p.get("date_col"),
                p.get("x_col"),
                p.get("title")
            )
            if key not in seen:
                deduped.append(p)
                seen.add(key)

        if len(deduped) < 4:
            for driver in drivers:
                if driver in categorical_cols and driver != best_cat:
                    extra = {
                        "type": "bar",
                        "category_col": driver,
                        "title": f"{format_label(target)} by {format_label(driver)}",
                        "description": f"Gives an additional comparison of {format_label(target).lower()} across {format_label(driver).lower()}."
                    }
                    key = ("bar", driver, None, None, extra["title"])
                    if key not in seen:
                        deduped.append(extra)
                        seen.add(key)
                    if len(deduped) >= 4:
                        break

        return deduped[:4]

    # -------------------------------------------------
    # ECHARTS OPTION BUILDERS
    # -------------------------------------------------
    def _base_option(self, title):
        return {
            "backgroundColor": "transparent",
            "animation": True,
            "grid": {"left": 70, "right": 30, "top": 70, "bottom": 60},
            "title": {
                "text": title,
                "left": 16,
                "top": 14,
                "textStyle": {
                    "fontSize": 18,
                    "fontWeight": 700,
                    "color": "#0f172a"
                }
            },
            "tooltip": {
                "trigger": "item",
                "backgroundColor": "#ffffff",
                "borderColor": "#e2e8f0",
                "borderWidth": 1,
                "textStyle": {
                    "color": "#0f172a"
                }
            }
        }

    def _build_bar_option(self, df, category_col, target, title):
        grouped = (
            df.groupby(category_col, dropna=False)[target]
            .sum()
            .reset_index()
            .sort_values(target, ascending=False)
            .head(10)
        )
        grouped[category_col] = grouped[category_col].astype(str)

        categories = grouped[category_col].tolist()[::-1]
        values = grouped[target].tolist()[::-1]

        option = self._base_option(title)
        option.update({
            "xAxis": {
                "type": "value",
                "name": format_label(target),
                "axisLabel": {
                    "formatter": "${value}" if is_money_like(target) else "{value}"
                },
                "splitLine": {"lineStyle": {"color": "#e5e7eb"}}
            },
            "yAxis": {
                "type": "category",
                "data": categories,
                "name": format_label(category_col),
                "axisLabel": {
                    "width": 120,
                    "overflow": "truncate"
                }
            },
            "series": [{
                "type": "bar",
                "data": values,
                "barWidth": 22,
                "itemStyle": {
                    "color": "#2563eb",
                    "borderRadius": [0, 8, 8, 0]
                },
                "label": {
                    "show": True,
                    "position": "right",
                    "formatter": "${@[0]}" if is_money_like(target) else "{@[0]}"
                }
            }]
        })
        return option

    def _build_time_series_option(self, df, date_col, target, title):
        temp_df = df[[date_col, target]].dropna().copy()
        temp_df["period"] = temp_df[date_col].dt.to_period("M").dt.to_timestamp()

        grouped = (
            temp_df.groupby("period")[target]
            .sum()
            .reset_index()
            .sort_values("period")
        )

        x_data = grouped["period"].dt.strftime("%b %Y").tolist()
        y_data = grouped[target].round(2).tolist()

        option = self._base_option(title)
        option.update({
            "xAxis": {
                "type": "category",
                "data": x_data,
                "axisLabel": {
                    "rotate": 35
                }
            },
            "yAxis": {
                "type": "value",
                "name": format_label(target),
                "axisLabel": {
                    "formatter": "${value}" if is_money_like(target) else "{value}"
                },
                "splitLine": {"lineStyle": {"color": "#e5e7eb"}}
            },
            "series": [{
                "type": "line",
                "data": y_data,
                "smooth": True,
                "symbolSize": 8,
                "lineStyle": {"width": 3, "color": "#2563eb"},
                "itemStyle": {"color": "#2563eb"},
                "areaStyle": {"color": "rgba(37, 99, 235, 0.10)"}
            }]
        })
        return option

    def _build_donut_option(self, df, category_col, target, title):
        grouped = (
            df.groupby(category_col, dropna=False)[target]
            .sum()
            .reset_index()
            .sort_values(target, ascending=False)
            .head(6)
        )

        data = [
            {"name": str(row[category_col]), "value": round(float(row[target]), 2)}
            for _, row in grouped.iterrows()
        ]

        option = self._base_option(title)
        option.update({
            "legend": {
                "bottom": 10,
                "left": "center"
            },
            "series": [{
                "type": "pie",
                "radius": ["48%", "70%"],
                "center": ["50%", "52%"],
                "label": {
                    "formatter": "{b}\n{d}%"
                },
                "data": data
            }]
        })
        return option

    def _build_scatter_option(self, df, x_col, y_col, title):
        temp_df = df[[x_col, y_col]].dropna()
        if len(temp_df) < 2:
            return None

        data = temp_df[[x_col, y_col]].values.tolist()

        option = self._base_option(title)
        option.update({
            "xAxis": {
                "type": "value",
                "name": format_label(x_col),
                "splitLine": {"lineStyle": {"color": "#e5e7eb"}}
            },
            "yAxis": {
                "type": "value",
                "name": format_label(y_col),
                "axisLabel": {
                    "formatter": "${value}" if is_money_like(y_col) else "{value}"
                },
                "splitLine": {"lineStyle": {"color": "#e5e7eb"}}
            },
            "series": [{
                "type": "scatter",
                "data": data,
                "symbolSize": 10,
                "itemStyle": {
                    "color": "#2563eb",
                    "opacity": 0.75
                }
            }]
        })
        return option

    def _build_histogram_option(self, df, target, title):
        temp_df = df[[target]].dropna().copy()

        q_low = temp_df[target].quantile(0.01)
        q_high = temp_df[target].quantile(0.99)
        temp_df = temp_df[(temp_df[target] >= q_low) & (temp_df[target] <= q_high)]

        values = temp_df[target].tolist()
        if len(values) == 0:
            return None

        min_v = min(values)
        max_v = max(values)
        bins = 20
        bin_size = (max_v - min_v) / bins if max_v != min_v else 1

        counts = [0] * bins
        labels = []

        for i in range(bins):
            start = min_v + i * bin_size
            end = start + bin_size
            labels.append(f"{round(start, 0)} - {round(end, 0)}")

        for v in values:
            idx = min(int((v - min_v) / bin_size), bins - 1) if bin_size > 0 else 0
            counts[idx] += 1

        option = self._base_option(title)
        option.update({
            "xAxis": {
                "type": "category",
                "data": labels,
                "axisLabel": {
                    "rotate": 35
                }
            },
            "yAxis": {
                "type": "value",
                "name": "Count",
                "splitLine": {"lineStyle": {"color": "#e5e7eb"}}
            },
            "series": [{
                "type": "bar",
                "data": counts,
                "barWidth": "85%",
                "itemStyle": {
                    "color": "#2563eb",
                    "borderRadius": [6, 6, 0, 0]
                }
            }]
        })
        return option

    # -------------------------------------------------
    # DATA PREP
    # -------------------------------------------------
    def _prepare_dataframe(self, df, target):
        df.columns = [str(col).strip() for col in df.columns]

        df[target] = (
            df[target]
            .astype(str)
            .str.replace(r"[^\d\.\-]", "", regex=True)
            .str.strip()
        )
        df[target] = pd.to_numeric(df[target], errors="coerce")

        for col in df.columns:
            if "date" in col.lower() or "time" in col.lower():
                df[col] = pd.to_datetime(df[col], errors="coerce")

        for col in df.columns:
            if col == target:
                continue
            if df[col].dtype == "object":
                cleaned = (
                    df[col]
                    .astype(str)
                    .str.replace(r"[^\d\.\-]", "", regex=True)
                    .str.strip()
                )
                numeric_candidate = pd.to_numeric(cleaned, errors="coerce")
                if numeric_candidate.notna().sum() > len(df) * 0.7:
                    df[col] = numeric_candidate

        return df


def choose_best_category_column(df, categorical_cols, question_text, drivers=None):
    q = question_text.lower()
    drivers = drivers or []

    for driver in drivers:
        if driver in categorical_cols:
            return driver

    priorities = [
        ("product", "Product"),
        ("country", "Country"),
        ("region", "Region"),
        ("sales person", "Sales Person"),
        ("channel", "Channel"),
        ("category", "Category"),
        ("segment", "Segment"),
        ("customer", "Customer")
    ]

    for key, pretty_name in priorities:
        if key in q:
            for col in categorical_cols:
                if col.lower() == pretty_name.lower():
                    return col
                if key in col.lower():
                    return col

    for _, pretty_name in priorities:
        for col in categorical_cols:
            if col.lower() == pretty_name.lower():
                return col

    return categorical_cols[0] if categorical_cols else None


def choose_best_numeric_driver(numeric_cols, target):
    for col in numeric_cols:
        if col != target:
            return col
    return None


def format_label(column_name):
    return str(column_name).replace("_", " ").strip().title()


def is_money_like(column_name):
    col = str(column_name).lower()
    return any(word in col for word in ["amount", "revenue", "price", "cost", "profit"])