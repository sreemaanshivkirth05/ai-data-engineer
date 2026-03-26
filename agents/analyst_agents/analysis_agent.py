import pandas as pd


class AnalysisAgent:

    def run(
        self,
        df,
        target,
        drivers=None,
        intent="general_analysis",
        time_column=None,
        aggregation="sum"
    ):
        results = {
            "correlations": {},
            "categorical_drivers": {},
            "top_segments": [],
            "bottom_segments": [],
            "top_bottom_segments": {},
            "distribution_summary": {},
            "time_summary": {},
            "concentration_summary": {},
            "outlier_summary": {},
            "analysis_metadata": {
                "intent": intent,
                "time_column_used": time_column,
                "aggregation_used": aggregation,
                "driver_priority": drivers or []
            }
        }

        if target not in df.columns:
            return results

        working_df = df.copy()
        working_df = working_df.dropna(subset=[target])

        if len(working_df) == 0:
            return results

        if not pd.api.types.is_numeric_dtype(working_df[target]):
            working_df[target] = pd.to_numeric(working_df[target], errors="coerce")
            working_df = working_df.dropna(subset=[target])

        if len(working_df) == 0:
            return results

        drivers = drivers or []
        aggregation = (aggregation or "sum").lower().strip()
        if aggregation not in {"sum", "avg", "mean", "median", "count", "count_distinct", "none"}:
            aggregation = "sum"

        numeric_cols = working_df.select_dtypes(include=["number"]).columns.tolist()
        categorical_cols = working_df.select_dtypes(include=["object"]).columns.tolist()
        datetime_cols = working_df.select_dtypes(include=["datetime64[ns]"]).columns.tolist()

        # --------------------------
        # NUMERIC DRIVER ANALYSIS
        # --------------------------
        for col in numeric_cols:
            if col == target:
                continue

            try:
                pair_df = working_df[[target, col]].dropna()
                if len(pair_df) < 3:
                    continue

                corr = pair_df[target].corr(pair_df[col])

                if pd.notna(corr):
                    results["correlations"][col] = round(float(corr), 3)
            except Exception:
                continue

        # --------------------------
        # CATEGORICAL DRIVER ANALYSIS
        # --------------------------
        preferred_cats = self._rank_categorical_columns(categorical_cols, drivers)

        for col in preferred_cats:
            try:
                grouped = (
                    working_df.groupby(col, dropna=False)[target]
                    .agg(["sum", "mean", "count", "median"])
                    .reset_index()
                )

                grouped = grouped[grouped["count"] > 0]

                if len(grouped) <= 1:
                    continue

                grouped["sum"] = pd.to_numeric(grouped["sum"], errors="coerce")
                grouped["mean"] = pd.to_numeric(grouped["mean"], errors="coerce")
                grouped["median"] = pd.to_numeric(grouped["median"], errors="coerce")

                mean_variance = grouped["mean"].var()
                total_variance = grouped["sum"].var()

                score = 0.0
                if pd.notna(mean_variance):
                    score += float(mean_variance)
                if pd.notna(total_variance):
                    score += float(total_variance) * 0.10

                results["categorical_drivers"][col] = round(score, 3)

                metric_col = self._choose_group_metric_column(aggregation)
                if metric_col not in grouped.columns:
                    metric_col = "sum"

                grouped_sorted = grouped.sort_values(metric_col, ascending=False)

                top_row = grouped_sorted.iloc[0]
                bottom_row = grouped_sorted.iloc[-1]

                top_info = {
                    "dimension": col,
                    "segment": self._safe_label(top_row[col]),
                    "total_target": round(float(top_row["sum"]), 2),
                    "average_target": round(float(top_row["mean"]), 2),
                    "median_target": round(float(top_row["median"]), 2),
                    "count": int(top_row["count"])
                }

                bottom_info = {
                    "dimension": col,
                    "segment": self._safe_label(bottom_row[col]),
                    "total_target": round(float(bottom_row["sum"]), 2),
                    "average_target": round(float(bottom_row["mean"]), 2),
                    "median_target": round(float(bottom_row["median"]), 2),
                    "count": int(bottom_row["count"])
                }

                results["top_bottom_segments"][col] = {
                    "top": top_info,
                    "bottom": bottom_info
                }

                results["top_segments"].append(top_info)
                results["bottom_segments"].append(bottom_info)

                total_target = float(working_df[target].sum())
                if total_target > 0:
                    top_share = float(top_row["sum"]) / total_target * 100
                    results["concentration_summary"][col] = {
                        "top_segment": self._safe_label(top_row[col]),
                        "top_segment_share_pct": round(top_share, 2),
                        "group_count": int(grouped[col].nunique())
                    }

            except Exception:
                continue

        results["top_segments"] = self._dedupe_segment_list(results["top_segments"])[:5]
        results["bottom_segments"] = self._dedupe_segment_list(results["bottom_segments"])[:5]

        # --------------------------
        # DISTRIBUTION SUMMARY
        # --------------------------
        try:
            target_series = pd.to_numeric(working_df[target], errors="coerce").dropna()

            if len(target_series) > 0:
                q1 = float(target_series.quantile(0.25))
                q3 = float(target_series.quantile(0.75))
                iqr = q3 - q1
                lower_bound = q1 - 1.5 * iqr
                upper_bound = q3 + 1.5 * iqr

                outliers = target_series[(target_series < lower_bound) | (target_series > upper_bound)]

                results["distribution_summary"] = {
                    "mean": round(float(target_series.mean()), 2),
                    "median": round(float(target_series.median()), 2),
                    "std": round(float(target_series.std()), 2) if len(target_series) > 1 else 0.0,
                    "min": round(float(target_series.min()), 2),
                    "max": round(float(target_series.max()), 2),
                    "q1": round(q1, 2),
                    "q3": round(q3, 2),
                    "iqr": round(iqr, 2)
                }

                results["outlier_summary"] = {
                    "outlier_count": int(len(outliers)),
                    "outlier_pct": round(float(len(outliers)) / len(target_series) * 100, 2),
                    "lower_bound": round(lower_bound, 2),
                    "upper_bound": round(upper_bound, 2)
                }
        except Exception:
            pass

        # --------------------------
        # TIME SUMMARY
        # --------------------------
        try:
            chosen_time_col = None

            if time_column and time_column in working_df.columns:
                chosen_time_col = time_column
            elif datetime_cols:
                chosen_time_col = datetime_cols[0]

            results["analysis_metadata"]["time_column_used"] = chosen_time_col

            if chosen_time_col:
                time_df = working_df.dropna(subset=[chosen_time_col, target]).copy()

                if len(time_df) > 1:
                    freq = self._detect_time_frequency(time_df[chosen_time_col])
                    period_code = self._period_code(freq)

                    time_df["_period"] = time_df[chosen_time_col].dt.to_period(period_code).astype(str)

                    if aggregation in {"avg", "mean"}:
                        grouped = time_df.groupby("_period")[target].mean().reset_index()
                    elif aggregation == "median":
                        grouped = time_df.groupby("_period")[target].median().reset_index()
                    elif aggregation == "count":
                        grouped = time_df.groupby("_period")[target].count().reset_index()
                    elif aggregation == "count_distinct":
                        grouped = time_df.groupby("_period")[target].nunique().reset_index()
                    else:
                        grouped = time_df.groupby("_period")[target].sum().reset_index()

                    grouped = grouped.sort_values("_period")

                    if len(grouped) >= 2:
                        first_value = float(grouped[target].iloc[0])
                        last_value = float(grouped[target].iloc[-1])

                        change_pct = None
                        if first_value != 0:
                            change_pct = ((last_value - first_value) / abs(first_value)) * 100

                        best_idx = grouped[target].idxmax()
                        worst_idx = grouped[target].idxmin()

                        results["time_summary"] = {
                            "date_column": chosen_time_col,
                            "frequency": freq,
                            "period_count": int(len(grouped)),
                            "first_period": str(grouped["_period"].iloc[0]),
                            "last_period": str(grouped["_period"].iloc[-1]),
                            "first_value": round(first_value, 2),
                            "last_value": round(last_value, 2),
                            "change_pct": round(change_pct, 2) if change_pct is not None else None,
                            "best_period": str(grouped.loc[best_idx, "_period"]),
                            "best_period_value": round(float(grouped.loc[best_idx, target]), 2),
                            "worst_period": str(grouped.loc[worst_idx, "_period"]),
                            "worst_period_value": round(float(grouped.loc[worst_idx, target]), 2)
                        }
        except Exception:
            pass

        return results

    def _rank_categorical_columns(self, categorical_cols, drivers):
        ranked = []
        seen = set()

        for col in drivers or []:
            if col in categorical_cols and col not in seen:
                ranked.append(col)
                seen.add(col)

        preferred_keywords = [
            "region", "country", "state", "city",
            "category", "segment", "product", "sub category",
            "channel", "customer", "ship mode"
        ]

        for keyword in preferred_keywords:
            for col in categorical_cols:
                if col in seen:
                    continue
                if keyword in col.lower():
                    ranked.append(col)
                    seen.add(col)

        for col in categorical_cols:
            if col not in seen:
                ranked.append(col)
                seen.add(col)

        return ranked

    def _choose_group_metric_column(self, aggregation):
        mapping = {
            "sum": "sum",
            "avg": "mean",
            "mean": "mean",
            "median": "median",
            "count": "count",
            "count_distinct": "count",
            "none": "sum"
        }
        return mapping.get(aggregation, "sum")

    def _detect_time_frequency(self, dt_series):
        clean_series = dt_series.dropna().sort_values()
        if len(clean_series) < 2:
            return "monthly"

        try:
            deltas = clean_series.diff().dropna().dt.days
            if len(deltas) == 0:
                return "monthly"

            median_gap = deltas.median()

            if median_gap <= 2:
                return "daily"
            if median_gap <= 10:
                return "weekly"
            if median_gap <= 45:
                return "monthly"
            if median_gap <= 120:
                return "quarterly"
            return "yearly"
        except Exception:
            return "monthly"

    def _period_code(self, frequency):
        mapping = {
            "daily": "D",
            "weekly": "W",
            "monthly": "M",
            "quarterly": "Q",
            "yearly": "Y"
        }
        return mapping.get(frequency, "M")

    def _dedupe_segment_list(self, items):
        seen = set()
        result = []

        for item in items:
            key = (
                str(item.get("dimension", "")).strip().lower(),
                str(item.get("segment", "")).strip().lower()
            )
            if key not in seen:
                result.append(item)
                seen.add(key)

        return result

    def _safe_label(self, value):
        if pd.isna(value):
            return "Unknown"
        return str(value)