import pandas as pd


class KPIAgent:
    def run(self, df, target):
        kpis = {}

        if target not in df.columns:
            return kpis

        working_df = df.copy()
        working_df = working_df.dropna(subset=[target])

        if len(working_df) == 0:
            return kpis

        kpis["row_count"] = int(len(working_df))
        kpis["column_count"] = int(len(working_df.columns))
        kpis["non_null_target_count"] = int(working_df[target].notna().sum())
        kpis["null_target_count"] = int(df[target].isna().sum()) if target in df.columns else 0
        kpis["target_coverage_pct"] = round(float(working_df[target].notna().sum() / len(df) * 100), 1) if len(df) > 0 else 0.0

        if pd.api.types.is_numeric_dtype(working_df[target]):
            target_series = pd.to_numeric(working_df[target], errors="coerce").dropna()

            if len(target_series) > 0:
                kpis["total_target"] = round(float(target_series.sum()), 2)
                kpis["average_target"] = round(float(target_series.mean()), 2)
                kpis["median_target"] = round(float(target_series.median()), 2)
                kpis["min_target"] = round(float(target_series.min()), 2)
                kpis["max_target"] = round(float(target_series.max()), 2)
                kpis["std_target"] = round(float(target_series.std()), 2) if len(target_series) > 1 else 0.0
                kpis["p25_target"] = round(float(target_series.quantile(0.25)), 2)
                kpis["p75_target"] = round(float(target_series.quantile(0.75)), 2)

        datetime_cols = working_df.select_dtypes(include=["datetime64[ns]"]).columns.tolist()
        if len(datetime_cols) > 0:
            date_col = datetime_cols[0]
            valid_dates = working_df[date_col].dropna()

            if len(valid_dates) > 0:
                kpis["date_column_used"] = date_col
                kpis["date_range_start"] = str(valid_dates.min().date())
                kpis["date_range_end"] = str(valid_dates.max().date())

                try:
                    time_df = working_df.dropna(subset=[date_col, target]).copy()
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

                        kpis["first_period"] = str(monthly["_period"].iloc[0])
                        kpis["last_period"] = str(monthly["_period"].iloc[-1])
                        kpis["first_period_value"] = round(first_value, 2)
                        kpis["last_period_value"] = round(last_value, 2)

                        if first_value != 0:
                            kpis["period_change_pct"] = round(((last_value - first_value) / abs(first_value)) * 100, 2)
                except Exception:
                    pass

        categorical_cols = working_df.select_dtypes(include=["object"]).columns.tolist()
        if len(categorical_cols) > 0 and pd.api.types.is_numeric_dtype(working_df[target]):
            best_col = self._choose_best_grouping_column(working_df, categorical_cols)

            if best_col:
                grouped = (
                    working_df.groupby(best_col, dropna=False)[target]
                    .agg(["sum", "mean", "count"])
                    .sort_values("sum", ascending=False)
                )

                if len(grouped) > 0:
                    top_row = grouped.iloc[0]
                    kpis["top_dimension_name"] = best_col
                    kpis["top_dimension_value"] = self._safe_label(grouped.index[0])
                    kpis["top_dimension_metric"] = round(float(top_row["sum"]), 2)
                    kpis["top_dimension_average"] = round(float(top_row["mean"]), 2)
                    kpis["top_dimension_count"] = int(top_row["count"])
                    kpis["unique_groups"] = int(working_df[best_col].nunique(dropna=True))

                    total_target = float(working_df[target].sum())
                    if total_target > 0:
                        kpis["top_dimension_share_pct"] = round(float(top_row["sum"]) / total_target * 100, 2)

                    if len(grouped) > 1:
                        bottom_row = grouped.iloc[-1]
                        kpis["bottom_dimension_value"] = self._safe_label(grouped.index[-1])
                        kpis["bottom_dimension_metric"] = round(float(bottom_row["sum"]), 2)

        return kpis

    def _choose_best_grouping_column(self, df, categorical_cols):
        preferred = [
            "product", "country", "region", "category", "segment",
            "customer", "sales person", "salesperson", "channel"
        ]

        filtered_cols = []
        for col in categorical_cols:
            nunique = int(df[col].nunique(dropna=True))
            if 1 < nunique <= min(20, max(5, int(len(df) * 0.5))):
                filtered_cols.append(col)

        candidate_cols = filtered_cols if filtered_cols else categorical_cols

        for pref in preferred:
            for col in candidate_cols:
                if pref in col.lower():
                    return col

        return candidate_cols[0] if candidate_cols else None

    def _safe_label(self, value):
        if pd.isna(value):
            return "Unknown"
        return str(value)