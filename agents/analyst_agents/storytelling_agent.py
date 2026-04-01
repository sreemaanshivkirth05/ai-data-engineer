class StorytellingAgent:
    def run(self, question, target, kpis, analysis, business_layer=None):
        kpis = kpis or {}
        analysis = analysis or {}
        business_layer = business_layer or {}

        title = "Data Story"
        headline = self._build_headline(target, kpis, analysis, business_layer)

        key_points = self._build_key_points(target, kpis, analysis, business_layer)
        business_view = self._build_business_view(question, target, kpis, analysis, business_layer)

        return {
            "title": title,
            "headline": headline,
            "key_points": key_points[:7],
            "business_view": business_view[:7]
        }

    # --------------------------
    # Headline
    # --------------------------

    def _build_headline(self, target, kpis, analysis, business_layer):
        # Prefer the pre-computed direct_answer from business_layer
        # (already uses best_headline_segment for correct dimension-segment pairing)
        direct_answer = business_layer.get("direct_answer")
        if direct_answer:
            return direct_answer

        target_label = self._label(target).lower()
        top_bottom_segments = analysis.get("top_bottom_segments", {}) or {}
        categorical_drivers = analysis.get("categorical_drivers", {}) or {}
        top_segments = analysis.get("top_segments", []) or []
        time_summary = analysis.get("time_summary", {}) or {}

        # FIX: use best_headline_segment for consistent dimension-segment pairing
        best_segment = self._best_headline_segment(top_bottom_segments, categorical_drivers)
        if not best_segment:
            best_segment = self._best_non_placeholder_segment(top_segments)

        if best_segment:
            return (
                f"The clearest answer is that {best_segment['segment']} is currently the leading "
                f"{self._label(best_segment['dimension']).lower()} for {target_label}, "
                f"with a measured contribution of {self._format_value(best_segment.get('total_target'), target)}."
            )

        if time_summary and time_summary.get("trend_direction") not in {None, "unknown"}:
            return (
                f"The clearest pattern is that {target_label} shows a "
                f"{time_summary.get('trend_direction')} trend over time."
            )

        return f"This story summarizes the most important patterns in {target_label}."

    # --------------------------
    # Key points
    # --------------------------

    def _build_key_points(self, target, kpis, analysis, business_layer):
        points = []
        target_label = self._label(target).lower()

        if kpis.get("total_target") is not None:
            points.append(
                f"Total {target_label}: {self._format_value(kpis.get('total_target'), target)}"
            )

        if kpis.get("average_target") is not None:
            points.append(
                f"Average {target_label}: {self._format_value(kpis.get('average_target'), target)}"
            )

        if kpis.get("median_target") is not None:
            points.append(
                f"Median {target_label}: {self._format_value(kpis.get('median_target'), target)}"
            )

        # FIX: use best_headline_segment to get correct leading dimension+segment
        top_bottom_segments = analysis.get("top_bottom_segments", {}) or {}
        categorical_drivers = analysis.get("categorical_drivers", {}) or {}
        best_seg = self._best_headline_segment(top_bottom_segments, categorical_drivers)
        if best_seg:
            points.append(
                f"Leading {self._label(best_seg['dimension']).lower()}: {best_seg['segment']}"
            )
        elif kpis.get("top_dimension_name") and kpis.get("top_dimension_value"):
            if not self._is_placeholder_label(kpis.get("top_dimension_value")):
                points.append(
                    f"Leading {str(kpis['top_dimension_name']).lower()}: {kpis['top_dimension_value']}"
                )

        time_summary = analysis.get("time_summary", {}) or {}
        if time_summary.get("trend_direction") and time_summary.get("trend_direction") != "unknown":
            trend_text = f"Trend direction: {time_summary['trend_direction']}"
            if time_summary.get("change_pct") is not None:
                trend_text += f" ({abs(float(time_summary['change_pct'])):.2f}% overall change)"
            points.append(trend_text)

        top_group_dim = self._best_group_dimension(analysis.get("categorical_drivers", {}) or {})
        if top_group_dim:
            points.append(f"Most meaningful group variation: {top_group_dim}")

        strong_signal = self._best_numeric_signal(analysis.get("correlations", {}) or {})
        if strong_signal:
            name, corr = strong_signal
            direction = "positive" if corr > 0 else "negative"
            points.append(
                f"Strongest numeric signal: {name} ({direction}, correlation: {round(float(corr), 3)})"
            )

        outliers = analysis.get("outlier_summary", {}) or {}
        if outliers.get("outlier_count") not in {None, 0}:
            points.append(f"Detected outliers: {int(outliers['outlier_count'])}")

        return points

    # --------------------------
    # Business view
    # --------------------------

    def _build_business_view(self, question, target, kpis, analysis, business_layer):
        paragraphs = []

        target_label = self._label(target).lower()
        top_segments = analysis.get("top_segments", []) or []
        top_bottom_segments = analysis.get("top_bottom_segments", {}) or {}
        categorical_drivers = analysis.get("categorical_drivers", {}) or {}
        time_summary = analysis.get("time_summary", {}) or {}
        distribution_summary = analysis.get("distribution_summary", {}) or {}
        outlier_summary = analysis.get("outlier_summary", {}) or {}
        business_impact = business_layer.get("business_impact", []) or []
        risks = business_layer.get("risks_or_limitations", []) or []

        paragraphs.append(
            f"Your question asks for a business interpretation of {target_label} in the context of the broader dataset. "
            f"To answer that, the system looks at overall scale, segment variation, time patterns where available, and reliability checks."
        )

        # FIX: use best_headline_segment for consistent labelling
        best_segment = self._best_headline_segment(top_bottom_segments, categorical_drivers)
        if not best_segment:
            best_segment = self._best_non_placeholder_segment(top_segments)

        if best_segment:
            share_text = ""
            if best_segment.get("share_pct") is not None:
                share_text = f" It contributes about {best_segment['share_pct']:.2f}% of the total."
            paragraphs.append(
                f"The clearest result is that {best_segment['segment']} is the leading "
                f"{self._label(best_segment['dimension']).lower()}. "
                f"This makes it a useful benchmark when comparing the rest of the groups.{share_text}"
            )

        if time_summary and time_summary.get("trend_direction") not in {None, "unknown"}:
            sentence = (
                f"Over time, {target_label} appears {time_summary['trend_direction']}."
            )
            if time_summary.get("volatility_level") and time_summary.get("volatility_level") != "unknown":
                sentence += f" The pattern also shows {time_summary['volatility_level']} volatility."
            if time_summary.get("best_period"):
                sentence += f" The strongest period was {time_summary['best_period']}."
            paragraphs.append(sentence)

        strong_group_dim = self._best_group_dimension(analysis.get("categorical_drivers", {}) or {})
        if strong_group_dim:
            paragraphs.append(
                f"There is also meaningful variation across {strong_group_dim.lower()}, which suggests that performance is not uniform across the dataset and should be interpreted at the segment level."
            )

        strong_signal = self._best_numeric_signal(analysis.get("correlations", {}) or {})
        if strong_signal:
            name, corr = strong_signal
            direction = "moves with" if corr > 0 else "moves opposite to"
            paragraphs.append(
                f"Among the measurable numeric fields, {name} is the strongest non-trivial signal and {direction} the target. "
                f"This is useful for directional investigation, but it should not be treated as proof of causation."
            )

        if distribution_summary:
            mean_val = distribution_summary.get("mean")
            median_val = distribution_summary.get("median")
            skew_direction = distribution_summary.get("skew_direction")

            distribution_text = (
                f"The metric's distribution also matters: the mean is {self._format_value(mean_val, target)} "
                f"and the median is {self._format_value(median_val, target)}."
            )

            if skew_direction and skew_direction != "balanced":
                distribution_text += f" This suggests the distribution is {skew_direction.replace('_', ' ')}."
            paragraphs.append(distribution_text)

        if outlier_summary.get("outlier_count") not in {None, 0}:
            paragraphs.append(
                f"A further caution is that {int(outlier_summary['outlier_count'])} outliers were detected, "
                f"so unusually high or low records may be influencing averages or totals."
            )

        cleaned_impact = [self._clean_sentence(x) for x in business_impact if x]
        if cleaned_impact:
            paragraphs.append(" ".join(cleaned_impact[:2]))

        cleaned_risks = [self._clean_sentence(x) for x in risks if x]
        if cleaned_risks:
            paragraphs.append(
                "A final caution is that this output is best used for decision support and prioritization, "
                "with these limitations kept in mind: " + " ".join(cleaned_risks[:2])
            )

        return paragraphs

    # --------------------------
    # Helpers
    # --------------------------


    def _best_headline_segment(self, top_bottom_segments, categorical_drivers):
        """
        Pick the top segment from the most discriminating dimension.
        Two-pass: pass 1 skips dominant dims (top segment >80% share),
        pass 2 falls back to highest-variance dim if nothing passes.
        """
        if not top_bottom_segments or not categorical_drivers:
            return None

        ranked_dims = sorted(
            categorical_drivers.items(),
            key=lambda x: x[1],
            reverse=True
        )

        def _get(dim_name):
            if any(bad in dim_name.lower() for bad in ["id", "postal", "zip", "row"]):
                return None
            dim_data = top_bottom_segments.get(dim_name)
            if not dim_data:
                return None
            top_seg = dim_data.get("top")
            if not top_seg:
                return None
            seg_label = str(top_seg.get("segment", "")).strip().lower()
            if seg_label in {"unknown", "error", "n/a", "na", "none", "null", ""}:
                return None
            return top_seg

        # Pass 1: skip dominant dims (top seg > 80% share or < 1%)
        for dim_name, _ in ranked_dims:
            top_seg = _get(dim_name)
            if top_seg is None:
                continue
            share = top_seg.get("share_pct")
            if share is not None and (share > 80 or share < 1):
                continue
            return top_seg

        # Pass 2: fallback to any valid segment
        for dim_name, _ in ranked_dims:
            top_seg = _get(dim_name)
            if top_seg is not None:
                return top_seg

        return None

        ranked_dims = sorted(
            categorical_drivers.items(),
            key=lambda x: x[1],
            reverse=True
        )

        for dim_name, _ in ranked_dims:
            if any(bad in dim_name.lower() for bad in ["id", "postal", "zip", "row"]):
                continue

            dim_data = top_bottom_segments.get(dim_name)
            if not dim_data:
                continue

            top_seg = dim_data.get("top")
            if not top_seg:
                continue

            seg_label = str(top_seg.get("segment", "")).strip().lower()
            if seg_label in {"unknown", "error", "n/a", "na", "none", "null", ""}:
                continue

            return top_seg

        return None

    def _best_non_placeholder_segment(self, segments):
        """Legacy fallback — used when top_bottom_segments is not populated."""
        if not segments:
            return None

        valid = []
        for seg in segments:
            label = str(seg.get("segment", "")).strip().lower()
            if label in {"unknown", "error", "n/a", "na", "none", "null", ""}:
                continue
            valid.append(seg)

        if not valid:
            return None

        return sorted(
            valid,
            key=lambda x: (
                x.get("share_pct") if x.get("share_pct") is not None else x.get("total_target", 0),
                x.get("total_target", 0)
            ),
            reverse=True
        )[0]

    def _best_group_dimension(self, categorical_drivers):
        if not categorical_drivers:
            return None

        ranked = sorted(categorical_drivers.items(), key=lambda x: x[1], reverse=True)
        for name, _score in ranked:
            lower = str(name).lower()
            if any(bad in lower for bad in ["id", "postal", "zip", "row"]):
                continue
            return self._label(name)

        return None

    def _best_numeric_signal(self, correlations):
        if not correlations:
            return None

        ranked = sorted(correlations.items(), key=lambda x: abs(x[1]), reverse=True)
        for name, corr in ranked:
            lower = str(name).lower()
            if any(bad in lower for bad in ["id", "postal", "zip", "row"]):
                continue
            if abs(float(corr)) < 0.05:
                continue
            return self._label(name), corr

        return None

    def _is_placeholder_label(self, value):
        value = str(value).strip().lower()
        return value in {"unknown", "error", "n/a", "na", "none", "null", ""}

    def _format_value(self, value, label=""):
        if value is None:
            return "N/A"

        try:
            num = float(value)
        except Exception:
            return str(value)

        label_lower = str(label or "").lower()
        is_money = any(word in label_lower for word in [
            "sales", "revenue", "profit", "cost", "amount", "price"
        ])

        if is_money:
            if abs(num) >= 1_000_000_000:
                return f"${num / 1_000_000_000:.2f}B"
            if abs(num) >= 1_000_000:
                return f"${num / 1_000_000:.2f}M"
            if abs(num) >= 1_000:
                return f"${num / 1_000:.2f}K"
            return f"${num:,.2f}"

        if abs(num) >= 1_000_000_000:
            return f"{num / 1_000_000_000:.2f}B"
        if abs(num) >= 1_000_000:
            return f"{num / 1_000_000:.2f}M"
        if abs(num) >= 1_000:
            return f"{num / 1_000:.2f}K"
        if num == int(num):
            return f"{int(num):,}"
        return f"{num:,.2f}"

    def _clean_sentence(self, text):
        text = str(text or "").strip()
        if not text:
            return ""
        if text[-1] not in ".!?":
            text += "."
        return text

    def _label(self, value):
        return str(value).replace("_", " ").strip()