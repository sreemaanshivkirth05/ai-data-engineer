import pandas as pd


class AnalysisAgent:

    def run(self, df, target):
        results = {
            "correlations": {},
            "categorical_drivers": {},
            "top_bottom_segments": {},
            "distribution_summary": {},
            "time_summary": {},
            "concentration_summary": {},
            "outlier_summary": {}
        }

        if target not in df.columns:
            return results

        working_df = df.copy()
        working_df = working_df.dropna(subset=[target])

        if len(working_df) == 0:
            return results

        if not pd.api.types.is_numeric_dtype(working_df[target]):
            return results

        # --------------------------
        # NUMERIC DRIVER ANALYSIS
        # --------------------------
        numeric_cols = working_df.select_dtypes(include=["number"]).columns.tolist()

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
        categorical_cols = working_df.select_dtypes(include=["object"]).columns.tolist()

        for col in categorical_cols:
            try:
                grouped = (
                    working_df.groupby(col, dropna=False)[target]
                    .agg(["mean", "sum", "count"])
                    .reset_index()
                )

                grouped = grouped[grouped["count"] > 0]

                if len(grouped) <= 1:
                    continue

                grouped["mean"] = pd.to_numeric(grouped["mean"], errors="coerce")
                grouped["sum"] = pd.to_numeric(grouped["sum"], errors="coerce")

                mean_variance = grouped["mean"].var()
                total_variance = grouped["sum"].var()

                score = 0.0
                if pd.notna(mean_variance):
                    score += float(mean_variance)
                if pd.notna(total_variance):
                    score += float(total_variance) * 0.1

                results["categorical_drivers"][col] = round(score, 3)

                grouped_sorted = grouped.sort_values("sum", ascending=False)

                top_row = grouped_sorted.iloc[0]
                bottom_row = grouped_sorted.iloc[-1]

                results["top_bottom_segments"][col] = {
                    "top": {
                        "segment": self._safe_label(top_row[col]),
                        "sum": round(float(top_row["sum"]), 2),
                        "mean": round(float(top_row["mean"]), 2),
                        "count": int(top_row["count"])
                    },
                    "bottom": {
                        "segment": self._safe_label(bottom_row[col]),
                        "sum": round(float(bottom_row["sum"]), 2),
                        "mean": round(float(bottom_row["mean"]), 2),
                        "count": int(bottom_row["count"])
                    }
                }

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
                    "q1": round(q1, 2),
                    "q3": round(q3, 2),
                    "iqr": round(iqr, 2)
                }

                results["outlier_summary"] = {
                    "outlier_count": int(len(outliers)),
                    "outlier_pct": round(float(len(outliers)) / len(target_series) * 100, 2)
                }
        except Exception:
            pass

        # --------------------------
        # TIME SUMMARY
        # --------------------------
        try:
            datetime_cols = working_df.select_dtypes(include=["datetime64[ns]"]).columns.tolist()

            if len(datetime_cols) > 0:
                date_col = datetime_cols[0]
                time_df = working_df.dropna(subset=[date_col, target]).copy()

                if len(time_df) > 1:
                    time_df["_period"] = time_df[date_col].dt.to_period("M").astype(str)

                    monthly = (
                        time_df.groupby("_period")[target]
                        .sum()
                        .reset_index()
                        .sort_values("_period")
                    )

                    if len(monthly) >= 2:
                        first_value = float(monthly[target].iloc[0])
                        last_value = float(monthly[target].iloc[-1])

                        if first_value != 0:
                            change_pct = ((last_value - first_value) / abs(first_value)) * 100
                        else:
                            change_pct = None

                        best_idx = monthly[target].idxmax()
                        worst_idx = monthly[target].idxmin()

                        results["time_summary"] = {
                            "date_column": date_col,
                            "period_count": int(len(monthly)),
                            "first_period": str(monthly["_period"].iloc[0]),
                            "last_period": str(monthly["_period"].iloc[-1]),
                            "first_value": round(first_value, 2),
                            "last_value": round(last_value, 2),
                            "change_pct": round(change_pct, 2) if change_pct is not None else None,
                            "best_period": str(monthly.loc[best_idx, "_period"]),
                            "best_period_value": round(float(monthly.loc[best_idx, target]), 2),
                            "worst_period": str(monthly.loc[worst_idx, "_period"]),
                            "worst_period_value": round(float(monthly.loc[worst_idx, target]), 2)
                        }
        except Exception:
            pass

        return results

    def _safe_label(self, value):
        if pd.isna(value):
            return "Unknown"
        return str(value)