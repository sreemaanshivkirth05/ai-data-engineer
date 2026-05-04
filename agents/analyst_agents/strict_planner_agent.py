import re
from typing import Any, Dict, List, Optional


class StrictPlannerAgent:
    """
    Builds a strict machine-usable plan for execution.
    This is deterministic and heuristic-first.
    """

    METRIC_KEYWORDS = [
        "revenue", "sales", "amount", "profit", "cost", "price", "value", "income", "spend", "quantity"
    ]

    TIME_KEYWORDS = [
        "date", "time", "month", "year", "quarter", "week", "day", "timestamp", "created", "order date"
    ]

    GROUP_KEYWORDS = [
        "country", "region", "state", "city", "product", "sales person", "salesperson",
        "customer", "segment", "category", "department", "channel"
    ]

    def _extract_limit(self, question: str, default: int = 5) -> int:
        match = re.search(r"\btop\s+(\d+)\b", question.lower())
        if match:
            return int(match.group(1))
        match = re.search(r"\bbottom\s+(\d+)\b", question.lower())
        if match:
            return int(match.group(1))
        return default

    def _detect_sort(self, question: str) -> str:
        q = question.lower()
        if "bottom" in q or "lowest" in q or "worst" in q:
            return "asc"
        return "desc"

    def _extract_candidate_terms(self, question: str, vocabulary: List[str]) -> List[str]:
        q = question.lower()
        found = []
        for term in vocabulary:
            if term in q:
                found.append(term)
        return found

    def plan(
        self,
        question: str,
        question_type: str,
        dataset_profile: Dict[str, Any],
    ) -> Dict[str, Any]:
        candidate_metric_terms = self._extract_candidate_terms(question, self.METRIC_KEYWORDS)
        candidate_group_terms = self._extract_candidate_terms(question, self.GROUP_KEYWORDS)
        candidate_time_terms = self._extract_candidate_terms(question, self.TIME_KEYWORDS)

        plan: Dict[str, Any] = {
            "question_type": question_type,
            "target_metric_hint": candidate_metric_terms[0] if candidate_metric_terms else None,
            "aggregation": "sum",
            "group_by_hint": candidate_group_terms[:2],
            "time_column_hint": candidate_time_terms[0] if candidate_time_terms else None,
            "filters": [],
            "sort": self._detect_sort(question),
            "limit": self._extract_limit(question, default=5),
            "expected_output": "",
            "confidence": 0.6,
            "reasoning": {
                "target_why": "",
                "drivers_why": [],
                "warnings": [],
            }
        }

        if question_type == "ranking":
            plan["expected_output"] = "table + bar_chart + direct_answer"
            plan["reasoning"]["target_why"] = "Ranking questions require a metric column and a grouping dimension."
            plan["confidence"] = 0.8

        elif question_type == "trend":
            plan["expected_output"] = "time_series + line_chart + direct_answer"
            plan["reasoning"]["target_why"] = "Trend questions require a metric and a date/time column."
            plan["confidence"] = 0.8

        elif question_type == "comparison":
            plan["expected_output"] = "comparison_table + bar_chart + direct_answer"
            plan["reasoning"]["target_why"] = "Comparison questions require a metric and a comparison dimension."
            plan["confidence"] = 0.75

        elif question_type == "summary":
            plan["expected_output"] = "kpis + insight_cards + direct_answer"
            plan["reasoning"]["target_why"] = "Summary questions should compute dataset-level KPIs and dominant drivers."
            plan["confidence"] = 0.7

        elif question_type == "contribution":
            plan["expected_output"] = "contribution_table + bar_chart + direct_answer"
            plan["reasoning"]["target_why"] = "Contribution questions need metric share across a grouping dimension."
            plan["confidence"] = 0.75

        elif question_type == "distribution":
            plan["expected_output"] = "distribution_table + chart + direct_answer"
            plan["reasoning"]["target_why"] = "Distribution questions need either a numeric spread or category breakdown."
            plan["confidence"] = 0.7

        if not dataset_profile.get("numeric_columns"):
            plan["reasoning"]["warnings"].append("No numeric metric columns were detected in the dataset profile.")
            plan["confidence"] -= 0.2

        if question_type == "trend" and not dataset_profile.get("datetime_columns"):
            plan["reasoning"]["warnings"].append("No datetime columns were detected for trend analysis.")
            plan["confidence"] -= 0.25

        if question_type in {"ranking", "comparison", "contribution"} and not dataset_profile.get("categorical_columns"):
            plan["reasoning"]["warnings"].append("No strong categorical grouping columns were detected.")
            plan["confidence"] -= 0.15

        plan["confidence"] = max(0.1, min(plan["confidence"], 0.95))
        return plan