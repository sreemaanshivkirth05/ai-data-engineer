class NarrativeAgent:

    def run(self, question, analysis, kpis=None, target=None, business_layer=None):
        kpis = kpis or {}
        analysis = analysis or {}
        business_layer = business_layer or {}

        correlations = analysis.get("correlations", {}) or {}
        categorical_drivers = analysis.get("categorical_drivers", {}) or {}
        time_summary = analysis.get("time_summary", {}) or {}
        distribution_summary = analysis.get("distribution_summary", {}) or {}
        outlier_summary = analysis.get("outlier_summary", {}) or {}
        top_segments = analysis.get("top_segments", []) or []
        top_bottom_segments = analysis.get("top_bottom_segments", {}) or {}
        analysis_metadata = analysis.get("analysis_metadata", {}) or {}

        intent = analysis_metadata.get("intent") or infer_intent_from_analysis(
            time_summary=time_summary,
            correlations=correlations,
            distribution_summary=distribution_summary
        )

        paragraphs = []

        if target:
            paragraphs.append(
                f"This analysis focuses on {format_label(target).lower()} because it is the primary metric most relevant to the business question."
            )

        if business_layer.get("direct_answer"):
            paragraphs.append(business_layer["direct_answer"])

        if intent == "trend_analysis" and time_summary:
            first_period = time_summary.get("first_period")
            last_period = time_summary.get("last_period")
            first_value = time_summary.get("first_value")
            last_value = time_summary.get("last_value")
            change_pct = time_summary.get("change_pct")
            best_period = time_summary.get("best_period")
            worst_period = time_summary.get("worst_period")

            trend_parts = []

            if first_period and last_period and first_value is not None and last_value is not None:
                trend_text = (
                    f"Over time, {format_label(target).lower()} moved from {format_number(first_value)} in {first_period} "
                    f"to {format_number(last_value)} in {last_period}"
                )
                if change_pct is not None:
                    direction = "increase" if change_pct >= 0 else "decrease"
                    trend_text += f", which represents an overall {direction} of {abs(change_pct):.1f}%."
                else:
                    trend_text += "."
                trend_parts.append(trend_text)

            if best_period:
                trend_parts.append(
                    f"The strongest observed period was {best_period}, which stands out as the clearest time-based benchmark."
                )

            if worst_period:
                trend_parts.append(
                    f"The weakest observed period was {worst_period}, which helps frame the range of performance across the timeline."
                )

            if trend_parts:
                paragraphs.append(" ".join(trend_parts))

        if kpis.get("total_target") is not None and kpis.get("average_target") is not None and target:
            paragraphs.append(
                f"At the overall level, total {format_label(target).lower()} is {format_number(kpis['total_target'])}, while the average per usable record is {format_number(kpis['average_target'])}. This gives a useful sense of scale before looking at deeper variation."
            )

        if top_segments:
            best = top_segments[0]
            paragraphs.append(
                f"The strongest visible segment is {best.get('segment')} within {format_label(best.get('dimension')).lower()}, contributing {format_number(best.get('total_target'))}. This makes it the clearest benchmark when comparing performance across the rest of the dataset."
            )
        elif kpis.get("top_dimension_name") and kpis.get("top_dimension_value"):
            dim_name = str(kpis["top_dimension_name"]).lower()
            dim_value = str(kpis["top_dimension_value"])
            dim_metric = format_number(kpis.get("top_dimension_metric"))
            paragraphs.append(
                f"The strongest visible segment is {dim_value} within {dim_name}, contributing {dim_metric}. This makes it the clearest benchmark when comparing performance across the rest of the dataset."
            )

        if intent == "relationship_analysis" and correlations:
            sorted_corr = sorted(
                correlations.items(),
                key=lambda x: abs(x[1]),
                reverse=True
            )
            top_corr = sorted_corr[:2]

            if top_corr:
                details = []
                for col, val in top_corr:
                    direction = "moves in the same direction as" if val > 0 else "moves in the opposite direction to"
                    details.append(f"{format_label(col).lower()} {direction} the target (correlation: {val})")

                paragraphs.append(
                    "The numeric relationship analysis shows that " + "; ".join(details) + ". These are useful directional signals for further investigation, even though they should not be treated as proof of causation."
                )

        elif correlations and intent != "trend_analysis":
            top_corr = sorted(correlations.items(), key=lambda x: abs(x[1]), reverse=True)[:2]
            if top_corr:
                details = []
                for col, val in top_corr:
                    relation = "positive" if val > 0 else "negative"
                    details.append(f"{format_label(col)} ({relation}, correlation {val})")
                paragraphs.append(
                    f"The strongest measurable numeric signals are {', '.join(details)}, which suggests these fields are worth investigating as potential drivers of {format_label(target).lower()}."
                )

        if categorical_drivers:
            sorted_cat = sorted(
                categorical_drivers.items(),
                key=lambda x: x[1],
                reverse=True
            )
            top_fields = [format_label(col) for col, _ in sorted_cat[:2]]

            if top_fields:
                paragraphs.append(
                    "The most meaningful group-level differences appear across " + ", ".join(top_fields) + ". This means performance is not evenly distributed and that segment-level analysis is important for decision-making."
                )

        if distribution_summary:
            mean_val = distribution_summary.get("mean")
            median_val = distribution_summary.get("median")
            std_val = distribution_summary.get("std")

            distribution_parts = []
            if mean_val is not None and median_val is not None:
                distribution_parts.append(
                    f"The distribution of {format_label(target).lower()} has a mean of {format_number(mean_val)} and a median of {format_number(median_val)}"
                )
            if std_val is not None:
                distribution_parts.append(
                    f"with a standard deviation of {format_number(std_val)}"
                )

            if distribution_parts:
                paragraphs.append(" ".join(distribution_parts) + ", which helps describe overall spread and concentration in the metric.")

        if outlier_summary.get("outlier_count", 0) > 0:
            paragraphs.append(
                f"There are {outlier_summary.get('outlier_count')} detected outliers, representing about {outlier_summary.get('outlier_pct', 0)}% of usable records. This suggests that unusually high or low values may be influencing the overall result."
            )

        if top_bottom_segments:
            top_dimension = next(iter(top_bottom_segments.keys()), None)
            if top_dimension:
                comparison = top_bottom_segments[top_dimension]
                top_info = comparison.get("top", {})
                bottom_info = comparison.get("bottom", {})

                if top_info and bottom_info:
                    paragraphs.append(
                        f"Within {format_label(top_dimension).lower()}, the gap between the strongest group ({top_info.get('segment')}) and weakest group ({bottom_info.get('segment')}) is large enough to matter for prioritization and decision support."
                    )

        if business_layer.get("business_impact"):
            paragraphs.append(
                "From a business perspective, " + " ".join(business_layer["business_impact"])
            )

        if business_layer.get("risks_or_limitations"):
            paragraphs.append(
                "At the same time, the analysis should be read with a few caveats in mind: " + " ".join(business_layer["risks_or_limitations"][:2])
            )

        paragraphs.append(
            "Taken together, the results show not just what is happening in the dataset, but where performance is concentrated, which patterns are most important, and where further action or deeper analysis would be most useful."
        )

        return {
            "title": "Analyst Narrative",
            "summary": build_summary_line(target, kpis, business_layer, analysis, intent),
            "paragraphs": paragraphs
        }


