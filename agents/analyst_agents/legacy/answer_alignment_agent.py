class AnswerAlignmentAgent:
    """
    Final answer repair agent.

    Purpose:
    - Make sure the final written answer is based on the user's actual question.
    - Prevent drift where charts/KPIs are correct but text answers the wrong thing.
    - Repair only the user-facing answer layer:
        - direct_answer
        - executive_summary
        - narrative.summary
        - story.headline
    """

    def run(
        self,
        question,
        intent,
        target,
        plan=None,
        kpis=None,
        analysis=None,
        charts=None,
        business_layer=None,
        narrative=None,
        story=None,
        review=None,
    ):
        plan = plan or {}
        kpis = kpis or {}
        analysis = analysis or {}
        charts = charts or []
        business_layer = business_layer or {}
        narrative = narrative or {}
        story = story or {}
        review = review or {}

        question = str(question or "").strip()
        target = target or plan.get("target")
        ranking_direction = self._infer_ranking_direction(question, target)
        requested_dimension = self._infer_requested_dimension(
            question=question,
            plan=plan,
            analysis=analysis,
            kpis=kpis
        )
        requested_numeric_driver = self._infer_requested_numeric_driver(
            question=question,
            plan=plan,
            analysis=analysis
        )

        selected_segment = self._extract_selected_segment(
            question=question,
            analysis=analysis,
            kpis=kpis,
            requested_dimension=requested_dimension
        )

        repaired_direct_answer = self._repair_direct_answer(
            question=question,
            intent=intent,
            target=target,
            ranking_direction=ranking_direction,
            requested_dimension=requested_dimension,
            requested_numeric_driver=requested_numeric_driver,
            selected_segment=selected_segment,
            analysis=analysis,
            kpis=kpis,
        )

        repaired_executive_summary = self._repair_executive_summary(
            question=question,
            intent=intent,
            target=target,
            ranking_direction=ranking_direction,
            requested_dimension=requested_dimension,
            requested_numeric_driver=requested_numeric_driver,
            selected_segment=selected_segment,
            analysis=analysis,
            repaired_direct_answer=repaired_direct_answer,
        )

        repaired_narrative_summary = repaired_direct_answer
        repaired_story_headline = repaired_direct_answer

        result = {
            "passed": True,
            "repairs_applied": True,
            "requested_dimension": requested_dimension,
            "requested_numeric_driver": requested_numeric_driver,
            "ranking_direction": ranking_direction,
            "selected_segment": selected_segment,
            "direct_answer": repaired_direct_answer,
            "executive_summary": repaired_executive_summary,
            "narrative_summary": repaired_narrative_summary,
            "story_headline": repaired_story_headline,
            "repair_reasoning": self._build_repair_reasoning(
                question=question,
                intent=intent,
                requested_dimension=requested_dimension,
                requested_numeric_driver=requested_numeric_driver,
                ranking_direction=ranking_direction,
                selected_segment=selected_segment
            )
        }

        return result

    # =====================================================
    # Main repair methods
    # =====================================================

    def _repair_direct_answer(
        self,
        question,
        intent,
        target,
        ranking_direction,
        requested_dimension,
        requested_numeric_driver,
        selected_segment,
        analysis,
        kpis,
    ):
        target_label = self._label(target).lower()
        time_summary = analysis.get("time_summary", {}) or {}
        correlations = analysis.get("correlations", {}) or {}

        # --------------------------
        # Relationship questions
        # --------------------------
        if intent == "relationship_analysis":
            if requested_numeric_driver and requested_numeric_driver in correlations:
                corr = correlations.get(requested_numeric_driver)
                relation_text = self._correlation_phrase(corr)
                return (
                    f"{self._label(requested_numeric_driver)} is {relation_text} "
                    f"{target_label} (correlation: {self._format_corr(corr)})."
                )

            if requested_numeric_driver:
                return (
                    f"The primary relationship check is between {self._label(requested_numeric_driver).lower()} "
                    f"and {target_label}. The chart should be used as the main evidence, and the result should be "
                    f"interpreted as association rather than causation."
                )

            strongest = self._strongest_meaningful_correlation(correlations)
            if strongest:
                name, corr = strongest
                relation_text = self._correlation_phrase(corr)
                return (
                    f"The strongest numeric relationship is that {self._label(name).lower()} is "
                    f"{relation_text} {target_label} (correlation: {self._format_corr(corr)})."
                )

        # --------------------------
        # Trend questions
        # --------------------------
        if intent == "trend_analysis" and time_summary:
            first_period = time_summary.get("first_period")
            last_period = time_summary.get("last_period")
            first_value = time_summary.get("first_value")
            last_value = time_summary.get("last_value")
            change_pct = time_summary.get("change_pct")
            best_period = time_summary.get("best_period")
            best_period_value = time_summary.get("best_period_value")

            if first_period and last_period and first_value is not None and last_value is not None:
                change_text = ""
                if change_pct is not None and abs(change_pct) >= 3:
                    direction = "up" if change_pct >= 0 else "down"
                    change_text = f", moving {direction} {abs(change_pct):.1f}% overall"
                elif change_pct is not None:
                    change_text = ", remaining broadly stable across the period"

                best_period_text = ""
                if best_period and best_period_value is not None:
                    best_period_text = (
                        f" The strongest period was {best_period} at {self._format_value(best_period_value, target)}."
                    )

                if requested_dimension:
                    return (
                        f"{self._label(target)} changes over time across {self._label(requested_dimension).lower()} groups. "
                        f"Overall, it moved from {self._format_value(first_value, target)} in {first_period} "
                        f"to {self._format_value(last_value, target)} in {last_period}{change_text}.{best_period_text}"
                    )

                return (
                    f"{self._label(target)} moved from {self._format_value(first_value, target)} in {first_period} "
                    f"to {self._format_value(last_value, target)} in {last_period}{change_text}.{best_period_text}"
                )

        # --------------------------
        # Ranking / comparison questions
        # --------------------------
        if selected_segment and requested_dimension:
            if ranking_direction == "ascending":
                metric_value = self._segment_metric_for_dimension(
                    analysis=analysis,
                    requested_dimension=requested_dimension,
                    selected_segment=selected_segment
                )
                if metric_value is not None:
                    return (
                        f"The clearest answer is that {selected_segment} is the lowest "
                        f"{self._label(requested_dimension).lower()} for {target_label}, "
                        f"with a measured contribution of {self._format_value(metric_value, target)}."
                    )
                return (
                    f"The clearest answer is that {selected_segment} is the lowest "
                    f"{self._label(requested_dimension).lower()} for {target_label}."
                )

            metric_value = self._segment_metric_for_dimension(
                analysis=analysis,
                requested_dimension=requested_dimension,
                selected_segment=selected_segment
            )
            if metric_value is not None:
                return (
                    f"The clearest answer is that {selected_segment} is the leading "
                    f"{self._label(requested_dimension).lower()} for {target_label}, "
                    f"with a measured contribution of {self._format_value(metric_value, target)}."
                )
            return (
                f"The clearest answer is that {selected_segment} is the leading "
                f"{self._label(requested_dimension).lower()} for {target_label}."
            )

        # --------------------------
        # KPI fallback
        # --------------------------
        if kpis.get("top_dimension_name") and kpis.get("top_dimension_value"):
            dim_name = str(kpis.get("top_dimension_name"))
            dim_value = str(kpis.get("top_dimension_value"))
            metric = kpis.get("top_dimension_metric")

            if ranking_direction == "ascending":
                return (
                    f"The clearest answer is that {dim_value} is the lowest "
                    f"{dim_name.lower()} for {target_label}, with a measured contribution of "
                    f"{self._format_value(metric, target)}."
                )

            return (
                f"The clearest answer is that {dim_value} is the leading "
                f"{dim_name.lower()} for {target_label}, with a measured contribution of "
                f"{self._format_value(metric, target)}."
            )

        if target:
            return (
                f"The analysis is centred on {self._label(target).lower()}. "
                f"See the visuals below for the strongest evidence related to the question."
            )

        return "The analysis completed successfully. See the charts and narrative below."

    def _repair_executive_summary(
        self,
        question,
        intent,
        target,
        ranking_direction,
        requested_dimension,
        requested_numeric_driver,
        selected_segment,
        analysis,
        repaired_direct_answer,
    ):
        parts = []
        target_label = self._label(target).lower()
        time_summary = analysis.get("time_summary", {}) or {}
        correlations = analysis.get("correlations", {}) or {}

        if target:
            parts.append(f"This analysis is centered on {target_label} as the primary business metric.")

        if intent == "relationship_analysis":
            if requested_numeric_driver:
                parts.append(
                    f"The question specifically asks whether {self._label(requested_numeric_driver).lower()} is related to {target_label}, so the relationship answer is anchored to that field."
                )
                if requested_numeric_driver in correlations:
                    corr = correlations.get(requested_numeric_driver)
                    relation_text = self._correlation_phrase(corr)
                    parts.append(
                        f"{self._label(requested_numeric_driver)} is {relation_text} the target metric."
                    )
                else:
                    parts.append(
                        "The chart should be used as the primary evidence, and the result should be interpreted as association rather than causation."
                    )
            else:
                strongest = self._strongest_meaningful_correlation(correlations)
                if strongest:
                    name, corr = strongest
                    relation_text = self._correlation_phrase(corr)
                    parts.append(
                        f"{self._label(name).lower()} is the strongest measurable numeric signal and {relation_text} the target metric."
                    )

        elif intent == "trend_analysis" and time_summary:
            first_period = time_summary.get("first_period")
            last_period = time_summary.get("last_period")
            change_pct = time_summary.get("change_pct")
            best_period = time_summary.get("best_period")

            if requested_dimension:
                parts.append(
                    f"The question is about how {target_label} changes over time across {self._label(requested_dimension).lower()} groups."
                )

            if first_period and last_period and change_pct is not None:
                direction = "increased" if change_pct >= 0 else "decreased"
                parts.append(
                    f"{self._label(target)} {direction} by {abs(change_pct):.1f}% from {first_period} to {last_period}."
                )

            if best_period:
                parts.append(f"The strongest observed period was {best_period}.")

        else:
            if selected_segment and requested_dimension:
                descriptor = "lowest" if ranking_direction == "ascending" else "leading"
                parts.append(
                    f"The clearest visible {descriptor} result is {selected_segment} within {self._label(requested_dimension).lower()}."
                )
            else:
                parts.append(repaired_direct_answer)

        if not parts:
            parts.append(repaired_direct_answer)

        return " ".join(parts)

    # =====================================================
    # Extraction helpers
    # =====================================================

    def _infer_requested_dimension(self, question, plan, analysis, kpis):
        q = str(question or "").lower().strip()

        alias_order = [
            ("Sub-Category", ["sub-category", "sub category", "subcategory", "subcategories"]),
            ("Category", ["category", "categories"]),
            ("Segment", ["segment", "segments"]),
            ("Region", ["region", "regions"]),
            ("Country", ["country", "countries"]),
            ("State", ["state", "states"]),
            ("City", ["city", "cities"]),
            ("Product", ["product", "products", "item", "items", "sku", "stockcode", "stock code"]),
            ("Customer", ["customer", "customers", "client", "clients"]),
            ("Ship Mode", ["ship mode", "shipping mode"]),
            ("Sales Person", ["sales person", "salesperson", "seller", "rep", "representative"]),
        ]

        for canonical, words in alias_order:
            if any(word in q for word in words):
                for driver in plan.get("drivers", []) or []:
                    if self._dimension_matches(driver, canonical):
                        return driver

                for seg in analysis.get("top_segments", []) or []:
                    dim = seg.get("dimension")
                    if self._dimension_matches(dim, canonical):
                        return dim

                top_dim = kpis.get("top_dimension_name")
                if self._dimension_matches(top_dim, canonical):
                    return top_dim

                return canonical

        for driver in plan.get("drivers", []) or []:
            if not self._is_bad_dimension(driver):
                return driver

        return None

    def _infer_requested_numeric_driver(self, question, plan, analysis):
        q = str(question or "").lower().strip()

        candidates = [
            "discount", "sales", "profit", "quantity", "price", "unit price",
            "cost", "revenue", "margin", "score", "rate"
        ]

        for c in candidates:
            if c in q:
                for driver in plan.get("drivers", []) or []:
                    if c in str(driver).lower():
                        return driver
                for name in (analysis.get("correlations", {}) or {}).keys():
                    if c in str(name).lower():
                        return name
                return c.title() if c != "unit price" else "Unit Price"

        return None

    def _extract_selected_segment(self, question, analysis, kpis, requested_dimension):
        ranking_direction = self._infer_ranking_direction(question, None)

        segments = analysis.get("top_segments", []) or []
        if requested_dimension:
            for seg in segments:
                dim = str(seg.get("dimension", "")).strip().lower()
                req = str(requested_dimension).strip().lower()
                if dim == req and not self._is_placeholder(seg.get("segment")):
                    return str(seg.get("segment"))

        top_value = kpis.get("top_dimension_value")
        if top_value and not self._is_placeholder(top_value):
            return str(top_value)

        if ranking_direction == "ascending":
            worst_value = kpis.get("worst_dimension_value")
            if worst_value and not self._is_placeholder(worst_value):
                return str(worst_value)

        best_value = kpis.get("best_dimension_value")
        if best_value and not self._is_placeholder(best_value):
            return str(best_value)

        return None

    def _segment_metric_for_dimension(self, analysis, requested_dimension, selected_segment):
        segments = analysis.get("top_segments", []) or []
        for seg in segments:
            dim = str(seg.get("dimension", "")).strip().lower()
            seg_name = str(seg.get("segment", "")).strip().lower()
            if dim == str(requested_dimension).strip().lower() and seg_name == str(selected_segment).strip().lower():
                return seg.get("total_target")
        return None

    # =====================================================
    # Small helpers
    # =====================================================

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

    def _strongest_meaningful_correlation(self, correlations):
        if not correlations:
            return None

        ranked = sorted(correlations.items(), key=lambda x: abs(x[1]), reverse=True)
        for name, corr in ranked:
            lower = str(name).lower()
            if any(bad in lower for bad in ["id", "postal", "zip", "row"]):
                continue
            return name, corr
        return None

    def _correlation_phrase(self, corr):
        if corr is None:
            return "associated with"
        try:
            corr = float(corr)
        except Exception:
            return "associated with"

        if corr > 0:
            if abs(corr) >= 0.50:
                return "strongly positively associated with"
            if abs(corr) >= 0.20:
                return "positively associated with"
            return "weakly positively associated with"

        if corr < 0:
            if abs(corr) >= 0.50:
                return "strongly negatively associated with"
            if abs(corr) >= 0.20:
                return "negatively associated with"
            return "weakly negatively associated with"

        return "not meaningfully associated with"

    def _dimension_matches(self, value, canonical):
        value_norm = self._normalize_dimension(value)
        canon_norm = self._normalize_dimension(canonical)

        if value_norm == canon_norm:
            return True
        if canon_norm == "sub-category" and value_norm in {"sub-category", "sub category"}:
            return True
        if canon_norm == "sales person" and value_norm in {"sales person", "salesperson"}:
            return True
        return False

    def _normalize_dimension(self, value):
        text = str(value or "").strip().lower().replace("_", " ").replace("-", " ")
        text = " ".join(text.split())

        if text in {"subcategory", "sub category"}:
            return "sub-category"
        if text == "salesperson":
            return "sales person"
        return text

    def _is_bad_dimension(self, dim):
        d = str(dim or "").lower()
        return any(token in d for token in ["id", "postal", "zip", "row"])

    def _is_placeholder(self, value):
        s = str(value or "").strip().lower()
        return s in {"unknown", "n/a", "na", "null", "none", "error", "not available", ""}

    def _label(self, value):
        return str(value).replace("_", " ").strip()

    def _format_corr(self, value):
        try:
            return f"{float(value):.3f}"
        except Exception:
            return str(value)

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

    def _build_repair_reasoning(
        self,
        question,
        intent,
        requested_dimension,
        requested_numeric_driver,
        ranking_direction,
        selected_segment
    ):
        reasons = []

        if requested_dimension:
            reasons.append(
                f"The answer was anchored to the requested grouping dimension: {requested_dimension}."
            )

        if requested_numeric_driver and intent == "relationship_analysis":
            reasons.append(
                f"The relationship answer was forced to prioritize the asked-about variable: {requested_numeric_driver}."
            )

        if ranking_direction == "ascending":
            reasons.append(
                "Bottom-style wording was enforced because the question asks for least/lowest/worst behavior."
            )

        if selected_segment:
            reasons.append(
                f"The selected segment used for the final answer is: {selected_segment}."
            )

        if not reasons:
            reasons.append("The final answer was aligned to the question and available evidence.")

        return reasons