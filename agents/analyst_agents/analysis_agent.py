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
                "time_column_used": None,
                "aggregation_used": normalize_aggregation(aggregation),
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

        if len(working_df) == 0 or not pd.api.types.is_numeric_dtype(working_df[target]):
            return results

        drivers = drivers or []
        agg = normalize_aggregation(aggregation)

        numeric_cols = working_df.select_dtypes(include=["number"]).columns.tolist()
        categorical_cols = working_df.select_dtypes(include=["object"]).columns.tolist()
        datetime_cols = working_df.select_dtypes(include=["datetime64[ns]"]).columns.tolist()

        ranked_categorical_cols = rank_categorical_candidates(
            df=working_df,
            categorical_cols=categorical_cols,
            drivers=drivers
        )

        ranked_numeric_cols = rank_numeric_candidates(
            numeric_cols=numeric_cols,
            target=target,
            drivers=drivers
        )

        # numeric relationships
        for col in ranked_numeric_cols:
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

        # categorical drivers
        for col in ranked_categorical_cols:
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

                # boost planner-selected drivers a bit
                if col in drivers:
                    score *= 1.15

                results["categorical_drivers"][col] = round(score, 3)

                grouped_sorted = grouped.sort_values("sum", ascending=False)
                top_row = grouped_sorted.iloc[0]
                bottom_row = grouped_sorted.iloc[-1]

                results["top_bottom_segments"][col] = {
                    "top": {
                        "segment": safe_label(top_row[col]),
                        "sum": round(float(top_row["sum"]), 2),
                        "mean": round(float(top_row["mean"]), 2),
                        "count": int(top_row["count"])
                    },
                    "bottom": {
                        "segment": safe_label(bottom_row[col]),
                        "sum": round(float(bottom_row["sum"]), 2),
                        "mean": round(float(bottom_row["mean"]), 2),
                        "count": int(bottom_row["count"])
                    }
                }

                total_target = float(working_df[target].sum())
                if total_target > 0:
                    top_share = float(top_row["sum"]) / total_target * 100
                    results["concentration_summary"][col] = {
                        "top_segment": safe_label(top_row[col]),
                        "top_segment_share_pct": round(top_share, 2),
                        "group_count": int(grouped[col].nunique())
                    }

            except Exception:
                continue

        # top/bottom segments from strongest categorical driver
        if results["categorical_drivers"]:
            best_cat = sorted(
                results["categorical_drivers"].items(),
                key=lambda x: x[1],
                reverse=True
            )[0][0]

            if best_cat in results["top_bottom_segments"]:
                tb = results["top_bottom_segments"][best_cat]
                results["top_segments"] = [{
                    "dimension": best_cat,
                    "segment": tb["top"]["segment"],
                    "mean_target": tb["top"]["mean"],
                    "total_target": tb["top"]["sum"],
                    "count": tb["top"]["count"]
                }]
                results["bottom_segments"] = [{
                    "dimension": best_cat,
                    "segment": tb["bottom"]["segment"],
                    "mean_target": tb["bottom"]["mean"],
                    "total_target": tb["bottom"]["sum"],
                    "count": tb["bottom"]["count"]
                }]

        # distribution summary
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
                    "iqr": round(iqr, 2),
                    "min": round(float(target_series.min()), 2),
                    "max": round(float(target_series.max()), 2)
                }

                results["outlier_summary"] = {
                    "outlier_count": int(len(outliers)),
                    "outlier_pct": round(float(len(outliers)) / len(target_series) * 100, 2)
                }
        except Exception:
            pass

        # time summary using planner-selected time column first
        try:
            chosen_time_col = None
            if time_column and time_column in working_df.columns:
                chosen_time_col = time_column
            elif datetime_cols:
                chosen_time_col = datetime_cols[0]

            if chosen_time_col:
                time_df = working_df.dropna(subset=[chosen_time_col, target]).copy()

                if len(time_df) > 1:
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

                        change_pct = None
                        if first_value != 0:
                            change_pct = ((last_value - first_value) / abs(first_value)) * 100

                        best_idx = grouped[target].idxmax()
                        worst_idx = grouped[target].idxmin()

                        results["time_summary"] = {
                            "date_column": chosen_time_col,
                            "frequency": freq,
                            "aggregation": agg,
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
                        results["analysis_metadata"]["time_column_used"] = chosen_time_col

        except Exception:
            pass

        return results


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


def rank_categorical_candidates(df, categorical_cols, drivers):
    scored = []

    for col in categorical_cols:
        score = 0.0
        nunique = int(df[col].nunique(dropna=True))

        if col in (drivers or []):
            score += 10.0

        if 1 < nunique <= min(20, max(6, int(len(df) * 0.5))):
            score += 5.0
        elif nunique == 1:
            score -= 10.0
        elif nunique > max(25, int(len(df) * 0.5)):
            score -= 4.0

        col_lower = col.lower()
        preferred = [
            "region", "country", "state", "city",
            "category", "segment", "product", "sub-category",
            "channel", "customer", "ship mode"
        ]
        for idx, keyword in enumerate(preferred):
            if keyword in col_lower:
                score += (len(preferred) - idx) * 0.25

        if "id" in col_lower or "postal" in col_lower or "zip" in col_lower:
            score -= 8.0

        scored.append((col, score))

    scored.sort(key=lambda x: x[1], reverse=True)
    return [col for col, score in scored if score > -5]


def rank_numeric_candidates(numeric_cols, target, drivers):
    scored = []

    for col in numeric_cols:
        if col == target:
            continue

        score = 0.0
        if col in (drivers or []):
            score += 10.0

        col_lower = col.lower()
        if any(word in col_lower for word in ["sales", "profit", "revenue", "cost", "amount", "discount", "quantity", "price"]):
            score += 2.0

        if "id" in col_lower or "postal" in col_lower or "zip" in col_lower:
            score -= 8.0

        scored.append((col, score))

    scored.sort(key=lambda x: x[1], reverse=True)
    return [col for col, _ in scored]


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


def safe_label(value):
    if pd.isna(value):
        return "Unknown"
    return str(value)