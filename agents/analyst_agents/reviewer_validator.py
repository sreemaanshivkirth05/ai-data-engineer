from typing import Dict, Any, List


class ReviewerValidator:
    """
    Validates whether the final answer matches the original question intent and computed result.
    """

    def validate(
        self,
        question: str,
        plan: Dict[str, Any],
        resolved: Dict[str, Any],
        result_object: Dict[str, Any],
        final_answer: Dict[str, Any],
    ) -> Dict[str, Any]:
        issues: List[str] = []
        question_lower = question.lower()
        question_type = plan.get("question_type")

        direct_answer = (final_answer.get("direct_answer") or "").lower()

        if question_type == "ranking":
            if "top" in question_lower and not result_object.get("top_results"):
                issues.append("Ranking question asked for top results, but no top results were computed.")
            if resolved.get("group_by"):
                expected_group = resolved["group_by"][0].lower()
                if expected_group not in direct_answer and not result_object.get("top_results"):
                    issues.append("Direct answer does not clearly reference the expected ranking group.")

        if question_type == "trend":
            if not result_object.get("time_series"):
                issues.append("Trend question asked for time behavior, but no time series was computed.")
            if "strongest" in question_lower and result_object.get("best_period") is None:
                issues.append("Question asked for strongest period, but best period was not computed.")
            if "weakest" in question_lower and result_object.get("worst_period") is None:
                issues.append("Question asked for weakest period, but worst period was not computed.")

        if question_type == "comparison":
            if not result_object.get("comparison_rows"):
                issues.append("Comparison question asked for comparison output, but no comparison rows were computed.")

        if not resolved.get("target_metric") and question_type != "summary":
            issues.append("No target metric was resolved for a non-summary question.")

        confidence = 0.92
        if issues:
            confidence = max(0.35, 0.92 - 0.12 * len(issues))

        return {
            "should_accept": len(issues) == 0,
            "is_aligned": len(issues) == 0,
            "confidence": confidence,
            "review_summary": "Answer is aligned with the computed result." if not issues else "Answer alignment issues detected.",
            "recommended_fix": "Revise planner resolution or deterministic execution for this question type." if issues else "None",
            "issues": issues,
        }