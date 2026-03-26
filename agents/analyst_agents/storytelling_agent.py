class StorytellingAgent:

    def run(self, question, target, kpis=None, analysis=None, business_layer=None):
        kpis = kpis or {}
        analysis = analysis or {}
        business_layer = business_layer or {}

        analysis_metadata = analysis.get("analysis_metadata", {}) or {}
        intent = analysis_metadata.get("intent") or infer_intent_from_analysis(analysis)

        headline = self._build_headline(question, target, kpis, analysis, business_layer, intent)
        key_points = self._build_key_points(target, kpis, analysis, business_layer, intent)
        business_view = self._build_business_view(question, target, kpis, analysis, business_layer, intent)

        return {
            "title": "Data Story",
            "headline": headline,
            "key_points": key_points,
            "business_view": business_view
        }

    def _build_headline(self, question, target, kpis, analysis, business_layer, intent):
        time_summary = analysis.get("time_summary", {}) or {}
        top_segments = analysis.get("top_segments", []) or []
        correlations = analysis.get("correlations", {}) or {}

        if business_layer.get("direct_answer"):
            return business_layer["direct_answer"]

        if intent == "trend_analysis" and time_summary:
            first_period = time_summary.get("first_period")
            last_period = time_summary.get("last_period")
            change_pct = time_summary.get("change_pct")

            if first_period and last_period and change_pct is not None:
                direction = "grew" if change_pct >= 0 else "declined"
                return (
                    f"{format_label(target)} {direction} by {abs(change_pct):.1f}% from {first_period} to {last_period}."
                )

        if top_segments:
            best = top_segments[0]
            return (
                f"{best['segment']} stands out as the leading "
                f"{format_label(best['dimension']).lower()} in this analysis."
            )

        if kpis.get("top_dimension_value") and kpis.get("top_dimension_name"):
            return (
                f"{kpis['top_dimension_value']} stands out as the leading "
                f"{str(kpis['top_dimension_name']).lower()} in this analysis."
            )

        if intent == "relationship_analysis" and correlations:
            top_corr = sorted(correlations.items(), key=lambda x: abs(x[1]), reverse=True)[0]
            return (
                f"{format_label(top_corr[0])} emerges as the strongest measurable signal associated with {format_label(target).lower()}."
            )

        if target:
            return f"The story in this dataset is mainly about how {format_label(target).lower()} is distributed, what drives it, and where the strongest performance is concentrated."

        return "This dataset reveals a mix of group-level differences, overall scale, and a few stronger signals that stand out."

    def _build_key_points(self, target, kpis, analysis, business_layer, intent):
        points = []

        time_summary = analysis.get("time_summary", {}) or {}
        correlations = analysis.get("correlations", {}) or {}
        categorical_drivers = analysis.get("categorical_drivers", {}) or {}
        outlier_summary = analysis.get("outlier_summary", {}) or {}
        top_segments = analysis.get("top_segments", []) or []

        if kpis.get("total_target") is not None and target:
            points.append(f"Total {format_label(target).lower()}: {format_number(kpis['total_target'])}")

        if kpis.get("average_target") is not None and target:
            points.append(f"Average {format_label(target).lower()}: {format_number(kpis['average_target'])}")

        if intent == "trend_analysis" and time_summary:
            if time_summary.get("best_period"):
                points.append(f"Best period: {time_summary['best_period']}")
            if time_summary.get("worst_period"):
                points.append(f"Weakest period: {time_summary['worst_period']}")
            if time_summary.get("change_pct") is not None:
                points.append(f"Overall period change: {abs(time_summary['change_pct']):.1f}%")

        if top_segments:
            best = top_segments[0]
            points.append(
                f"Leading {format_label(best['dimension']).lower()}: {best['segment']}"
            )
        elif kpis.get("top_dimension_name") and kpis.get("top_dimension_value"):
            points.append(
                f"Leading {str(kpis['top_dimension_name']).lower()}: {kpis['top_dimension_value']}"
            )

        if correlations:
            sorted_corr = sorted(correlations.items(), key=lambda x: abs(x[1]), reverse=True)
            top_driver = sorted_corr[0]
            points.append(f"Strongest numeric signal: {format_label(top_driver[0])} (correlation: {top_driver[1]})")

        if categorical_drivers:
            sorted_cat = sorted(categorical_drivers.items(), key=lambda x: x[1], reverse=True)
            points.append(f"Most meaningful group variation: {format_label(sorted_cat[0][0])}")

        if outlier_summary.get("outlier_count", 0) > 0:
            points.append(f"Detected outliers: {outlier_summary.get('outlier_count', 0)}")

        if business_layer.get("recommended_actions"):
            points.append(f"Suggested next step: {business_layer['recommended_actions'][0]}")

        return points[:6]

    def _build_business_view(self, question, target, kpis, analysis, business_layer, intent):
        lines = []

        time_summary = analysis.get("time_summary", {}) or {}
        correlations = analysis.get("correlations", {}) or {}
        categorical_drivers = analysis.get("categorical_drivers", {}) or {}
        top_segments = analysis.get("top_segments", []) or []
        distribution_summary = analysis.get("distribution_summary", {}) or {}
        outlier_summary = analysis.get("outlier_summary", {}) or {}

        if business_layer.get("executive_summary"):
            lines.append(business_layer["executive_summary"])

        lines.append(
            f"Your question asks for a business interpretation of {format_label(target).lower()} in the context of the broader dataset. To answer that, the analysis looks at overall scale, identifies the strongest segments, and checks for measurable supporting signals."
        )

        if intent == "trend_analysis" and time_summary:
            first_period = time_summary.get("first_period")
            last_period = time_summary.get("last_period")
            change_pct = time_summary.get("change_pct")
            best_period = time_summary.get("best_period")

            if first_period and last_period and change_pct is not None:
                direction = "grew" if change_pct >= 0 else "declined"
                lines.append(
                    f"Across the observed time range, {format_label(target).lower()} {direction} by {abs(change_pct):.1f}% from {first_period} to {last_period}. This gives the analysis a clear time-based story rather than just a static snapshot."
                )

            if best_period:
                lines.append(
                    f"The strongest period was {best_period}, which acts as a natural benchmark for comparing weaker periods and understanding what good performance looks like."
                )

        if top_segments:
            best = top_segments[0]
            lines.append(
                f"The clearest result is that {best['segment']} is the leading {format_label(best['dimension']).lower()}. This makes it the strongest visible contributor in the dataset and a useful benchmark when comparing the rest of the groups."
            )

        elif kpis.get("top_dimension_name") and kpis.get("top_dimension_value"):
            lines.append(
                f"The clearest result is that {kpis['top_dimension_value']} is the leading {str(kpis['top_dimension_name']).lower()}. This makes it the strongest visible contributor in the dataset and a useful benchmark when comparing the rest of the groups."
            )

        if correlations and intent != "trend_analysis":
            sorted_corr = sorted(correlations.items(), key=lambda x: abs(x[1]), reverse=True)
            col, val = sorted_corr[0]
            relation = "moves with" if val > 0 else "moves opposite to"
            lines.append(
                f"Among the numeric fields, {format_label(col).lower()} is the strongest measurable signal and {relation} the target metric. While this does not prove causation, it gives a useful direction for deeper investigation."
            )

        if categorical_drivers:
            sorted_cat = sorted(categorical_drivers.items(), key=lambda x: x[1], reverse=True)
            top_cat = sorted_cat[0][0]
            lines.append(
                f"There is also meaningful variation across {format_label(top_cat).lower()}, which suggests that performance is not uniform across the dataset. Some segments stand out more clearly than others."
            )

        if distribution_summary:
            mean_val = distribution_summary.get("mean")
            median_val = distribution_summary.get("median")
            if mean_val is not None and median_val is not None:
                lines.append(
                    f"The metric’s distribution also matters: with a mean of {format_number(mean_val)} and a median of {format_number(median_val)}, the result should be read in terms of spread and concentration, not just totals."
                )

        if outlier_summary.get("outlier_count", 0) > 0:
            lines.append(
                f"A further caution is that {outlier_summary.get('outlier_count', 0)} outliers were detected, so unusually high or low records may be influencing the averages or totals."
            )

        if business_layer.get("business_impact"):
            lines.extend(business_layer["business_impact"][:2])

        if business_layer.get("risks_or_limitations"):
            lines.append(
                "A final caution is that this output is best used for decision support and prioritization, with limitations kept in mind before making high-stakes decisions."
            )

        return lines


def infer_intent_from_analysis(analysis):
    if analysis.get("time_summary"):
        return "trend_analysis"
    if analysis.get("correlations"):
        return "relationship_analysis"
    if analysis.get("distribution_summary"):
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