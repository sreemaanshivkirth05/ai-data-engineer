import pandas as pd


def normalize_aggregation(aggregation):
    agg = str(aggregation or "sum").lower().strip()
    if agg in {"avg", "average"}:
        return "mean"
    if agg not in {"sum", "mean", "median", "count", "count_distinct", "none"}:
        return "sum"
    return agg


def resolve_pandas_agg(agg):
    if agg == "count_distinct":
        return "nunique"
    if agg == "none":
        return "sum"
    return agg


def infer_time_frequency(df, date_col):
    try:
        series = pd.to_datetime(df[date_col], errors="coerce").dropna().sort_values()
        if len(series) < 3:
            return "M"

        diffs = series.diff().dropna()
        if len(diffs) == 0:
            return "M"

        median_days = diffs.dt.total_seconds().median() / 86400.0

        if median_days <= 2:
            return "D"
        if median_days <= 10:
            return "W"
        if median_days <= 45:
            return "M"
        if median_days <= 120:
            return "Q"
        return "Y"
    except Exception:
        return "M"


def to_period_string(series, freq):
    s = pd.to_datetime(series, errors="coerce")
    if freq == "D":
        return s.dt.strftime("%Y-%m-%d")
    if freq == "W":
        return s.dt.to_period("W").astype(str)
    if freq == "M":
        return s.dt.to_period("M").astype(str)
    if freq == "Q":
        return s.dt.to_period("Q").astype(str)
    if freq == "Y":
        return s.dt.to_period("Y").astype(str)
    return s.dt.to_period("M").astype(str)


