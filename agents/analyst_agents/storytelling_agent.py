class StorytellingAgent:
    def run(self, question, target, kpis, analysis, business_layer=None, is_overview=False):
        kpis = kpis or {}
        analysis = analysis or {}
        business_layer = business_layer or {}

        title = "Data Story"
        headline = self._build_headline(question, target, kpis, analysis, business_layer, is_overview)
        key_points = self._build_key_points(question, target, kpis, analysis, business_layer, is_overview)
        business_view = self._build_business_view(question, target, kpis, analysis, business_layer, is_overview)

        return {
            "title": title,
            "headline": headline,
            "key_points": key_points[:7],
            "business_view": business_view[:7]
        }

    # --------------------------
    # Headline
    # --------------------------

    def _build_headline(self, question, target, kpis, analysis, business_layer, is_overview=False):
        direct_answer = business_layer.get("direct_answer")
        if direct_answer:
            return direct_answer

        target_label = self._label(target).lower()
        top_segments = analysis.get("top_segments", []) or []
        time_summary = analysis.get("time_summary", {}) or {}
        ranking_direction = self._infer_ranking_direction(question, target)

        if is_overview and target:
            seen_dims = {}
            for seg in top_segments:
                dim = seg.get("dimension", "")
                segment_val = seg.get("segment", "")
                if dim and not self._is_bad_dimension(dim) and dim not in seen_dims:
                    seen_dims[dim] = segment_val
                if len(seen_dims) >= 3:
                    break

            if seen_dims:
                dim_parts = ", ".join(
                    f"{self._label(dim).lower()} (led by {seg})"
                    for dim, seg in seen_dims.items()
                )
                return (
                    f"{self._label(target)} is the primary business metric. "
                    f"The strongest visible variation appears across {dim_parts}."
                )

        focus_dim = self._infer_focus_dimension(question, top_segments)
        best_segment = self._best_segment_for_dimension(
            top_segments,
            preferred_dimension=focus_dim,
            ranking_direction=ranking_direction
        )
        if best_segment:
            lead_word = "lowest" if ranking_direction == "ascending" else "leading"
            return (
                f"The clearest answer is that {best_segment['segment']} is currently the {lead_word} "
                f"{self._label(best_segment['dimension']).lower()} for {target_label}."
            )

        if time_summary and time_summary.get("trend_direction") not in {None, "unknown"}:
            return (
                f"The clearest pattern is that {target_label} shows a "
                f"{time_summary.get('trend_direction')} trend over time."
            )

        return f"This story summarises the most important patterns in {target_label}."

    # --------------------------
    # Key points
    # --------------------------

    def _build_key_points(self, question, target, kpis, analysis, business_layer, is_overview=False):
        points = []
        target_label = self._label(target).lower()
        ranking_direction = self._infer_ranking_direction(question, target)

        if kpis.get("total_target") is not None:
            points.append(f"Total {target_label}: {self._format_value(kpis.get('total_target'), target)}")

        if kpis.get("average_target") is not None:
            points.append(f"Average {target_label}: {self._format_value(kpis.get('average_target'), target)}")

        if kpis.get("median_target") is not None:
            points.append(f"Median {target_label}: {self._format_value(kpis.get('median_target'), target)}")

        top_segments = analysis.get("top_segments", []) or []
        time_summary = analysis.get("time_summary", {}) or {}

        if is_overview:
            seen_dims = {}
            for seg in top_segments:
                dim = seg.get("dimension", "")
                segment_val = seg.get("segment", "")
                if dim and not self._is_bad_dimension(dim) and dim not in seen_dims:
                    seen_dims[dim] = segment_val
                if len(seen_dims) >= 3:
                    break
            for dim, seg_val in seen_dims.items():
                points.append(f"Leading {self._label(dim).lower()}: {seg_val}")
        else:
            focus_dim = self._infer_focus_dimension(question, top_segments)
            focused = self._best_segment_for_dimension(
                top_segments,
                preferred_dimension=focus_dim,
                ranking_direction=ranking_direction
            )
            if focused and not self._is_placeholder_label(focused.get("segment")):
                label_word = "Lowest" if ranking_direction == "ascending" else "Leading"
                points.append(
                    f"{label_word} {self._label(focused.get('dimension')).lower()}: {focused.get('segment')}"
                )
            elif kpis.get("top_dimension_name") and kpis.get("top_dimension_value"):
                if not self._is_placeholder_label(kpis.get("top_dimension_value")):
                    label_word = "Lowest" if ranking_direction == "ascending" else "Leading"
                    points.append(f"{label_word} {str(kpis['top_dimension_name']).lower()}: {kpis['top_dimension_value']}")

        if time_summary.get("trend_direction") and time_summary.get("trend_direction") != "unknown":
            trend_text = f"Trend direction: {time_summary['trend_direction']}"
            if time_summary.get("change_pct") is not None:
                trend_text += f" ({abs(float(time_summary['change_pct'])):.2f}% overall change)"
            points.append(trend_text)

        top_group_dim = self._best_group_dimension(
            analysis.get("categorical_drivers", {}) or {},
            preferred_dimension=self._infer_focus_dimension(question, top_segments)
        )
        if top_group_dim:
            points.append(f"Most meaningful group variation: {self._label(top_group_dim)}")

        outlier_summary = analysis.get("outlier_summary", {}) or {}
        if outlier_summary.get("outlier_count") is not None:
            outlier_count = int(outlier_summary.get("outlier_count", 0))
            if outlier_count > 0:
                points.append(f"Detected outliers: {outlier_count}")

        return points

    # --------------------------
    # Business view
    # --------------------------

    def _build_business_view(self, question, target, kpis, analysis, business_layer, is_overview=False):
        view = []

        target_label = self._label(target).lower()
        direct_answer = business_layer.get("direct_answer")
        top_segments = analysis.get("top_segments", []) or []
        time_summary = analysis.get("time_summary", {}) or {}
        distribution_summary = analysis.get("distribution_summary", {}) or {}
        outlier_summary = analysis.get("outlier_summary", {}) or {}
        business_impact = business_layer.get("business_impact", []) or []
        risks = business_layer.get("risks_or_limitations", []) or []
        ranking_direction = self._infer_ranking_direction(question, target)

        view.append(
            f"Your question asks for a business interpretation of {target_label} in the context of the broader dataset. "
            f"To answer that, the system looks at overall scale, segment variation, time patterns where available, and reliability checks."
        )

        focus_dim = self._infer_focus_dimension(question, top_segments)
        best_segment = self._best_segment_for_dimension(
            top_segments,
            preferred_dimension=focus_dim,
            ranking_direction=ranking_direction
        )
        if best_segment:
            share_text = ""
            if best_segment.get("share_pct") is not None:
                share_text = f" It contributes about {best_segment['share_pct']:.2f}% of the total."
            descriptor = "lowest" if ranking_direction == "ascending" else "leading"
            comparison_text = (
                "This highlights the weakest-performing group that may need attention."
                if ranking_direction == "ascending"
                else "This makes it a useful benchmark when comparing the rest of the groups."
            )
            view.append(
                f"The clearest result is that {best_segment['segment']} is the {descriptor} "
                f"{self._label(best_segment['dimension']).lower()}. "
                f"{comparison_text}{share_text}"
            )
        elif direct_answer:
            view.append(direct_answer)

        if time_summary and time_summary.get("trend_direction") not in {None, "unknown"}:
            sentence = f"Over time, {target_label} appears {time_summary['trend_direction']}."
            if time_summary.get("volatility_level") and time_summary.get("volatility_level") != "unknown":
                sentence += f" The pattern also shows {time_summary['volatility_level']} volatility."
            if time_summary.get("best_period"):
                sentence += f" The strongest period was {time_summary['best_period']}."
            view.append(sentence)

        top_group_dim = self._best_group_dimension(
            analysis.get("categorical_drivers", {}) or {},
            preferred_dimension=focus_dim
        )
        if top_group_dim:
            view.append(
                f"There is meaningful variation across {self._label(top_group_dim).lower()}, "
                f"which suggests that performance is not uniform across the dataset and should be interpreted at the segment level."
            )

        if distribution_summary:
            mean_val = distribution_summary.get("mean")
            median_val = distribution_summary.get("median")
            skew_direction = distribution_summary.get("skew_direction")
            sentence = (
                f"The metric's distribution also matters: the mean is {self._format_value(mean_val, target)} "
                f"and the median is {self._format_value(median_val, target)}."
            )
            if skew_direction and skew_direction != "balanced":
                sentence += f" This suggests the distribution is {skew_direction.replace('_', ' ')}."
            view.append(sentence)

        if outlier_summary.get("outlier_count") is not None:
            outlier_count = int(outlier_summary.get("outlier_count", 0))
            if outlier_count > 0:
                view.append(
                    f"A further caution is that {outlier_count} outliers were detected, so unusually high or low records may be influencing averages or totals."
                )

        if business_impact:
            for item in business_impact[:2]:
                cleaned = self._clean_sentence(item)
                if cleaned:
                    view.append(cleaned)

        if risks:
            for item in risks[:2]:
                cleaned = self._clean_sentence(item)
                if cleaned:
                    view.append(f"Caveat: {cleaned}")

        if not view:
            view.append(
                f"This story summarises the strongest visible business patterns in {target_label}, "
                f"including scale, segment performance, and risks in interpretation."
            )

        return view

    # --------------------------
    # Focus helpers
    # --------------------------

    def _infer_focus_dimension(self, question, top_segments):
        q = str(question or "").lower().strip()

        if any(word in q for word in ["sub-category", "sub category", "subcategory", "subcategories"]):
            for seg in top_segments:
                dim = str(seg.get("dimension", "")).lower()
                if "sub-category" in dim or "sub category" in dim:
                    return seg.get("dimension")

        if any(word in q for word in ["product", "products", "item", "items", "chocolate", "chocolates"]):
            for seg in top_segments:
                dim = str(seg.get("dimension", "")).lower()
                if "product" in dim or "item" in dim:
                    return seg.get("dimension")

        if any(word in q for word in ["country", "countries", "market", "markets", "region", "regions"]):
            for seg in top_segments:
                dim = str(seg.get("dimension", "")).lower()
                if "country" in dim or "region" in dim or "market" in dim:
                    return seg.get("dimension")

        if any(word in q for word in ["sales person", "salesperson", "seller", "rep", "representative"]):
            for seg in top_segments:
                dim = str(seg.get("dimension", "")).lower()
                if "sales person" in dim or "salesperson" in dim:
                    return seg.get("dimension")

        if any(word in q for word in ["category", "categories"]):
            for seg in top_segments:
                dim = str(seg.get("dimension", "")).lower()
                if "category" in dim and "sub-category" not in dim and "sub category" not in dim:
                    return seg.get("dimension")

        if any(word in q for word in ["segment", "segments", "group", "groups"]):
            for seg in top_segments:
                dim = str(seg.get("dimension", "")).lower()
                if "segment" in dim or "group" in dim:
                    return seg.get("dimension")

        return None

    def _best_segment_for_dimension(self, segments, preferred_dimension=None, ranking_direction="descending"):
        if not segments:
            return None

        valid = [
            seg for seg in segments
            if str(seg.get("segment", "")).strip().lower() not in {"unknown", "error", "n/a", "na", "none", "null", ""}
        ]
        if not valid:
            return None

        candidates = valid
        if preferred_dimension:
            focused = [
                seg for seg in valid
                if str(seg.get("dimension", "")).strip().lower() == str(preferred_dimension).strip().lower()
            ]
            if focused:
                candidates = focused

        reverse = ranking_direction != "ascending"
        return sorted(
            candidates,
            key=lambda x: (
                x.get("share_pct") if x.get("share_pct") is not None else x.get("total_target", 0),
                x.get("total_target", 0)
            ),
            reverse=reverse
        )[0]

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
    # Existing helpers
    # --------------------------

    def _best_non_placeholder_segment(self, segments):
        if not segments:
            return None

        valid = [
            seg for seg in segments
            if str(seg.get("segment", "")).strip().lower() not in {"unknown", "error", "n/a", "na", "none", "null", ""}
        ]
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

    def _best_group_dimension(self, categorical_drivers, preferred_dimension=None):
        if preferred_dimension and preferred_dimension in categorical_drivers:
            return preferred_dimension

        if not categorical_drivers:
            return None

        filtered = {
            k: v for k, v in categorical_drivers.items()
            if not self._is_bad_dimension(k)
        }
        if not filtered:
            return None

        return sorted(filtered.items(), key=lambda x: x[1], reverse=True)[0][0]

    def _is_bad_dimension(self, dim):
        d = str(dim or "").lower()
        return any(token in d for token in ["id", "postal", "zip", "row"])

    def _is_placeholder_label(self, label):
        s = str(label or "").strip().lower()
        return s in {"unknown", "n/a", "na", "null", "none", "error", "not available", ""}

    def _format_value(self, value, label=""):
        if value is None:
            return "N/A"

        try:
            num = float(value)
        except Exception:
            return str(value)

        label_lower = str(label or "").lower()
        is_money = any(word in label_lower for word in ["sales", "revenue", "profit", "cost", "amount", "price"])

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
        if num.is_integer():
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