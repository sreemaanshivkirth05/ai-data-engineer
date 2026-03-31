import pandas as pd


class NarrativeAgent:
    def run(self, question, analysis, kpis, target, business_layer=None):
        analysis = analysis or {}
        kpis = kpis or {}
        business_layer = business_layer or {}

        title = "Analyst Narrative"
        summary = self._build_summary(
            question=question,
            analysis=analysis,
            kpis=kpis,
            target=target,
            business_layer=business_layer
        )

        paragraphs = []
        paragraphs.extend(self._build_core_paragraphs(question, analysis, kpis, target, business_layer))
        paragraphs = [p for p in paragraphs if p and str(p).strip()]

        return {
            "title": title,
            "summary": summary,
            "paragraphs": paragraphs[:8]
        }

    # --------------------------
    # Summary
    # --------------------------

    def _build_summary(self, question, analysis, kpis, target, business_layer):
        top_segments = analysis.get("top_segments", []) or []
        time_summary = analysis.get("time_summary", {}) or {}
        direct_answer = business_layer.get("direct_answer")
        target_label = self._label(target).lower()
        ranking_direction = self._infer_ranking_direction(question, target)

        if direct_answer:
            return direct_answer

        focus_dim = self._infer_focus_dimension(question, top_segments)

        if time_summary and time_summary.get("trend_direction") not in {None, "unknown"}:
            direction = time_summary.get("trend_direction")
            return (
                f"This analysis is centered on {target_label}. "
                f"The clearest visible pattern is a {direction} trend over time."
            )

        best_segment = self._best_segment_for_dimension(
            top_segments,
            preferred_dimension=focus_dim,
            ranking_direction=ranking_direction
        )
        if best_segment:
            descriptor = "lowest" if ranking_direction == "ascending" else "leading"
            return (
                f"This analysis is centered on {target_label}. "
                f"The clearest visible {descriptor} group is {best_segment['segment']} within {self._label(best_segment['dimension']).lower()}."
            )

        return (
            f"This analysis is centered on {target_label}. "
            f"It summarizes the strongest visible patterns, segment differences, and risks in the dataset."
        )

    # --------------------------
    # Paragraph builders
    # --------------------------

    def _build_core_paragraphs(self, question, analysis, kpis, target, business_layer):
        paragraphs = []

        target_label = self._label(target).lower()
        top_segments = analysis.get("top_segments", []) or []
        correlations = analysis.get("correlations", {}) or {}
        categorical_drivers = analysis.get("categorical_drivers", {}) or {}
        distribution_summary = analysis.get("distribution_summary", {}) or {}
        time_summary = analysis.get("time_summary", {}) or {}
        outlier_summary = analysis.get("outlier_summary", {}) or {}
        concentration_summary = analysis.get("concentration_summary", {}) or {}
        performance_diagnostics = analysis.get("performance_diagnostics", {}) or {}
        risks = business_layer.get("risks_or_limitations", []) or []
        business_impact = business_layer.get("business_impact", []) or []
        ranking_direction = self._infer_ranking_direction(question, target)

        paragraphs.append(
            f"This analysis focuses on {target_label} because it is the primary metric most relevant to the question."
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
                share_text = f", contributing about {best_segment['share_pct']:.2f}% of the total"

            if ranking_direction == "ascending":
                paragraphs.append(
                    f"The clearest answer is that {best_segment['segment']} is the lowest "
                    f"{self._label(best_segment['dimension']).lower()} for {target_label}{share_text}. "
                    f"This highlights the weakest-performing group that may need closer attention."
                )
            else:
                paragraphs.append(
                    f"The clearest answer is that {best_segment['segment']} is the leading "
                    f"{self._label(best_segment['dimension']).lower()} for {target_label}{share_text}. "
                    f"This makes it a useful benchmark when comparing weaker groups."
                )

        if kpis.get("total_target") is not None and kpis.get("average_target") is not None:
            paragraphs.append(
                f"At the overall level, total {target_label} is {self._format_value(kpis.get('total_target'), target)}, "
                f"while the average per usable record is {self._format_value(kpis.get('average_target'), target)}. "
                f"This gives a useful sense of scale before looking at deeper variation."
            )

        if time_summary and time_summary.get("period_count"):
            direction = time_summary.get("trend_direction", "unknown")
            volatility = time_summary.get("volatility_level", "unknown")
            best_period = time_summary.get("best_period")
            worst_period = time_summary.get("worst_period")

            parts = [
                f"The time pattern shows {direction if direction != 'unknown' else 'a measurable'} movement in {target_label}"
            ]

            if time_summary.get("change_pct") is not None:
                parts.append(
                    f"with an overall change of {abs(float(time_summary['change_pct'])):.2f}%"
                )

            if volatility != "unknown":
                parts.append(f"and {volatility} volatility")

            sentence = " ".join(parts) + "."

            if best_period and worst_period:
                sentence += f" The strongest period was {best_period}, while the weakest period was {worst_period}."

            paragraphs.append(sentence)

        strong_group_dims = self._top_meaningful_group_dims(categorical_drivers)

        if focus_dim:
            focus_label = self._label(focus_dim)
            strong_group_dims = [focus_label] + [d for d in strong_group_dims if d != focus_label]

        if strong_group_dims:
            paragraphs.append(
                f"The most meaningful group-level differences appear across {', '.join(strong_group_dims[:2])}. "
                f"This suggests that performance is not evenly distributed and that segment-level decisions are more useful than one-size-fits-all actions."
            )

        strong_numeric_signals = self._top_meaningful_numeric_signals(correlations)
        if strong_numeric_signals:
            formatted_signals = ", ".join(
                [f"{name} ({direction}, correlation {corr})" for name, direction, corr in strong_numeric_signals[:2]]
            )
            paragraphs.append(
                f"The strongest measurable numeric signals are {formatted_signals}. "
                f"These should be treated as directional relationships rather than proof of causation."
            )

        if distribution_summary:
            mean_val = distribution_summary.get("mean")
            median_val = distribution_summary.get("median")
            std_val = distribution_summary.get("std")
            skew_direction = distribution_summary.get("skew_direction")

            distribution_text = (
                f"The distribution of {target_label} has a mean of {self._format_value(mean_val, target)} "
                f"and a median of {self._format_value(median_val, target)}"
            )
            if std_val is not None:
                distribution_text += f", with a standard deviation of {self._format_value(std_val, target)}"
            distribution_text += "."

            if skew_direction and skew_direction != "balanced":
                distribution_text += f" The distribution appears {skew_direction.replace('_', ' ')}."
            paragraphs.append(distribution_text)

        if outlier_summary and outlier_summary.get("outlier_count") is not None:
            outlier_count = int(outlier_summary.get("outlier_count", 0))
            outlier_pct = outlier_summary.get("outlier_pct")
            if outlier_count > 0:
                paragraphs.append(
                    f"There are {outlier_count} detected outliers, representing about "
                    f"{outlier_pct:.2f}% of usable records. This suggests that unusually high or low values may be influencing averages or totals."
                )

        best_concentration = self._best_concentration_summary(concentration_summary, preferred_dimension=focus_dim)
        if best_concentration:
            risk = best_concentration.get("concentration_risk", "unknown")
            top3 = best_concentration.get("top_3_share_pct")
            dim_name = best_concentration.get("dimension")
            top_segment = best_concentration.get("top_segment")

            text = (
                f"Concentration is also important here: within {self._label(dim_name).lower()}, "
                f"{top_segment} is a leading segment"
            )
            if top3 is not None:
                text += f", and the top 3 groups account for about {top3:.2f}% of total {target_label}"
            text += f". This points to a {risk} concentration risk profile."
            paragraphs.append(text)

        diag_text = self._build_diagnostics_paragraph(performance_diagnostics, preferred_dimension=focus_dim)
        if diag_text:
            paragraphs.append(diag_text)

        if business_impact:
            cleaned_impact = [self._clean_sentence(x) for x in business_impact if x]
            if cleaned_impact:
                paragraphs.append(
                    "From a business perspective, " + " ".join(cleaned_impact[:3])
                )

        if risks:
            cleaned_risks = [self._clean_sentence(x) for x in risks if x]
            if cleaned_risks:
                paragraphs.append(
                    "At the same time, the analysis should be read with a few caveats in mind: "
                    + " ".join(cleaned_risks[:3])
                )

        paragraphs.append(
            "Taken together, the results show not just what is happening in the dataset, "
            "but where performance is concentrated, which patterns are most important, and where further action or deeper analysis would be most useful."
        )

        return paragraphs

    # --------------------------
    # Helpers
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

        valid = []
        for seg in segments:
            label = str(seg.get("segment", "")).strip().lower()
            if label in {"unknown", "error", "n/a", "na", "none", "null", ""}:
                continue
            valid.append(seg)

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

    def _best_non_placeholder_segment(self, segments):
        if not segments:
            return None

        valid = []
        for seg in segments:
            label = str(seg.get("segment", "")).strip().lower()
            if label in {"unknown", "error", "n/a", "na", "none", "null", ""}:
                continue
            valid.append(seg)

        if valid:
            return sorted(
                valid,
                key=lambda x: (
                    x.get("share_pct") if x.get("share_pct") is not None else x.get("total_target", 0),
                    x.get("total_target", 0)
                ),
                reverse=True
            )[0]

        return None

    def _top_meaningful_group_dims(self, categorical_drivers):
        if not categorical_drivers:
            return []

        items = sorted(categorical_drivers.items(), key=lambda x: x[1], reverse=True)

        cleaned = []
        for name, _score in items:
            lower = str(name).lower()
            if any(bad in lower for bad in ["id", "postal", "zip", "row"]):
                continue
            cleaned.append(self._label(name))

        return cleaned[:3]

    def _top_meaningful_numeric_signals(self, correlations):
        if not correlations:
            return []

        ranked = sorted(correlations.items(), key=lambda x: abs(x[1]), reverse=True)
        cleaned = []

        for name, corr in ranked:
            lower = str(name).lower()
            if any(bad in lower for bad in ["id", "postal", "zip", "row"]):
                continue
            if abs(float(corr)) < 0.05:
                continue

            direction = "positive" if corr > 0 else "negative"
            cleaned.append((self._label(name), direction, round(float(corr), 3)))

        return cleaned[:3]

    def _best_concentration_summary(self, concentration_summary, preferred_dimension=None):
        if not concentration_summary:
            return None

        if preferred_dimension and preferred_dimension in concentration_summary:
            best_obj = dict(concentration_summary[preferred_dimension])
            best_obj["dimension"] = preferred_dimension
            return best_obj

        best_dim = None
        best_obj = None
        best_score = -1

        for dim, info in concentration_summary.items():
            score = info.get("top_3_share_pct")
            if score is None:
                score = info.get("top_segment_share_pct", -1)
            if score is not None and score > best_score:
                best_score = score
                best_dim = dim
                best_obj = dict(info)
                best_obj["dimension"] = dim

        return best_obj

    def _build_diagnostics_paragraph(self, performance_diagnostics, preferred_dimension=None):
        if not performance_diagnostics:
            return None

        dims_to_check = []
        if preferred_dimension and preferred_dimension in performance_diagnostics:
            dims_to_check.append((preferred_dimension, performance_diagnostics[preferred_dimension]))

        for dim, info in performance_diagnostics.items():
            if preferred_dimension and dim == preferred_dimension:
                continue
            dims_to_check.append((dim, info))

        for dim, info in dims_to_check:
            high_total_low_avg = info.get("high_total_low_avg_segments", []) or []
            high_avg_low_volume = info.get("high_avg_low_volume_segments", []) or []
            long_tail_count = info.get("long_tail_segment_count")

            parts = []

            if high_total_low_avg:
                parts.append(
                    f"Within {self._label(dim).lower()}, some groups such as {', '.join(high_total_low_avg[:2])} appear to have high total contribution but lower average performance"
                )

            if high_avg_low_volume:
                parts.append(
                    f"while groups such as {', '.join(high_avg_low_volume[:2])} appear strong on average but at lower volume"
                )

            if long_tail_count is not None and long_tail_count > 0:
                parts.append(
                    f"and the dimension also shows a long tail of {long_tail_count} smaller segments"
                )

            if parts:
                text = " ".join(parts).strip()
                if not text.endswith("."):
                    text += "."
                return text

        return None

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