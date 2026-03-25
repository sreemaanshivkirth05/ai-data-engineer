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
        distribution_signals = analysis.get("distribution_signals", {})

        paragraphs = []

        if target:
            paragraphs.append(
                f"This analysis is centered on {format_label(target).lower()} because it is the main metric most relevant to the business question."
            )

        if business_layer.get("direct_answer"):
            paragraphs.append(business_layer["direct_answer"])

        if target and kpis.get("total_target") is not None and kpis.get("average_target") is not None:
            paragraphs.append(
                f"At the overall level, total {format_label(target).lower()} is {format_number(kpis['total_target'])}, while the average per record is {format_number(kpis['average_target'])}. This gives a clear sense of the overall scale before comparing segments."
            )

        if top_segments:
            top = top_segments[0]
            paragraphs.append(
                f"The strongest segment-level result appears in {format_label(top['dimension']).lower()}, where {top['segment']} leads with an average {format_label(target).lower()} of {format_number(top.get('mean_target'))} across {top.get('count', 'N/A')} records."
            )

        if bottom_segments:
            bottom = bottom_segments[0]
            paragraphs.append(
                f"At the lower end, {bottom['segment']} is one of the weakest visible segments in {format_label(bottom['dimension']).lower()}, suggesting a meaningful performance gap across groups."
            )

        if correlations:
            sorted_corr = sorted(correlations.items(), key=lambda x: abs(x[1]), reverse=True)[:2]
            details = []
            for col, val in sorted_corr:
                direction = "moves in the same direction as" if val > 0 else "moves in the opposite direction to"
                details.append(f"{format_label(col)} {direction} the target (correlation: {val})")

            if details:
                paragraphs.append(
                    "The numeric analysis indicates that " + "; ".join(details) + ". These are useful directional signals for investigation, but they should not be interpreted as causal proof."
                )

        if categorical_drivers:
            sorted_cat = sorted(categorical_drivers.items(), key=lambda x: x[1], reverse=True)[:2]
            top_fields = [format_label(col) for col, _ in sorted_cat]
            if top_fields:
                paragraphs.append(
                    "The strongest group-level differences appear across " + ", ".join(top_fields) + ", which suggests that segment-level analysis is important and that performance is not evenly distributed."
                )

        if distribution_signals.get("spread_ratio") is not None:
            spread_ratio = distribution_signals["spread_ratio"]
            if spread_ratio >= 1:
                paragraphs.append(
                    "The target distribution appears relatively spread out, which suggests that performance varies significantly across the dataset rather than clustering tightly around the average."
                )

        if outlier_signals.get("outlier_count") is not None and outlier_signals.get("outlier_count", 0) > 0:
            paragraphs.append(
                f"The data also contains {outlier_signals['outlier_count']} outlier records ({format_number(outlier_signals.get('outlier_pct'))}%), so a small number of unusually high or low observations may be influencing headline metrics."
            )

        if business_layer.get("business_impact"):
            paragraphs.append(
                "From a business perspective, " + " ".join(business_layer["business_impact"])
            )

        if business_layer.get("risks_or_limitations"):
            paragraphs.append(
                "The analysis should still be read with some caution: " + " ".join(business_layer["risks_or_limitations"][:2])
            )

        paragraphs.append(
            "Taken together, the results show where performance is concentrated, where gaps exist, and which signals are most relevant for deeper investigation or next-step decisions."
        )

        return {
            "title": "Analyst Narrative",
            "summary": build_summary_line(target, kpis, business_layer, analysis),
            "paragraphs": paragraphs
        }


def build_summary_line(target, kpis, business_layer, analysis):
    if business_layer.get("executive_summary"):
        return business_layer["executive_summary"]

    top_segments = analysis.get("top_segments", [])
    if target and top_segments:
        top = top_segments[0]
        return (
            f"At a high level, the analysis is centered on {format_label(target).lower()}, "
            f"with {top['segment']} standing out as a leading segment in {format_label(top['dimension']).lower()}."
        )

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