class KPIAgent:
    def run(self, df, target, time_column=None, aggregation="sum", drivers=None, question="",
            dataset_context=None):
        kpis = {}
        dataset_context = dataset_context or {}

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
        ranking_direction = self._infer_ranking_direction(question, target=target)

        kpis["row_count"] = int(len(working_df))
        kpis["column_count"] = int(len(working_df.columns))
        kpis["non_null_target_count"] = int(working_df[target].notna().sum())
        kpis["null_target_count"] = int(df[target].isna().sum()) if target in df.columns else 0
        kpis["target_coverage_pct"] = round(
            float(working_df[target].notna().sum() / len(df) * 100), 1
        ) if len(df) > 0 else 0.0
        kpis["aggregation_used"] = agg
        kpis["ranking_direction"] = ranking_direction

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

        # --------------------------
        # TIME-AWARE KPIs
        # FIX: Only use columns with actual datetime64 dtype for date range.
        # Year/month integer columns (e.g. arrival_date_year) were being
        # passed here and producing 1970-01-01 because pandas treated
        # integer 0 as epoch when no valid dates were found.
        # --------------------------
        chosen_time_col = None

        # Only consider columns that are actual datetime64 types
        datetime_cols = [
            col for col in working_df.columns
            if pd.api.types.is_datetime64_any_dtype(working_df[col])
        ]

        if time_column and time_column in working_df.columns:
            # Only use the provided time_column if it is genuinely datetime dtype
            if pd.api.types.is_datetime64_any_dtype(working_df[time_column]):
                chosen_time_col = time_column
            # else: don't use it — it's probably an integer year column
        elif datetime_cols:
            chosen_time_col = self._choose_best_time_column(working_df, datetime_cols, drivers)

        if chosen_time_col:
            valid_dates = working_df[chosen_time_col].dropna()

            if len(valid_dates) > 0:
                try:
                    # Verify the dates are not all NaT or epoch
                    min_date = valid_dates.min()
                    max_date = valid_dates.max()

                    # Guard: skip if dates look like epoch (year 1970)
                    if min_date.year == 1970 and max_date.year == 1970:
                        chosen_time_col = None
                    else:
                        kpis["date_column_used"] = chosen_time_col
                        kpis["date_range_start"] = str(min_date.date())
                        kpis["date_range_end"] = str(max_date.date())

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
                except Exception:
                    chosen_time_col = None

        # If no valid datetime column found, record None (not 1970-01-01)
        if not chosen_time_col:
            kpis["date_range_start"] = None
            kpis["date_range_end"] = None

        # --------------------------
        # GROUPING KPIs
        # --------------------------
        categorical_cols = working_df.select_dtypes(include=["object"]).columns.tolist()
        if len(categorical_cols) > 0:
            best_col = self._choose_best_grouping_column(
                working_df,
                categorical_cols,
                drivers=drivers,
                question=question
            )

            if best_col:
                grouped = (
                    working_df.groupby(best_col, dropna=False)[target]
                    .agg(["sum", "mean", "count", "median"])
                    .reset_index()
                )

                grouped["sum"] = pd.to_numeric(grouped["sum"], errors="coerce")
                grouped["mean"] = pd.to_numeric(grouped["mean"], errors="coerce")
                grouped["median"] = pd.to_numeric(grouped["median"], errors="coerce")

                grouped["_label"] = grouped[best_col].apply(self._safe_label)
                grouped["_is_placeholder"] = grouped["_label"].apply(self._is_placeholder_label)

                preferred_grouped = grouped[~grouped["_is_placeholder"]].copy()
                use_grouped = preferred_grouped if len(preferred_grouped) > 0 else grouped.copy()

                desc_grouped = use_grouped.sort_values("sum", ascending=False)
                asc_grouped = use_grouped.sort_values("sum", ascending=True)

                selected_grouped = asc_grouped if ranking_direction == "ascending" else desc_grouped

                if len(selected_grouped) > 0:
                    lead_row = selected_grouped.iloc[0]
                    best_row = desc_grouped.iloc[0]
                    worst_row = asc_grouped.iloc[0]

                    kpis["top_dimension_name"] = best_col
                    kpis["top_dimension_value"] = self._safe_label(lead_row[best_col])
                    kpis["top_dimension_metric"] = round(float(lead_row["sum"]), 2)
                    kpis["top_dimension_average"] = round(float(lead_row["mean"]), 2)
                    kpis["top_dimension_median"] = round(float(lead_row["median"]), 2)
                    kpis["top_dimension_count"] = int(lead_row["count"])
                    kpis["unique_groups"] = int(working_df[best_col].nunique(dropna=True))

                    total_target = float(working_df[target].sum())
                    if total_target != 0:
                        kpis["top_dimension_share_pct"] = round(
                            float(lead_row["sum"]) / total_target * 100, 2
                        )

                    kpis["best_dimension_value"] = self._safe_label(best_row[best_col])
                    kpis["best_dimension_metric"] = round(float(best_row["sum"]), 2)

                    kpis["worst_dimension_value"] = self._safe_label(worst_row[best_col])
                    kpis["worst_dimension_metric"] = round(float(worst_row["sum"]), 2)

                    if len(selected_grouped) > 1:
                        opposite_grouped = desc_grouped if ranking_direction == "ascending" else asc_grouped
                        bottom_row = opposite_grouped.iloc[0]
                        kpis["bottom_dimension_value"] = self._safe_label(bottom_row[best_col])
                        kpis["bottom_dimension_metric"] = round(float(bottom_row["sum"]), 2)
                        kpis["bottom_dimension_average"] = round(float(bottom_row["mean"]), 2)
                        kpis["bottom_dimension_count"] = int(bottom_row["count"])

                    placeholder_count = int(grouped["_is_placeholder"].sum())
                    if placeholder_count > 0:
                        kpis["group_quality_note"] = (
                            f"{placeholder_count} placeholder group value(s) such as Unknown/ERROR were deprioritized in KPI leadership selection."
                        )

        return kpis

    def _infer_ranking_direction(self, question, target=None):
        q = str(question or "").lower().strip()
        target_lower = str(target or "").lower().strip()

        ascending_terms = {
            "least", "lowest", "bottom", "worst", "smallest", "minimum", "min",
            "least profitable", "least profit", "lowest profit", "lowest sales",
            "lowest revenue", "smallest contribution", "most negative"
        }
        descending_terms = {
            "most", "highest", "top", "leading", "largest", "biggest", "maximum", "max",
            "most profitable", "highest profit", "highest sales", "highest revenue"
        }

        if any(term in q for term in ascending_terms):
            return "ascending"
        if any(term in q for term in descending_terms):
            return "descending"

        if "profit" in target_lower and any(term in q for term in ["least", "lowest", "worst"]):
            return "ascending"

        return "descending"

    # --------------------------
    # Grouping selection
    # --------------------------

    def _choose_best_grouping_column(self, df, categorical_cols, drivers=None, question=""):
        drivers = drivers or []
        q = str(question or "").lower().strip()

        alias_map = {
            "product": {"product", "products", "item", "items", "sku", "chocolate", "chocolates"},
            "country": {"country", "countries", "market", "markets", "geography", "region", "regions"},
            "sales person": {"sales person", "salesperson", "seller", "rep", "representative"},
            "category": {"category", "categories", "segment", "segments", "group", "groups"},
            "sub-category": {"sub-category", "sub category", "subcategory", "subcategories"},
        }

        scored = []

        for col in categorical_cols:
            col_lower = col.lower().strip()
            nunique = int(df[col].nunique(dropna=True))
            non_null_pct = float(df[col].notna().mean())

            score = 0.0

            if col in drivers:
                score += 6.0

            if self._looks_like_identifier(col):
                score -= 100.0

            if nunique <= 1:
                score -= 100.0
            elif 2 <= nunique <= 12:
                score += 5.0
            elif 13 <= nunique <= 25:
                score += 3.0
            elif 26 <= nunique <= 40:
                score += 1.0
            else:
                score -= 5.0

            preferred = [
                "sub-category", "sub category", "category", "segment", "region",
                "ship mode", "channel", "market", "brand", "status", "item",
                "product", "customer type", "department", "country", "sales person"
            ]
            for pref in preferred:
                if pref in col_lower:
                    score += 2.5

            for canonical, terms in alias_map.items():
                if any(term in q for term in terms):
                    if canonical in col_lower:
                        score += 10.0
                    if canonical == "sub-category" and any(term in col_lower for term in ["sub-category", "sub category"]):
                        score += 10.0

            q_tokens = set(q.replace("-", " ").replace("_", " ").split())
            c_tokens = set(col_lower.replace("-", " ").replace("_", " ").split())
            score += 1.5 * len(q_tokens.intersection(c_tokens))

            placeholder_ratio = self._placeholder_ratio(df[col])
            if placeholder_ratio > 0.40:
                score -= 4.0
            elif placeholder_ratio > 0.20:
                score -= 2.0

            score += non_null_pct
            scored.append((col, score))

        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[0][0] if scored and scored[0][1] > 0 else None

    def _choose_best_time_column(self, df, datetime_cols, drivers=None):
        """
        Only called with actual datetime64 dtype columns.
        Strongly prefers synthesised full datetime columns (full year+month+day)
        over component columns. Wide date ranges score much higher.
        """
        drivers = drivers or []
        if not datetime_cols:
            return None

        scored = []
        for col in datetime_cols:
            score = 0.0
            col_lower = col.lower().strip().replace("_", " ")

            if col in drivers:
                score += 5.0

            non_null_pct = float(df[col].notna().mean())
            score += non_null_pct * 3.0

            # Wide date range = full datetime column, not a date-part component.
            # Generic detection — works for any dataset.
            try:
                valid = df[col].dropna()
                if len(valid) > 1:
                    date_range_days = (valid.max() - valid.min()).days
                    if date_range_days > 365:
                        score += 10.0   # multi-year: full datetime column
                    elif date_range_days > 90:
                        score += 5.0
                    elif date_range_days > 30:
                        score += 2.0
                    else:
                        score -= 6.0    # narrow range = component column, avoid
            except Exception:
                pass

            # Full date column names — generic check, no dataset-specific names
            date_part_words = {"year", "month", "week", "day", "quarter"}
            col_tokens = set(col_lower.replace("_", " ").split())
            if "date" in col_lower and not col_tokens.intersection(date_part_words):
                score += 3.0
            if "timestamp" in col_lower:
                score += 2.0
            if "time" in col_lower:
                score += 1.0

            scored.append((col, score))

        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[0][0] if scored else None

    # --------------------------
    # Helpers
    # --------------------------

    def _safe_label(self, value):
        if pd.isna(value):
            return "Unknown"
        text = str(value).strip()
        return text if text else "Unknown"

    def _is_placeholder_label(self, label):
        s = str(label or "").strip().lower()
        return s in {"unknown", "n/a", "na", "null", "none", "error", "not available", ""}

    def _placeholder_ratio(self, series):
        try:
            if len(series) == 0:
                return 0.0

            labels = series.astype(str).str.strip().str.lower()
            placeholders = {
                "", "unknown", "n/a", "na", "null", "none",
                "error", "not available", "other", "misc"
            }
            return float(labels.isin(placeholders).mean())
        except Exception:
            return 0.0

    def _looks_like_identifier(self, col_name):
        col = str(col_name or "").strip().lower()
        id_terms = {
            "id", "uuid", "key", "code", "row id", "rowid",
            "transaction id", "order id", "customer id", "product id"
        }
        return any(term in col for term in id_terms)