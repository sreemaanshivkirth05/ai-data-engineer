class NarrativeAgent:

    def run(self, question, analysis, kpis=None, target=None):
        kpis = kpis or {}
        correlations = analysis.get("correlations", {})
        categorical_drivers = analysis.get("categorical_drivers", {})

        paragraphs = []

        # opening
        if target:
            paragraphs.append(
                f"This analysis focuses on {target} because it is the main metric most relevant to your question."
            )

        if kpis.get("total_target") is not None and kpis.get("average_target") is not None:
            paragraphs.append(
                f"Across the analyzed dataset, the total {target.lower()} is {format_number(kpis['total_target'])}, and the average {target.lower()} per record is {format_number(kpis['average_target'])}. These summary metrics help establish the overall scale of the dataset before looking at patterns in more detail."
            )

        # top contributor
        if kpis.get("top_dimension_name") and kpis.get("top_dimension_value"):
            dim_name = str(kpis["top_dimension_name"]).lower()
            dim_value = str(kpis["top_dimension_value"])
            dim_metric = format_number(kpis.get("top_dimension_metric"))

            paragraphs.append(
                f"The strongest contributor in this analysis is {dim_value} within {dim_name}. It contributes {dim_metric}, making it the leading segment relative to the target metric."
            )

        # numeric relationships
        if correlations:
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
                    details.append(f"{col} {direction} the target (correlation: {val})")

                paragraphs.append(
                    "The strongest numeric signals suggest that " + "; ".join(details) + ". This helps identify which quantitative factors may be most closely associated with performance."
                )

        # categorical differences
        if categorical_drivers:
            sorted_cat = sorted(
                categorical_drivers.items(),
                key=lambda x: x[1],
                reverse=True
            )
            top_fields = [col for col, _ in sorted_cat[:2]]

            if top_fields:
                paragraphs.append(
                    "The most meaningful categorical differences appear across " + ", ".join(top_fields) + ". This means performance is not distributed evenly, and some groups stand out more clearly than others."
                )

        # closing interpretation
        paragraphs.append(
            "Taken together, these results suggest that the dataset has a few clearly leading groups, some meaningful variation across categories, and a limited number of factors that are most important when explaining the target metric."
        )

        return {
            "title": "Analyst Narrative",
            "summary": build_summary_line(target, kpis),
            "paragraphs": paragraphs
        }


def build_summary_line(target, kpis):
    if target and kpis.get("top_dimension_value") and kpis.get("top_dimension_name"):
        return (
            f"At a high level, the leading {str(kpis['top_dimension_name']).lower()} "
            f"is {kpis['top_dimension_value']}, and the analysis is centered on {target.lower()}."
        )
    if target:
        return f"At a high level, this analysis is centered on {target.lower()}."
    return "At a high level, the dataset was analyzed successfully."


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