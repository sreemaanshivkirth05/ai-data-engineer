class StorytellingAgent:
    def run(self, question, target, kpis=None, analysis=None, business_layer=None):
        kpis = kpis or {}
        analysis = analysis or {}
        business_layer = business_layer or {}

        headline = self._build_headline(question, target, kpis, analysis, business_layer)
        key_points = self._build_key_points(target, kpis, analysis, business_layer)
        business_view = self._build_business_view(question, target, kpis, analysis, business_layer)

        return {
            "title": "Data Story",
            "headline": headline,
            "key_points": key_points,
            "business_view": business_view
        }

    def _build_headline(self, question, target, kpis, analysis, business_layer):
        if business_layer.get("direct_answer"):
            return business_layer["direct_answer"]

        top_segments = analysis.get("top_segments", [])
        if top_segments:
            top = top_segments[0]
            return (
                f"{top['segment']} emerges as the strongest visible segment in "
                f"{format_label(top['dimension']).lower()} for {format_label(target).lower()}."
            )

        if kpis.get("top_dimension_value") and kpis.get("top_dimension_name"):
            return (
                f"{kpis['top_dimension_value']} stands out as the leading "
                f"{str(kpis['top_dimension_name']).lower()} in this analysis."
            )

        if target:
            return (
                f"The main story in this dataset is how {format_label(target).lower()} is distributed, "
                f"which segments lead, and which signals appear most relevant."
            )

        return "This dataset shows meaningful performance differences and a few stronger patterns worth further investigation."

    def _build_key_points(self, target, kpis, analysis, business_layer):
        points = []

        if kpis.get("total_target") is not None and target:
            points.append(f"Total {format_label(target).lower()}: {format_number(kpis['total_target'])}")

        if kpis.get("average_target") is not None and target:
            points.append(f"Average {format_label(target).lower()}: {format_number(kpis['average_target'])}")

        top_segments = analysis.get("top_segments", [])
        if top_segments:
            top = top_segments[0]
            points.append(
                f"Leading segment: {top['segment']} in {format_label(top['dimension']).lower()}"
            )

        correlations = analysis.get("correlations", {})
        if correlations:
            top_driver = sorted(correlations.items(), key=lambda x: abs(x[1]), reverse=True)[0]
            points.append(
                f"Strongest numeric signal: {format_label(top_driver[0])} (correlation: {top_driver[1]})"
            )

        outlier_signals = analysis.get("outlier_signals", {})
        if outlier_signals.get("outlier_count", 0) > 0:
            points.append(
                f"Outliers detected: {outlier_signals['outlier_count']} records"
            )

        if business_layer.get("recommended_actions"):
            points.append(f"Suggested next step: {business_layer['recommended_actions'][0]}")

        return points[:5]

    def _build_business_view(self, question, target, kpis, analysis, business_layer):
        lines = []

        if business_layer.get("executive_summary"):
            lines.append(business_layer["executive_summary"])

        if target:
            lines.append(
                f"The question is ultimately about how {format_label(target).lower()} behaves across the dataset and what that means from a decision-making perspective."
            )

        top_segments = analysis.get("top_segments", [])
        bottom_segments = analysis.get("bottom_segments", [])

        if top_segments:
            top = top_segments[0]
            lines.append(
                f"The clearest positive signal is that {top['segment']} leads within {format_label(top['dimension']).lower()}, making it a useful benchmark when comparing the rest of the dataset."
            )

        if bottom_segments:
            bottom = bottom_segments[0]
            lines.append(
                f"At the same time, weaker segments such as {bottom['segment']} indicate that performance is uneven and that not all groups are contributing equally."
            )

        correlations = analysis.get("correlations", {})
        if correlations:
            col, val = sorted(correlations.items(), key=lambda x: abs(x[1]), reverse=True)[0]
            relation = "moves with" if val > 0 else "moves opposite to"
            lines.append(
                f"Among the numeric fields, {format_label(col)} is the strongest measurable signal and {relation} the target metric. This should be treated as directional evidence rather than causal proof."
            )

        categorical_drivers = analysis.get("categorical_drivers", {})
        if categorical_drivers:
            top_cat = sorted(categorical_drivers.items(), key=lambda x: x[1], reverse=True)[0][0]
            lines.append(
                f"There is also clear variation across {format_label(top_cat).lower()}, which suggests that broad averages alone may hide meaningful segment-level differences."
            )

        if business_layer.get("business_impact"):
            lines.extend(business_layer["business_impact"][:2])

        if business_layer.get("risks_or_limitations"):
            lines.append(
                "This output is best used for prioritization and business direction, while keeping the stated data limitations in mind before making high-stakes decisions."
            )

        return lines


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