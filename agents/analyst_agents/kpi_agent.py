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

        # Numeric target KPIs
        if pd.api.types.is_numeric_dtype(working_df[target]):
            kpis["total_target"] = round(float(working_df[target].sum()), 2)
            kpis["average_target"] = round(float(working_df[target].mean()), 2)
            kpis["median_target"] = round(float(working_df[target].median()), 2)
            kpis["min_target"] = round(float(working_df[target].min()), 2)
            kpis["max_target"] = round(float(working_df[target].max()), 2)

        # Date range KPI
        datetime_cols = working_df.select_dtypes(include=["datetime64[ns]"]).columns.tolist()
        if len(datetime_cols) > 0:
            date_col = datetime_cols[0]
            if working_df[date_col].notna().any():
                kpis["date_range_start"] = str(working_df[date_col].min().date())
                kpis["date_range_end"] = str(working_df[date_col].max().date())

        # Top category KPI
        categorical_cols = working_df.select_dtypes(include=["object"]).columns.tolist()
        if len(categorical_cols) > 0 and pd.api.types.is_numeric_dtype(working_df[target]):
            best_col = self._choose_best_grouping_column(working_df, categorical_cols)

            if best_col:
                grouped = working_df.groupby(best_col)[target].sum().sort_values(ascending=False)
                if len(grouped) > 0:
                    kpis["top_dimension_name"] = best_col
                    kpis["top_dimension_value"] = str(grouped.index[0])
                    kpis["top_dimension_metric"] = round(float(grouped.iloc[0]), 2)
                    kpis["unique_groups"] = int(working_df[best_col].nunique())

        return kpis

    def _choose_best_grouping_column(self, df, categorical_cols):
        preferred = ["product", "country", "region", "category", "segment", "customer", "sales person", "channel"]

        for pref in preferred:
            for col in categorical_cols:
                if pref in col.lower():
                    return col

        return categorical_cols[0] if categorical_cols else None