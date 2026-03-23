class StorytellingAgent:

    def run(self, question, target, kpis=None, analysis=None):
        kpis = kpis or {}
        analysis = analysis or {}

        headline = self._build_headline(question, target, kpis)
        key_points = self._build_key_points(target, kpis, analysis)
        business_view = self._build_business_view(question, target, kpis, analysis)

        return {
            "title": "Data Story",
            "headline": headline,
            "key_points": key_points,
            "business_view": business_view
        }

    def _build_headline(self, question, target, kpis):
        if kpis.get("top_dimension_value") and kpis.get("top_dimension_name"):
            return (
                f"{kpis['top_dimension_value']} stands out as the leading "
                f"{str(kpis['top_dimension_name']).lower()} in this analysis."
            )

        if target:
            return f"The story in this dataset is mainly about how {target.lower()} is distributed, what drives it, and where the strongest performance is concentrated."

        return "This dataset reveals a mix of group-level differences, overall scale, and a few stronger signals that stand out."

    def _build_key_points(self, target, kpis, analysis):
        points = []

        if kpis.get("total_target") is not None:
            points.append(f"Total {target.lower()}: {format_number(kpis['total_target'])}")

        if kpis.get("average_target") is not None:
            points.append(f"Average {target.lower()}: {format_number(kpis['average_target'])}")

        if kpis.get("top_dimension_name") and kpis.get("top_dimension_value"):
            points.append(
                f"Leading {str(kpis['top_dimension_name']).lower()}: {kpis['top_dimension_value']}"
            )

        correlations = analysis.get("correlations", {})
        if correlations:
            sorted_corr = sorted(correlations.items(), key=lambda x: abs(x[1]), reverse=True)
            top_driver = sorted_corr[0]
            points.append(f"Strongest numeric signal: {top_driver[0]} (correlation: {top_driver[1]})")

        categorical_drivers = analysis.get("categorical_drivers", {})
        if categorical_drivers:
            sorted_cat = sorted(categorical_drivers.items(), key=lambda x: x[1], reverse=True)
            points.append(f"Most meaningful group variation: {sorted_cat[0][0]}")

        return points

    def _build_business_view(self, question, target, kpis, analysis):
        lines = []

        lines.append(
            f"Your question asks for an explanation of {target.lower()} in the context of the broader dataset. To answer that, the analysis first looks at the overall size of the metric, then identifies which groups contribute the most, and finally checks whether any numeric signals appear to move with the target."
        )

        if kpis.get("top_dimension_name") and kpis.get("top_dimension_value"):
            lines.append(
                f"The clearest result is that {kpis['top_dimension_value']} is the leading {str(kpis['top_dimension_name']).lower()}. This makes it the strongest visible contributor in the dataset and a useful benchmark when comparing the rest of the groups."
            )

        correlations = analysis.get("correlations", {})
        if correlations:
            sorted_corr = sorted(correlations.items(), key=lambda x: abs(x[1]), reverse=True)
            col, val = sorted_corr[0]
            relation = "moves with" if val > 0 else "moves opposite to"
            lines.append(
                f"Among the numeric fields, {col} is the strongest measurable signal and {relation} the target metric. While this does not automatically prove causation, it gives the user a strong direction for deeper investigation."
            )

        categorical_drivers = analysis.get("categorical_drivers", {})
        if categorical_drivers:
            sorted_cat = sorted(categorical_drivers.items(), key=lambda x: x[1], reverse=True)
            top_cat = sorted_cat[0][0]
            lines.append(
                f"There is also meaningful variation across {top_cat}, which suggests that performance is not uniform across the dataset. Some segments stand out much more than others and likely explain a large share of the overall result."
            )

        lines.append(
            "In practical terms, the charts and KPIs together show where performance is concentrated, how it changes over time, how it is distributed across important business categories, and which signals are most closely associated with the target. This makes the dataset easier to understand for both analysts and business users."
        )

        return lines


def format_number(value):
    if value is None:
        return "N/A"
    try:
        value = float(value)
        if abs(value) >= 1000:
            return f"{value:,.2f}"
        return f"{value:.2f}"
    except Exception:
        return str(value)