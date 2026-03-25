class NarrativeAgent:
    def run(self, question, analysis, kpis=None, target=None, business_layer=None):
        kpis = kpis or {}
        analysis = analysis or {}
        business_layer = business_layer or {}

        correlations = analysis.get("correlations", {})
        categorical_drivers = analysis.get("categorical_drivers", {})
        target_summary = analysis.get("target_summary", {})
        top_segments = analysis.get("top_segments", [])
        bottom_segments = analysis.get("bottom_segments", [])
        outlier_signals = analysis.get("outlier_signals", {})

        paragraphs = []

        if target:
            paragraphs.append(
                f"This analysis is centered on {format_label(target).lower()} because it is the primary metric most relevant to the business question."
            )

        if business_layer.get("direct_answer"):
            paragraphs.append(business_layer["direct_answer"])

        if target_summary:
            mean_value = format_number(target_summary.get("mean"))
            median_value = format_number(target_summary.get("median"))
            min_value = format_number(target_summary.get("min"))
            max_value = format_number(target_summary.get("max"))

            paragraphs.append(
                f"At the overall level, the distribution of {format_label(target).lower()} shows an average of {mean_value}, a median of {median_value}, and a range from {min_value} to {max_value}. This helps establish the scale and spread of the metric before looking at segment-level differences."
            )

        elif kpis.get("total_target") is not None and kpis.get("average_target") is not None and target:
            paragraphs.append(
                f"At the overall level, total {format_label(target).lower()} is {format_number(kpis['total_target'])}, while the average per record is {format_number(kpis['average_target'])}. This gives a useful sense of scale before looking at which groups are driving the result."
            )

        if top_segments:
            top = top_segments[0]
            paragraphs.append(
                f"The strongest visible segment is {top['segment']} within {format_label(top['dimension']).lower()}, with an average {format_label(target).lower()} of {format_number(top.get('mean_target'))} and a total contribution of {format_number(top.get('total_target'))}. This makes it a strong benchmark against the rest of the dataset."
            )

        elif kpis.get("top_dimension_name") and kpis.get("top_dimension_value"):
            dim_name = str(kpis["top_dimension_name"]).lower()
            dim_value = str(kpis["top_dimension_value"])
            dim_metric = format_number(kpis.get("top_dimension_metric"))

            paragraphs.append(
                f"The strongest visible segment is {dim_value} within {dim_name}, contributing {dim_metric}. This makes it the clearest benchmark when comparing performance across the rest of the dataset."
            )

        if bottom_segments:
            bottom = bottom_segments[0]
            paragraphs.append(
                f"At the lower end, {bottom['segment']} within {format_label(bottom['dimension']).lower()} appears weaker, which suggests that performance is not evenly distributed and that some groups may need closer investigation."
            )

        if correlations:
            sorted_corr = sorted(
                correlations.items(),
                key=lambda x: abs(x[1]),
                reverse=True
            )[:2]

            details = []
            for col, val in sorted_corr:
                direction = "moves in the same direction as" if val > 0 else "moves in the opposite direction to"
                details.append(f"{format_label(col)} {direction} the target (correlation: {val})")

            if details:
                paragraphs.append(
                    "The numeric analysis suggests that " + "; ".join(details) + ". These are useful directional signals for deeper investigation, even though they should not be treated as proof of causation."
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
                    "The most meaningful group-level differences appear across " + ", ".join(top_fields) + ". This indicates that segment-level analysis is important and that overall averages alone may hide important variation."
                )

        if outlier_signals and outlier_signals.get("outlier_count"):
            paragraphs.append(
                f"The target also shows {outlier_signals['outlier_count']} outlier values ({outlier_signals.get('outlier_pct', 0)}% of usable records), which means some extreme observations may be influencing the overall pattern."
            )

        if business_layer.get("business_impact"):
            paragraphs.append(
                "From a business perspective, " + " ".join(business_layer["business_impact"])
            )

        if business_layer.get("risks_or_limitations"):
            paragraphs.append(
                "This analysis should still be read with context: " + " ".join(business_layer["risks_or_limitations"][:2])
            )

        paragraphs.append(
            "Taken together, the results show not just what is happening in the dataset, but where performance is concentrated, which segments stand out, and where further action or deeper analysis would be most useful."
        )

        return {
            "title": "Analyst Narrative",
            "summary": build_summary_line(target, kpis, business_layer),
            "paragraphs": paragraphs
        }


def build_summary_line(target, kpis, business_layer):
    if business_layer.get("executive_summary"):
        return business_layer["executive_summary"]

    if target and kpis.get("top_dimension_value") and kpis.get("top_dimension_name"):
        return (
            f"At a high level, the leading {str(kpis['top_dimension_name']).lower()} "
            f"is {kpis['top_dimension_value']}, and the analysis is centered on {format_label(target).lower()}."
        )

    if target:
        return f"At a high level, this analysis is centered on {format_label(target).lower()}."

    return "At a high level, the dataset was analyzed successfully."


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