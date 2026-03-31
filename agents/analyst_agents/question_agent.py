class QuestionAgent:
    def run(self, question):
        q = (question or "").lower().strip()

        intent = "general_analysis"
        show_kpis = True
        question_category = "general"
        question_goal = "Understand the most important patterns in the dataset."
        is_count_question = False

        trend_terms = [
            "trend", "over time", "monthly", "daily", "weekly", "yearly",
            "timeline", "growth", "decline", "change over time", "seasonality"
        ]
        comparison_terms = [
            "compare", "comparison", "versus", "vs", "higher than", "lower than",
            "better than", "worse than", "difference between"
        ]
        distribution_terms = [
            "distribution", "spread", "outlier", "variance", "histogram",
            "range", "dispersion"
        ]
        relationship_terms = [
            "relationship", "correlation", "impact", "influence", "driver",
            "associated with", "linked to", "related to"
        ]
        ranking_terms = [
            "top", "best", "highest", "lowest", "rank", "ranking",
            "bottom", "leader", "laggard"
        ]
        summary_terms = [
            "summary", "overview", "dashboard", "kpi", "performance", "report",
            "snapshot"
        ]
        contribution_terms = [
            "contribution", "share", "mix", "composition", "portion", "split"
        ]
        segment_terms = [
            "segment", "group", "category", "region", "country", "channel",
            "customer", "product"
        ]
        count_terms = [
            "count", "counts", "how many", "number of", "total number"
        ]

        if any(term in q for term in count_terms):
            is_count_question = True

        if any(term in q for term in trend_terms):
            intent = "trend_analysis"
            question_category = "trend"
            question_goal = "Understand how performance changes over time."

        elif any(term in q for term in comparison_terms):
            intent = "comparison"
            question_category = "comparison"
            question_goal = "Compare performance across groups and identify leaders and laggards."

        elif any(term in q for term in distribution_terms):
            intent = "distribution_analysis"
            question_category = "distribution"
            question_goal = "Understand spread, concentration, and unusual values."

        elif any(term in q for term in relationship_terms):
            intent = "relationship_analysis"
            question_category = "relationship"
            question_goal = "Identify which measurable factors move most strongly with the target."

        elif any(term in q for term in contribution_terms):
            intent = "contribution_analysis"
            question_category = "contribution"
            question_goal = "Understand which groups contribute the most to the overall result."

        elif any(term in q for term in ranking_terms):
            intent = "ranking_analysis"
            question_category = "ranking"
            question_goal = "Identify the top and bottom performers across the dataset."

        elif any(term in q for term in segment_terms):
            intent = "segment_analysis"
            question_category = "segment"
            question_goal = "Understand how performance differs across business segments."

        elif any(term in q for term in summary_terms):
            intent = "summary_analysis"
            question_category = "summary"
            question_goal = "Provide a business-friendly summary of overall performance."

        if is_count_question:
            question_goal = "Count records or entities and compare how those counts vary across groups."

        kpi_terms = [
            "total", "average", "avg", "top", "best", "highest", "lowest",
            "revenue", "sales", "profit", "performance", "summary", "overview",
            "kpi", "metric", "count", "number of", "how many"
        ]

        show_kpis = any(term in q for term in kpi_terms) or intent != "distribution_analysis"

        # --------------------------
        # OVERVIEW MODE DETECTION
        # --------------------------
        # Fires when the question is broad/exploratory with no specific metric named.
        # Controls answer framing in build_direct_answer and storytelling agents.
        OVERVIEW_EXACT = {
            "kpi overview", "kpi insights", "pki insights", "pki overview",
            "dataset overview", "business summary", "overall performance",
            "overview", "summary", "insights", "analysis", "show insights",
            "general overview", "full overview", "full summary",
        }

        OVERVIEW_FRAGMENTS = [
            "overview", "overall", "big picture", "dashboard", "snapshot",
            "tell me about", "what can you tell", "show me the data",
            "explore this", "general analysis", "full picture",
        ]

        SPECIFIC_METRIC_TERMS = [
            "sales", "revenue", "profit", "quantity", "cost", "price",
            "discount", "margin", "amount", "units", "score",
        ]

        token_count = len(q.split())
        has_specific_metric = any(term in q for term in SPECIFIC_METRIC_TERMS)

        is_overview_mode = (
            q in OVERVIEW_EXACT
            or (any(f in q for f in OVERVIEW_FRAGMENTS) and not has_specific_metric)
            or (token_count <= 4 and intent in ("summary_analysis", "general_analysis") and not has_specific_metric)
        )

        return {
            "question": question,
            "intent": intent,
            "show_kpis": show_kpis,
            "question_category": question_category,
            "question_goal": question_goal,
            "is_count_question": is_count_question,
            "is_overview_mode": is_overview_mode,
        }