def build_summary_line(target, kpis, business_layer, analysis, intent):
    if business_layer.get("executive_summary"):
        return business_layer["executive_summary"]

    time_summary = analysis.get("time_summary", {}) or {}
    top_segments = analysis.get("top_segments", []) or {}

    if intent == "trend_analysis" and time_summary:
        first_period = time_summary.get("first_period")
        last_period = time_summary.get("last_period")
        change_pct = time_summary.get("change_pct")

        if first_period and last_period and change_pct is not None:
            direction = "up" if change_pct >= 0 else "down"
            return (
                f"At a high level, {format_label(target).lower()} moved {direction} by {abs(change_pct):.1f}% from {first_period} to {last_period}."
            )

    if top_segments:
        best = top_segments[0]
        return (
            f"At a high level, the leading {format_label(best.get('dimension')).lower()} "
            f"is {best.get('segment')}, and the analysis is centered on {format_label(target).lower()}."
        )

    if target and kpis.get("top_dimension_value") and kpis.get("top_dimension_name"):
        return (
            f"At a high level, the leading {str(kpis['top_dimension_name']).lower()} "
            f"is {kpis['top_dimension_value']}, and the analysis is centered on {format_label(target).lower()}."
        )

    if target:
        return f"At a high level, this analysis is centered on {format_label(target).lower()}."

    return "At a high level, the dataset was analyzed successfully."


def infer_intent_from_analysis(time_summary, correlations, distribution_summary):
    if time_summary:
        return "trend_analysis"
    if correlations:
        return "relationship_analysis"
    if distribution_summary:
        return "distribution_analysis"
    return "general_analysis"


def format_number(value):
    if value is None:
        return "N/A"
    try:
        value = float(value)
        abs_value = abs(value)

        if abs_value >= 1_000_000_000:
            return f"{value / 1_000_000_000:.2f}B"
        if abs_value >= 1_000_000:
            return f"{value / 1_000_000:.2f}M"
        if abs_value >= 1_000:
            return f"{value / 1_000:.2f}K"
        if float(value).is_integer():
            return f"{int(value):,}"
        return f"{value:,.2f}"
    except Exception:
        return str(value)


def format_label(value):
    return str(value).replace("_", " ").strip()