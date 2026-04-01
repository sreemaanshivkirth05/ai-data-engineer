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
        top_bottom_segments = analysis.get("top_bottom_segments", {}) or {}
        categorical_drivers = analysis.get("categorical_drivers", {}) or {}
        time_summary = analysis.get("time_summary", {}) or {}
        direct_answer = business_layer.get("direct_answer")
        target_label = self._label(target).lower()

        # Prefer direct_answer from business_layer (already uses best_headline_segment)
        if direct_answer:
            return direct_answer

        if time_summary and time_summary.get("trend_direction") not in {None, "unknown"}:
            direction = time_summary.get("trend_direction")
            return (
                f"This analysis is centered on {target_label}. "
                f"The clearest visible pattern is a {direction} trend over time."
            )

        # FIX: use best_headline_segment instead of flat top_segments sort
        # to prevent dimension-segment label mismatch
        best_segment = self._best_headline_segment(top_bottom_segments, categorical_drivers)
        if best_segment:
            return (
                f"This analysis is centered on {target_label}. "
                f"The clearest visible leader is {best_segment['segment']} within {self._label(best_segment['dimension']).lower()}."
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
        top_bottom_segments = analysis.get("top_bottom_segments", {}) or {}
        correlations = analysis.get("correlations", {}) or {}
        categorical_drivers = analysis.get("categorical_drivers", {}) or {}
        distribution_summary = analysis.get("distribution_summary", {}) or {}
        time_summary = analysis.get("time_summary", {}) or {}
        outlier_summary = analysis.get("outlier_summary", {}) or {}
        concentration_summary = analysis.get("concentration_summary", {}) or {}
        performance_diagnostics = analysis.get("performance_diagnostics", {}) or {}
        risks = business_layer.get("risks_or_limitations", []) or []
        business_impact = business_layer.get("business_impact", []) or []

        # Paragraph 1: framing
        paragraphs.append(
            f"This analysis focuses on {target_label} because it is the primary metric most relevant to the question."
        )

        # Paragraph 2: direct answer / strongest visible segment
        # FIX: use best_headline_segment for consistent dimension-segment pairing
        best_segment = self._best_headline_segment(top_bottom_segments, categorical_drivers)
        if not best_segment:
            best_segment = self._best_non_placeholder_segment(top_segments)

        if best_segment:
            share_text = ""
            if best_segment.get("share_pct") is not None:
                share_text = f", contributing about {best_segment['share_pct']:.2f}% of the total"
            paragraphs.append(
                f"The clearest answer is that {best_segment['segment']} is the leading "
                f"{self._label(best_segment['dimension']).lower()} for {target_label}{share_text}. "
                f"This makes it a useful benchmark when comparing weaker groups."
            )

        # Paragraph 3: overall scale
        if kpis.get("total_target") is not None and kpis.get("average_target") is not None:
            paragraphs.append(
                f"At the overall level, total {target_label} is {self._format_value(kpis.get('total_target'), target)}, "
                f"while the average per usable record is {self._format_value(kpis.get('average_target'), target)}. "
                f"This gives a useful sense of scale before looking at deeper variation."
            )

        # Paragraph 4: time interpretation
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

        # Paragraph 5: strongest grouping dimensions
        strong_group_dims = self._top_meaningful_group_dims(categorical_drivers)
        if strong_group_dims:
            paragraphs.append(
                f"The most meaningful group-level differences appear across {', '.join(strong_group_dims[:2])}. "
                f"This suggests that performance is not evenly distributed and that segment-level decisions are more useful than one-size-fits-all actions."
            )

        # Paragraph 6: numeric signals
        strong_numeric_signals = self._top_meaningful_numeric_signals(correlations)
        if strong_numeric_signals:
            formatted_signals = ", ".join(
                [f"{name} ({direction}, correlation {corr})" for name, direction, corr in strong_numeric_signals[:2]]
            )
            paragraphs.append(
                f"The strongest measurable numeric signals are {formatted_signals}. "
                f"These should be treated as directional relationships rather than proof of causation."
            )

        # Paragraph 7: distribution and outliers
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

        # Paragraph 8: concentration / business implication
        best_concentration = self._best_concentration_summary(concentration_summary)
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

        # Paragraph 9: performance diagnostics
        diag_text = self._build_diagnostics_paragraph(performance_diagnostics)
        if diag_text:
            paragraphs.append(diag_text)

        # Paragraph 10: business impact
        if business_impact:
            cleaned_impact = [self._clean_sentence(x) for x in business_impact if x]
            if cleaned_impact:
                paragraphs.append(
                    "Performance is not evenly distributed: " + " ".join(cleaned_impact[:2])
                )

        # Paragraph 11: risks / caveats
        if risks:
            cleaned_risks = [self._clean_sentence(x) for x in risks if x]
            if cleaned_risks:
                paragraphs.append(
                    "A further caution is that " + " ".join(cleaned_risks[:2]).lower()
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

    def _best_concentration_summary(self, concentration_summary):
        if not concentration_summary:
            return None

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

    def _build_diagnostics_paragraph(self, performance_diagnostics):
        if not performance_diagnostics:
            return None

        for dim, info in performance_diagnostics.items():
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