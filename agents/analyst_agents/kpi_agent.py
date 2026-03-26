import pandas as pd


class KPIAgent:
    def run(self, df, target, time_column=None, aggregation="sum", drivers=None):
        kpis = {}

        if target not in df.columns:
            return kpis

        working_df = df.copy()
        working_df = working_df.dropna(subset=[target])

        if len(working_df) == 0:
            return kpis

        if not pd.api.types.is_numeric_dtype(working_df[target]):
            working_df[target] = pd.to_numeric(working_df[target], errors="coerce")
            working_df = working_df.dropna(subset=[target])

        if len(working_df) == 0:
            return kpis

        agg = normalize_aggregation(aggregation)
        drivers = drivers or []

        kpis["row_count"] = int(len(working_df))
        kpis["column_count"] = int(len(working_df.columns))
        kpis["non_null_target_count"] = int(working_df[target].notna().sum())
        kpis["null_target_count"] = int(df[target].isna().sum()) if target in df.columns else 0
        kpis["target_coverage_pct"] = round(
            float(working_df[target].notna().sum() / len(df) * 100), 1
        ) if len(df) > 0 else 0.0
        kpis["aggregation_used"] = agg

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

        # time-aware KPIs using planner-selected time column first
        chosen_time_col = None
        datetime_cols = working_df.select_dtypes(include=["datetime64[ns]"]).columns.tolist()

        if time_column and time_column in working_df.columns:
            chosen_time_col = time_column
        elif len(datetime_cols) > 0:
            chosen_time_col = datetime_cols[0]

        if chosen_time_col:
            valid_dates = working_df[chosen_time_col].dropna()

            if len(valid_dates) > 0:
                kpis["date_column_used"] = chosen_time_col
                kpis["date_range_start"] = str(valid_dates.min().date())
                kpis["date_range_end"] = str(valid_dates.max().date())

                try:
                    time_df = working_df.dropna(subset=[chosen_time_col, target]).copy()
                    freq = infer_time_frequency(time_df, chosen_time_col)
                    time_df["_period"] = to_period_string(time_df[chosen_time_col], freq)

                    grouped = (
                        time_df.groupby("_period")[target]
                        .agg(resolve_pandas_agg(agg))
                        .reset_index()
                        .sort_values("_period")
                    )

                    if len(grouped) >= 2:
                        first_value = float(grouped[target].iloc[0])
                        last_value = float(grouped[target].iloc[-1])

                        kpis["time_frequency"] = freq
                        kpis["first_period"] = str(grouped["_period"].iloc[0])
                        kpis["last_period"] = str(grouped["_period"].iloc[-1])
                        kpis["first_period_value"] = round(first_value, 2)
                        kpis["last_period_value"] = round(last_value, 2)

                        if first_value != 0:
                            kpis["period_change_pct"] = round(
                                ((last_value - first_value) / abs(first_value)) * 100, 2
                            )

                        best_idx = grouped[target].idxmax()
                        worst_idx = grouped[target].idxmin()

                        kpis["best_period"] = str(grouped.loc[best_idx, "_period"])
                        kpis["best_period_value"] = round(float(grouped.loc[best_idx, target]), 2)
                        kpis["worst_period"] = str(grouped.loc[worst_idx, "_period"])
                        kpis["worst_period_value"] = round(float(grouped.loc[worst_idx, target]), 2)
                except Exception:
                    pass

        # grouping KPIs using planner-selected drivers first
        categorical_cols = working_df.select_dtypes(include=["object"]).columns.tolist()
        if len(categorical_cols) > 0:
            best_col = self._choose_best_grouping_column(working_df, categorical_cols, drivers=drivers)

            if best_col:
                grouped = (
                    working_df.groupby(best_col, dropna=False)[target]
                    .agg(["sum", "mean", "count", "median"])
                    .sort_values("sum", ascending=False)
                )

                if len(grouped) > 0:
                    top_row = grouped.iloc[0]
                    kpis["top_dimension_name"] = best_col
                    kpis["top_dimension_value"] = self._safe_label(grouped.index[0])
                    kpis["top_dimension_metric"] = round(float(top_row["sum"]), 2)
                    kpis["top_dimension_average"] = round(float(top_row["mean"]), 2)
                    kpis["top_dimension_median"] = round(float(top_row["median"]), 2)
                    kpis["top_dimension_count"] = int(top_row["count"])
                    kpis["unique_groups"] = int(working_df[best_col].nunique(dropna=True))

                    total_target = float(working_df[target].sum())
                    if total_target > 0:
                        kpis["top_dimension_share_pct"] = round(
                            float(top_row["sum"]) / total_target * 100, 2
                        )

                    if len(grouped) > 1:
                        bottom_row = grouped.iloc[-1]
                        kpis["bottom_dimension_value"] = self._safe_label(grouped.index[-1])
                        kpis["bottom_dimension_metric"] = round(float(bottom_row["sum"]), 2)
                        kpis["bottom_dimension_average"] = round(float(bottom_row["mean"]), 2)
                        kpis["bottom_dimension_count"] = int(bottom_row["count"])

        return kpis

    def _choose_best_grouping_column(self, df, categorical_cols, drivers=None):
        drivers = drivers or []

        filtered_cols = []
        for col in categorical_cols:
            nunique = int(df[col].nunique(dropna=True))
            if 1 < nunique <= min(20, max(5, int(len(df) * 0.5))):
                filtered_cols.append(col)

        candidate_cols = filtered_cols if filtered_cols else categorical_cols

        for driver in drivers:
            if driver in candidate_cols:
                return driver

        preferred = [
            "product", "country", "region", "category", "segment",
            "customer", "sales person", "salesperson", "channel", "ship mode"
        ]

        for pref in preferred:
            for col in candidate_cols:
                if pref in col.lower():
                    return col

        return candidate_cols[0] if candidate_cols else None

    def _safe_label(self, value):
        if pd.isna(value):
            return "Unknown"
        return str(value)


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


def to_period_string(series, freq):
    if freq == "Y":
        return series.dt.to_period("Y").astype(str)
    if freq == "Q":
        return series.dt.to_period("Q").astype(str)
    if freq == "W":
        return series.dt.to_period("W").astype(str)
    if freq == "D":
        return series.dt.to_period("D").astype(str)
    return series.dt.to_period("M").astype(str)