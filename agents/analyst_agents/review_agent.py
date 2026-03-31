class ReviewAgent:
    """
    Deterministic consistency reviewer for the AI Data Analyst flow.

    Purpose:
    - Check alignment between question, planner intent, KPI outputs, charts, direct answer,
      narrative summary, and story headline.
    - Surface specific issues before final rendering.
    - Provide suggested fixes that downstream pipeline can use for repair.

    This agent is intentionally rule-based and explainable.
    """

    def run(
        self,
        question,
        target,
        intent,
        plan=None,
        kpis=None,
        analysis=None,
        charts=None,
        business_layer=None,
        narrative=None,
        story=None,
    ):
        plan = plan or {}
        kpis = kpis or {}
        analysis = analysis or {}
        charts = charts or []
        business_layer = business_layer or {}
        narrative = narrative or {}
        story = story or {}

        question = str(question or "").strip()
        question_lower = question.lower()

        target = target or plan.get("target")
        ranking_direction = self._infer_ranking_direction(question, target)
        requested_dimension = self._infer_requested_dimension(
            question=question,
            plan=plan,
            analysis=analysis,
            kpis=kpis
        )

        direct_answer = str(business_layer.get("direct_answer", "") or "")
        executive_summary = str(business_layer.get("executive_summary", "") or "")
        narrative_summary = str(narrative.get("summary", "") or "")
        story_headline = str(story.get("headline", "") or "")
        narrative_paragraphs = narrative.get("paragraphs", []) or []
        story_key_points = story.get("key_points", []) or []
        primary_chart = self._get_primary_chart(charts)

        issues = []
        warnings = []
        suggestions = {}

        # -------------------------------------------------
        # Rule 1: ranking direction consistency
        # -------------------------------------------------
        if ranking_direction == "ascending":
            top_words = ["leading", "top", "highest", "strongest", "best performer", "best segment"]
            text_blocks = [
                ("direct_answer", direct_answer),
                ("executive_summary", executive_summary),
                ("narrative_summary", narrative_summary),
                ("story_headline", story_headline),
            ]

            for block_name, text in text_blocks:
                if self._contains_any(text, top_words):
                    issues.append({
                        "type": "ranking_mismatch",
                        "severity": "high",
                        "location": block_name,
                        "message": (
                            f"The question is bottom-style, but {block_name} still uses top-style wording."
                        )
                    })

            if primary_chart:
                chart_title = str(primary_chart.get("title", "")).lower()
                if self._contains_any(chart_title, ["top ", "highest", "leading"]) and not self._contains_any(chart_title, ["lowest", "least", "bottom", "worst"]):
                    issues.append({
                        "type": "ranking_mismatch",
                        "severity": "high",
                        "location": "primary_chart",
                        "message": "Primary chart title does not reflect bottom-style ranking."
                    })

        # -------------------------------------------------
        # Rule 2: requested grouping consistency
        # -------------------------------------------------
        if requested_dimension:
            requested_dimension_lower = str(requested_dimension).lower().strip()

            # Chart title
            if primary_chart:
                chart_title = str(primary_chart.get("title", "") or "")
                if requested_dimension_lower not in chart_title.lower():
                    issues.append({
                        "type": "group_mismatch",
                        "severity": "high",
                        "location": "primary_chart",
                        "message": (
                            f"Question/planner indicate grouping by {requested_dimension}, "
                            f"but the primary chart title does not reflect that grouping."
                        )
                    })

            # Text blocks should not drift away from requested grouping when explicit
            text_blocks = [
                ("direct_answer", direct_answer),
                ("executive_summary", executive_summary),
                ("narrative_summary", narrative_summary),
                ("story_headline", story_headline),
            ]

            for block_name, text in text_blocks:
                if text and not self._text_mentions_dimension_or_segment(text, requested_dimension):
                    warnings.append({
                        "type": "group_soft_mismatch",
                        "severity": "medium",
                        "location": block_name,
                        "message": (
                            f"{block_name} may not be explicitly aligned to the requested grouping dimension: {requested_dimension}."
                        )
                    })

        # -------------------------------------------------
        # Rule 3: KPI vs direct answer alignment
        # -------------------------------------------------
        selected_segment = self._extract_selected_segment(question, analysis, kpis, requested_dimension)
        if selected_segment:
            if direct_answer and selected_segment.lower() not in direct_answer.lower():
                issues.append({
                    "type": "answer_kpi_mismatch",
                    "severity": "high",
                    "location": "direct_answer",
                    "message": (
                        f"Direct answer does not match the selected segment from KPI/analysis: {selected_segment}."
                    )
                })

            if story_headline and selected_segment.lower() not in story_headline.lower():
                warnings.append({
                    "type": "story_kpi_mismatch",
                    "severity": "medium",
                    "location": "story_headline",
                    "message": (
                        f"Story headline does not clearly match the selected segment from KPI/analysis: {selected_segment}."
                    )
                })

        # -------------------------------------------------
        # Rule 4: planner grouping vs narrative/story drift
        # -------------------------------------------------
        planner_drivers = plan.get("drivers", []) or []
        planner_group_dimension = requested_dimension or self._best_group_dimension_from_plan(planner_drivers)

        if planner_group_dimension:
            drifting_dims = self._detect_drift_dimensions(
                planner_group_dimension=planner_group_dimension,
                narrative_summary=narrative_summary,
                story_headline=story_headline,
                narrative_paragraphs=narrative_paragraphs,
                story_key_points=story_key_points
            )

            for drift in drifting_dims:
                warnings.append({
                    "type": "narrative_group_drift",
                    "severity": "medium",
                    "location": drift["location"],
                    "message": drift["message"]
                })

        # -------------------------------------------------
        # Rule 5: trend question should keep time + grouping alignment
        # -------------------------------------------------
        if intent == "trend_analysis":
            if primary_chart:
                chart_title = str(primary_chart.get("title", "") or "").lower()
                if "trend" not in chart_title and "over time" not in chart_title:
                    issues.append({
                        "type": "trend_chart_mismatch",
                        "severity": "high",
                        "location": "primary_chart",
                        "message": "Trend question detected, but primary chart is not clearly time-based."
                    })

            time_column = plan.get("time_column")
            if not time_column:
                warnings.append({
                    "type": "trend_time_missing",
                    "severity": "medium",
                    "location": "plan",
                    "message": "Trend question detected, but no time column is set in the plan."
                })

        # -------------------------------------------------
        # Suggested fixes
        # -------------------------------------------------
        suggestions["requested_dimension"] = requested_dimension
        suggestions["ranking_direction"] = ranking_direction
        suggestions["selected_segment"] = selected_segment
        suggestions["primary_chart_title"] = primary_chart.get("title") if primary_chart else None
        suggestions["use_requested_dimension_in_text"] = bool(requested_dimension)
        suggestions["avoid_top_language"] = ranking_direction == "ascending"

        passed = not any(issue["severity"] == "high" for issue in issues)

        return {
            "passed": passed,
            "issues": issues,
            "warnings": warnings,
            "suggestions": suggestions,
            "review_summary": self._build_review_summary(
                passed=passed,
                issues=issues,
                warnings=warnings,
                requested_dimension=requested_dimension,
                ranking_direction=ranking_direction,
                selected_segment=selected_segment
            )
        }

    # =====================================================
    # Core extractors
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
            ("Product", ["product", "products", "item", "items", "sku"]),
            ("Customer", ["customer", "customers", "client", "clients"]),
            ("Ship Mode", ["ship mode", "shipping mode"]),
            ("Sales Person", ["sales person", "salesperson", "seller", "rep", "representative"]),
        ]

        for canonical, words in alias_order:
            if any(word in q for word in words):
                # First, try exact planner drivers
                for driver in plan.get("drivers", []) or []:
                    if self._dimension_matches(driver, canonical):
                        return driver

                # Then use analysis top segments
                for seg in analysis.get("top_segments", []) or []:
                    dim = seg.get("dimension")
                    if self._dimension_matches(dim, canonical):
                        return dim

                # Then KPI name
                top_dim = kpis.get("top_dimension_name")
                if self._dimension_matches(top_dim, canonical):
                    return top_dim

                return canonical

        # Fallback to first meaningful driver
        for driver in plan.get("drivers", []) or []:
            if not self._is_bad_dimension(driver):
                return driver

        return None

    def _extract_selected_segment(self, question, analysis, kpis, requested_dimension):
        ranking_direction = self._infer_ranking_direction(question, None)

        # First use analysis top_segments aligned to requested dimension
        segments = analysis.get("top_segments", []) or []
        if requested_dimension:
            for seg in segments:
                dim = str(seg.get("dimension", "")).strip().lower()
                req = str(requested_dimension).strip().lower()
                if dim == req and not self._is_placeholder(seg.get("segment")):
                    return str(seg.get("segment"))

        # Then KPI top dimension value
        top_value = kpis.get("top_dimension_value")
        if top_value and not self._is_placeholder(top_value):
            return str(top_value)

        # Then best/worst dimension values
        if ranking_direction == "ascending":
            worst_value = kpis.get("worst_dimension_value")
            if worst_value and not self._is_placeholder(worst_value):
                return str(worst_value)

        best_value = kpis.get("best_dimension_value")
        if best_value and not self._is_placeholder(best_value):
            return str(best_value)

        return None

    def _get_primary_chart(self, charts):
        if not charts:
            return None

        for chart in charts:
            if chart.get("primary"):
                return chart

        return charts[0]

    # =====================================================
    # Drift / consistency helpers
    # =====================================================

    def _detect_drift_dimensions(
        self,
        planner_group_dimension,
        narrative_summary,
        story_headline,
        narrative_paragraphs,
        story_key_points
    ):
        drifts = []
        planner_dim_norm = self._normalize_dimension(planner_group_dimension)

        competing_dimensions = [
            "category", "sub-category", "segment", "region",
            "country", "product", "customer", "ship mode"
        ]

        text_targets = [
            ("narrative_summary", narrative_summary),
            ("story_headline", story_headline),
        ]

        for p in narrative_paragraphs[:3]:
            text_targets.append(("narrative_paragraph", p))
        for p in story_key_points[:3]:
            text_targets.append(("story_key_point", p))

        for location, text in text_targets:
            lower = str(text or "").lower()
            if not lower:
                continue

            for comp in competing_dimensions:
                if comp == planner_dim_norm:
                    continue
                if comp in lower and planner_dim_norm not in lower:
                    drifts.append({
                        "location": location,
                        "message": (
                            f"Text appears to drift toward {comp} instead of the requested/planned grouping: {planner_group_dimension}."
                        )
                    })
                    break

        return drifts

    def _text_mentions_dimension_or_segment(self, text, dimension):
        lower = str(text or "").lower()
        dim_norm = self._normalize_dimension(dimension)

        alias_map = {
            "sub-category": ["sub-category", "sub category", "subcategory"],
            "category": ["category", "categories"],
            "segment": ["segment", "segments"],
            "region": ["region", "regions"],
            "country": ["country", "countries"],
            "product": ["product", "products", "item", "items"],
            "customer": ["customer", "customers", "client", "clients"],
            "ship mode": ["ship mode", "shipping mode"],
            "sales person": ["sales person", "salesperson", "seller", "rep"],
        }

        aliases = alias_map.get(dim_norm, [dim_norm])
        return any(alias in lower for alias in aliases)

    def _best_group_dimension_from_plan(self, drivers):
        for driver in drivers or []:
            if not self._is_bad_dimension(driver):
                return driver
        return None

    # =====================================================
    # Ranking / dimension matching
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

    def _dimension_matches(self, value, canonical):
        value_norm = self._normalize_dimension(value)
        canon_norm = self._normalize_dimension(canonical)

        if value_norm == canon_norm:
            return True

        if canon_norm == "sub-category" and value_norm in {"sub-category", "sub category"}:
            return True
        if canon_norm == "category" and value_norm == "category":
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

    # =====================================================
    # Text helpers
    # =====================================================

    def _contains_any(self, text, tokens):
        lower = str(text or "").lower()
        return any(token in lower for token in tokens)

    def _is_bad_dimension(self, dim):
        d = str(dim or "").lower()
        return any(token in d for token in ["id", "postal", "zip", "row"])

    def _is_placeholder(self, value):
        s = str(value or "").strip().lower()
        return s in {"unknown", "n/a", "na", "null", "none", "error", "not available", ""}

    # =====================================================
    # Summary
    # =====================================================

    def _build_review_summary(self, passed, issues, warnings, requested_dimension, ranking_direction, selected_segment):
        if passed:
            return (
                f"Review passed. The answer set is broadly consistent with the question, "
                f"requested dimension={requested_dimension}, ranking_direction={ranking_direction}, "
                f"selected_segment={selected_segment}."
            )

        high_count = sum(1 for x in issues if x.get("severity") == "high")
        med_count = sum(1 for x in warnings if x.get("severity") == "medium")

        return (
            f"Review found consistency issues. "
            f"High-severity issues={high_count}, medium warnings={med_count}, "
            f"requested dimension={requested_dimension}, ranking_direction={ranking_direction}, "
            f"selected_segment={selected_segment}."
        )