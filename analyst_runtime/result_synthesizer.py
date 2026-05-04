from typing import Dict, Any, List


class ResultSynthesizer:
    """
    Generates direct answer, executive summary, insight cards, narrative, and follow-ups
    ONLY from computed results.
    """

    def synthesize(
        self,
        question: str,
        resolved: Dict[str, Any],
        result_object: Dict[str, Any],
        dataset_summary: Dict[str, Any],
        data_quality_summary: Dict[str, Any],
    ) -> Dict[str, Any]:
        question_type = resolved.get("question_type")
        target = resolved.get("target_metric")
        group_by = resolved.get("group_by", [])
        time_column = resolved.get("time_column")

        direct_answer = "No direct answer could be generated."
        executive_summary = "No executive summary available."
        top_insights: List[Dict[str, Any]] = []
        business_impact: List[str] = []
        recommended_actions: List[str] = []
        risks_or_limitations: List[str] = []
        follow_up_questions: List[str] = []

        if question_type == "ranking":
            rows = result_object.get("top_results", [])
            if rows:
                first = rows[0]
                dim = group_by[0] if group_by else "group"
                direct_answer = (
                    f"The highest {dim.lower()} by total {target} is {first[dim]} "
                    f"with a value of {round(float(first[target]), 2)}."
                )
                executive_summary = (
                    f"This ranking shows which {dim.lower()} contribute the most to {target}. "
                    f"The leading segment is clearly visible in the computed top results."
                )
                for row in rows[:4]:
                    top_insights.append({
                        "title": row[dim],
                        "value": round(float(row[target]), 2),
                        "detail": f"{dim} contribution by total {target}.",
                        "type": "signal",
                    })
                business_impact.append(f"Use the ranking to prioritize the strongest-performing {dim.lower()} segments.")
                recommended_actions.append(f"Investigate why the top {dim.lower()} is outperforming others.")
                recommended_actions.append(f"Review the lowest-ranked {dim.lower()} segments for improvement opportunities.")
                follow_up_questions = [
                    f"Show the monthly trend for the top {dim.lower()} by {target}.",
                    f"Which {dim.lower()} underperforms the most by {target}?",
                    f"Compare the top two {dim.lower()} by {target}.",
                ]

        elif question_type == "trend":
            best_period = result_object.get("best_period")
            worst_period = result_object.get("worst_period")
            change = result_object.get("period_change_pct")
            direct_answer = (
                f"The trend in {target} was computed over time. "
                f"The strongest period was {best_period}, and the weakest period was {worst_period}."
            )
            if change is not None:
                direct_answer += f" Overall change from first to last period was {change}%."

            executive_summary = (
                f"This trend analysis shows how {target} changes across time and highlights the strongest and weakest periods."
            )
            top_insights = [
                {
                    "title": "Best period",
                    "value": best_period or "N/A",
                    "detail": f"Highest observed period by aggregated {target}.",
                    "type": "positive",
                },
                {
                    "title": "Worst period",
                    "value": worst_period or "N/A",
                    "detail": f"Weakest observed period by aggregated {target}.",
                    "type": "risk",
                },
                {
                    "title": "Period change",
                    "value": f"{change}%" if change is not None else "N/A",
                    "detail": "Overall directional change from the first to last period.",
                    "type": "signal",
                }
            ]
            business_impact.append("Trend changes can guide timing decisions, inventory, staffing, and campaign planning.")
            recommended_actions.append("Investigate the strongest and weakest periods for operational or commercial drivers.")
            recommended_actions.append("Break the time trend by a major grouping dimension to isolate the source of variation.")
            follow_up_questions = [
                f"Break the {target} trend down by product.",
                f"Which segment contributed most in {best_period}?",
                f"Compare the strongest and weakest periods in more detail.",
            ]

        elif question_type == "comparison":
            rows = result_object.get("comparison_rows", [])
            diff = result_object.get("difference_top_2")
            if rows:
                direct_answer = (
                    f"The comparison shows {rows[0][group_by[0]]} as the leading segment by {target}."
                )
                if diff is not None and len(rows) > 1:
                    direct_answer += f" It leads the second segment by {round(diff, 2)}."
                executive_summary = "This comparison highlights the relative performance gap between the leading groups."
                for row in rows[:4]:
                    top_insights.append({
                        "title": row[group_by[0]],
                        "value": round(float(row[target]), 2),
                        "detail": f"Computed {target} for the compared group.",
                        "type": "signal",
                    })
            business_impact.append("Use the comparison to identify relative performance gaps between groups.")
            recommended_actions.append("Investigate drivers of the gap between the top groups.")
            follow_up_questions = [
                f"Show the time trend for the top {group_by[0]}.",
                f"Which factor most influences this comparison?",
            ]

        elif question_type == "summary":
            stats = result_object.get("summary_stats", {})
            direct_answer = (
                f"This dataset contains {dataset_summary.get('row_count')} rows and {dataset_summary.get('column_count')} columns."
            )
            if target:
                direct_answer += f" The main target metric is {target}."
            executive_summary = (
                "This summary combines overall dataset size, key KPI signals, and the dominant business dimension."
            )
            if stats.get("total_target") is not None:
                top_insights.append({
                    "title": f"Total {target}",
                    "value": round(float(stats["total_target"]), 2),
                    "detail": f"Total computed value of {target}.",
                    "type": "positive",
                })
            if stats.get("top_dimension_name") and stats.get("top_dimension_value"):
                top_insights.append({
                    "title": f"Top {stats['top_dimension_name']}",
                    "value": stats["top_dimension_value"],
                    "detail": f"Leading segment by {target}.",
                    "type": "signal",
                })
            business_impact.append("This summary gives a fast business overview before deeper drill-down analysis.")
            recommended_actions.append("Use the top KPI signals to choose a follow-up trend or ranking analysis.")
            follow_up_questions = [
                f"What are the top 5 groups by {target}?" if target else "What are the top 5 contributing groups?",
                f"Show the time trend for {target}." if target else "Show the monthly trend of the main metric.",
            ]

        elif question_type == "contribution":
            top_entity = result_object.get("top_entity")
            top_share = result_object.get("top_share_pct")
            dim = group_by[0] if group_by else "group"
            direct_answer = (
                f"The biggest contributor is {top_entity} with approximately {top_share}% share of {target}."
                if top_entity is not None else
                f"The contribution analysis was computed for {target} across {dim}."
            )
            executive_summary = "This contribution view shows which segment accounts for the largest share of the metric."
            for row in result_object.get("contribution_rows", [])[:4]:
                top_insights.append({
                    "title": row[dim],
                    "value": f"{row['share_pct']}%",
                    "detail": f"Share of total {target}.",
                    "type": "signal",
                })
            business_impact.append("Contribution analysis helps identify concentration risk and dominant performers.")
            recommended_actions.append("Review whether the top contributor represents healthy concentration or dependency risk.")
            follow_up_questions = [
                f"Show the trend of the top contributor over time.",
                f"Which contributor has the lowest share?",
            ]

        elif question_type == "distribution":
            stats = result_object.get("distribution_stats", {})
            if stats:
                direct_answer = (
                    f"The distribution of {target} has a mean of {round(float(stats['mean']), 2) if stats.get('mean') is not None else 'N/A'} "
                    f"and a median of {round(float(stats['median']), 2) if stats.get('median') is not None else 'N/A'}."
                )
                executive_summary = "This distribution view shows the spread and central tendency of the selected metric."
                top_insights = [
                    {
                        "title": "Mean",
                        "value": round(float(stats["mean"]), 2) if stats.get("mean") is not None else "N/A",
                        "detail": "Average value of the metric.",
                        "type": "signal",
                    },
                    {
                        "title": "Median",
                        "value": round(float(stats["median"]), 2) if stats.get("median") is not None else "N/A",
                        "detail": "Middle value of the metric.",
                        "type": "signal",
                    }
                ]
            business_impact.append("Distribution helps understand spread, skew, and whether averages may hide variation.")
            recommended_actions.append("Segment the distribution by a key grouping column for deeper insight.")
            follow_up_questions = [
                f"Break this distribution down by {group_by[0]}." if group_by else "Break this distribution down by a major group.",
            ]

        if data_quality_summary.get("overall_missing_pct", 0) > 10:
            risks_or_limitations.append("High missingness may affect the stability of the result.")
        if data_quality_summary.get("duplicate_rows", 0) > 0:
            risks_or_limitations.append("Duplicate rows may influence totals or grouped calculations.")
        if resolved.get("warnings"):
            risks_or_limitations.extend(resolved["warnings"])

        narrative = {
            "title": "Analyst Narrative",
            "summary": executive_summary,
            "paragraphs": [
                direct_answer,
                "This answer was generated from deterministic computation rather than freeform estimation.",
                "Use the supporting visuals and KPI context to validate the result before making decisions."
            ]
        }

        story = {
            "title": "Business Story",
            "headline": direct_answer,
            "key_points": [item["detail"] for item in top_insights[:3]] if top_insights else [],
            "business_view": business_impact[:2],
        }

        return {
            "direct_answer": direct_answer,
            "executive_summary": executive_summary,
            "question_goal": f"Answer the business question: {question}",
            "top_insights": top_insights,
            "business_impact": business_impact,
            "recommended_actions": recommended_actions,
            "risks_or_limitations": risks_or_limitations,
            "follow_up_questions": follow_up_questions,
            "narrative": narrative,
            "story": story,
        }