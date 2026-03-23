import pandas as pd


class AnalysisAgent:

    def run(self, df, target):

        results = {
            "correlations": {},
            "categorical_drivers": {}
        }

        # safety check
        if target not in df.columns:
            return results

        # --------------------------
        # NUMERIC DRIVER ANALYSIS
        # --------------------------

        numeric_cols = df.select_dtypes(include=["int64", "float64"]).columns.tolist()

        for col in numeric_cols:

            if col == target:
                continue

            try:
                corr = df[target].corr(df[col])

                if pd.notna(corr):
                    results["correlations"][col] = round(float(corr), 3)

            except Exception:
                continue

        # --------------------------
        # CATEGORICAL DRIVER ANALYSIS
        # --------------------------

        categorical_cols = df.select_dtypes(include=["object"]).columns.tolist()

        for col in categorical_cols:

            try:

                grouped = df.groupby(col)[target].mean()

                if len(grouped) > 1:

                    variance = grouped.var()

                    results["categorical_drivers"][col] = round(float(variance), 3)

            except Exception:
                continue

        return results