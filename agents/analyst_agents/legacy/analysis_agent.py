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
            "performance_diagnostics": {},
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
        datetime_cols = working_df.select_dtypes(include=["datetime64[ns]", "datetime64[ns, UTC]"]).columns.tolist()

        for col in numeric_cols:
            if col == target:
                continue

            if self._is_bad_numeric_signal_column(col, working_df[col]):
                continue

            try:
                pair_df = working_df[[target, col]].dropna()
                if len(pair_df) < 3:
                    continue

                corr = pair_df[target].corr(pair_df[col])

                if pd.notna(corr):
                    if abs(float(corr)) < 0.05:
                        continue
                    results["correlations"][col] = round(float(corr), 3)
            except Exception:
                continue

        preferred_cats = self._rank_categorical_columns(categorical_cols, drivers)

        for col in preferred_cats:
            try:
                nunique = int(working_df[col].nunique(dropna=True))
                non_null_pct = float(working_df[col].notna().mean())

                if nunique <= 1:
                    continue
                if nunique > min(30, max(12, int(len(working_df) * 0.35))):
                    continue
                if non_null_pct < 0.40:
                    continue

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

                grouped["_label"] = grouped[col].apply(self._safe_label)
                grouped["_is_placeholder"] = grouped["_label"].apply(self._is_placeholder_label)

                mean_variance = grouped["mean"].var()
                total_variance = grouped["sum"].var()

                score = 0.0
                if pd.notna(mean_variance):
                    score += float(mean_variance)
                if pd.notna(total_variance):
                    score += float(total_variance) * 0.10

                if col in drivers:
                    score *= 1.15

                results["categorical_drivers"][col] = round(score, 3)

                metric_col = self._choose_group_metric_column(aggregation)
                if metric_col not in grouped.columns:
                    metric_col = "sum"

                grouped_sorted = grouped.sort_values(metric_col, ascending=False)

                preferred_sorted = grouped_sorted[~grouped_sorted["_is_placeholder"]].copy()
                leadership_df = preferred_sorted if len(preferred_sorted) > 0 else grouped_sorted

                top_row = leadership_df.iloc[0]
                bottom_row = leadership_df.iloc[-1]

                total_target = float(working_df[target].sum())
                total_records = int(len(working_df))

                top_info = {
                    "dimension": col,
                    "segment": self._safe_label(top_row[col]),
                    "total_target": round(float(top_row["sum"]), 2),
                    "average_target": round(float(top_row["mean"]), 2),
                    "median_target": round(float(top_row["median"]), 2),
                    "count": int(top_row["count"]),
                    "share_pct": round((float(top_row["sum"]) / total_target * 100), 2) if total_target > 0 else None
                }

                bottom_info = {
                    "dimension": col,
                    "segment": self._safe_label(bottom_row[col]),
                    "total_target": round(float(bottom_row["sum"]), 2),
                    "average_target": round(float(bottom_row["mean"]), 2),
                    "median_target": round(float(bottom_row["median"]), 2),
                    "count": int(bottom_row["count"]),
                    "share_pct": round((float(bottom_row["sum"]) / total_target * 100), 2) if total_target > 0 else None
                }

                results["top_bottom_segments"][col] = {
                    "top": top_info,
                    "bottom": bottom_info
                }

                results["top_segments"].append(top_info)
                results["bottom_segments"].append(bottom_info)

                if total_target > 0:
                    grouped_sorted["share_pct"] = (grouped_sorted["sum"] / total_target) * 100
                    grouped_sorted["cumulative_share_pct"] = grouped_sorted["share_pct"].cumsum()

                    top_3_share = float(grouped_sorted["share_pct"].head(3).sum())
                    top_5_share = float(grouped_sorted["share_pct"].head(5).sum()) if len(grouped_sorted) >= 5 else float(grouped_sorted["share_pct"].sum())

                    results["concentration_summary"][col] = {
                        "top_segment": self._safe_label(top_row[col]),
                        "top_segment_share_pct": round(float(top_row["sum"] / total_target * 100), 2) if total_target > 0 else None,
                        "top_3_share_pct": round(top_3_share, 2),
                        "top_5_share_pct": round(top_5_share, 2),
                        "group_count": int(grouped[col].nunique()),
                        "concentration_risk": self._classify_concentration_risk(top_3_share)
                    }

                high_total_low_avg = grouped[
                    (grouped["sum"] >= grouped["sum"].median()) &
                    (grouped["mean"] < grouped["mean"].median())
                ]

                high_avg_low_volume = grouped[
                    (grouped["mean"] >= grouped["mean"].median()) &
                    (grouped["count"] < grouped["count"].median())
                ]

                long_tail_segments = grouped[grouped["count"] <= grouped["count"].quantile(0.25)]

                results["performance_diagnostics"][col] = {
                    "high_total_low_avg_segments": [
                        self._safe_label(v) for v in high_total_low_avg[col].head(3).tolist()
                        if not self._is_placeholder_label(self._safe_label(v))
                    ],
                    "high_avg_low_volume_segments": [
                        self._safe_label(v) for v in high_avg_low_volume[col].head(3).tolist()
                        if not self._is_placeholder_label(self._safe_label(v))
                    ],
                    "long_tail_segment_count": int(len(long_tail_segments)),
                    "records_covered_pct": round((grouped["count"].sum() / total_records) * 100, 2) if total_records > 0 else None
                }

            except Exception:
                continue

        results["top_segments"] = self._sort_segments(self._dedupe_segment_list(results["top_segments"]))[:5]
        results["bottom_segments"] = self._sort_segments(self._dedupe_segment_list(results["bottom_segments"]), reverse=False)[:5]

        try:
            target_series = pd.to_numeric(working_df[target], errors="coerce").dropna()

            if len(target_series) > 0:
                q1 = float(target_series.quantile(0.25))
                q3 = float(target_series.quantile(0.75))
                iqr = q3 - q1
                lower_bound = q1 - 1.5 * iqr
                upper_bound = q3 + 1.5 * iqr

                outliers = target_series[(target_series < lower_bound) | (target_series > upper_bound)]

                skew_direction = "balanced"
                mean_value = float(target_series.mean())
                median_value = float(target_series.median())

                if mean_value > median_value * 1.10:
                    skew_direction = "right_skewed"
                elif median_value > mean_value * 1.10:
                    skew_direction = "left_skewed"

                results["distribution_summary"] = {
                    "mean": round(mean_value, 2),
                    "median": round(median_value, 2),
                    "std": round(float(target_series.std()), 2) if len(target_series) > 1 else 0.0,
                    "min": round(float(target_series.min()), 2),
                    "max": round(float(target_series.max()), 2),
                    "q1": round(q1, 2),
                    "q3": round(q3, 2),
                    "iqr": round(iqr, 2),
                    "skew_direction": skew_direction
                }

                results["outlier_summary"] = {
                    "outlier_count": int(len(outliers)),
                    "outlier_pct": round(float(len(outliers)) / len(target_series) * 100, 2),
                    "lower_bound": round(lower_bound, 2),
                    "upper_bound": round(upper_bound, 2)
                }
        except Exception:
            pass

        try:
            chosen_time_col = None

            if time_column and time_column in working_df.columns:
                # Only use provided time_column if it is actual datetime dtype
                if pd.api.types.is_datetime64_any_dtype(working_df[time_column]):
                    chosen_time_col = time_column
            
            if not chosen_time_col and datetime_cols:
                # Generic: prefer full datetime columns over date-part components.
                # Score by date range width — wider range = higher precision column.
                # No dataset-specific column names hardcoded.
                best_col = None
                best_score = -1
                for col in datetime_cols:
                    score = 0.0
                    col_lower = col.lower().strip().replace("_", " ")
                    col_tokens = set(col_lower.split())
                    date_part_words = {"year", "month", "week", "day", "quarter"}

                    # Wide date range = full datetime column
                    try:
                        valid = working_df[col].dropna()
                        if len(valid) > 1:
                            days = (valid.max() - valid.min()).days
                            if days > 365:
                                score += 10.0
                            elif days > 90:
                                score += 5.0
                            elif days > 30:
                                score += 2.0
                            else:
                                score -= 5.0  # narrow = component column
                    except Exception:
                        pass

                    # Full date name bonus
                    if "date" in col_lower and not col_tokens.intersection(date_part_words):
                        score += 3.0
                    if "timestamp" in col_lower:
                        score += 2.0

                    if score > best_score:
                        best_score = score
                        best_col = col
                chosen_time_col = best_col

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

                        grouped["period_change"] = grouped[target].diff()
                        grouped["pct_change"] = grouped[target].pct_change() * 100

                        recent_momentum = None
                        if len(grouped) >= 3:
                            recent_slice = grouped[target].tail(3)
                            if len(recent_slice) >= 2 and recent_slice.iloc[0] != 0:
                                recent_momentum = ((recent_slice.iloc[-1] - recent_slice.iloc[0]) / abs(recent_slice.iloc[0])) * 100

                        volatility_level = self._classify_volatility(grouped[target])

                        results["time_summary"] = {
                            "date_column": chosen_time_col,
                            "frequency": freq,
                            "period_count": int(len(grouped)),
                            "first_period": str(grouped["_period"].iloc[0]),
                            "last_period": str(grouped["_period"].iloc[-1]),
                            "first_value": round(first_value, 2),
                            "last_value": round(last_value, 2),
                            "change_pct": round(change_pct, 2) if change_pct is not None else None,
                            "trend_direction": self._classify_trend_direction(change_pct),
                            "recent_momentum_pct": round(recent_momentum, 2) if recent_momentum is not None else None,
                            "volatility_level": volatility_level,
                            "best_period": str(grouped.loc[best_idx, "_period"]),
                            "best_period_value": round(float(grouped.loc[best_idx, target]), 2),
                            "worst_period": str(grouped.loc[worst_idx, "_period"]),
                            "worst_period_value": round(float(grouped.loc[worst_idx, target]), 2)
                        }
        except Exception:
            pass

        return results

    def _is_bad_numeric_signal_column(self, col_name, series):
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
            "channel", "customer", "ship mode", "market", "brand", "status"
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

    def _sort_segments(self, items, reverse=True):
        return sorted(
            items,
            key=lambda x: (
                x.get("share_pct") if x.get("share_pct") is not None else x.get("total_target", 0),
                x.get("total_target", 0)
            ),
            reverse=reverse
        )

    def _classify_concentration_risk(self, top_3_share):
        if top_3_share is None:
            return "unknown"
        if top_3_share >= 75:
            return "high"
        if top_3_share >= 50:
            return "moderate"
        return "low"

    def _classify_trend_direction(self, change_pct):
        if change_pct is None:
            return "unknown"
        if change_pct > 3:
            return "increasing"
        if change_pct < -3:
            return "decreasing"
        return "stable"

    def _classify_volatility(self, series):
        try:
            series = pd.to_numeric(series, errors="coerce").dropna()
            if len(series) < 3:
                return "unknown"

            mean_value = float(series.mean())
            std_value = float(series.std())

            if mean_value == 0:
                return "unknown"

            cv = abs(std_value / mean_value)

            if cv >= 0.50:
                return "high"
            if cv >= 0.20:
                return "moderate"
            return "low"
        except Exception:
            return "unknown"

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

    def _is_placeholder_label(self, value):
        value = str(value).strip().lower()
        return value in {"unknown", "error", "n/a", "na", "null", "none", ""}

    def _safe_label(self, value):
        if pd.isna(value):
            return "Unknown"
        return str(value)