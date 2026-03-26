import os
import pandas as pd

from agents.analyst_agents.question_agent import QuestionAgent
from agents.analyst_agents.planner_agent import PlannerAgent
from agents.analyst_agents.analysis_agent import AnalysisAgent
from agents.analyst_agents.visualization_agent import VisualizationAgent
from agents.analyst_agents.narrative_agent import NarrativeAgent
from agents.analyst_agents.storytelling_agent import StorytellingAgent
from agents.analyst_agents.kpi_agent import KPIAgent

from analyst_runtime.phase1_product_layer import build_phase1_product_layer


def run_analysis_pipeline(dataset_path, question):
    print("🚀 ANALYSIS PIPELINE STARTED")
    print(f"📂 Loading dataset: {dataset_path}")

    os.makedirs("outputs/analyst/charts", exist_ok=True)

    if dataset_path.endswith(".csv"):
        df = pd.read_csv(dataset_path)
    elif dataset_path.endswith(".xlsx"):
        df = pd.read_excel(dataset_path)
    else:
        raise ValueError("Unsupported dataset format")

    if not isinstance(df, pd.DataFrame):
        raise ValueError("Dataset failed to load")

    print(f"✅ Dataset loaded — {len(df):,} rows × {len(df.columns)} columns")

    df = preprocess_dataframe(df)
    columns = df.columns.tolist()

    print(f"✅ Preprocessing complete — columns: {columns}")

    print("🧠 Running QuestionAgent")
    question_agent = QuestionAgent()
    question_info = question_agent.run(question)

    fallback_intent = question_info["intent"]
    show_kpis = question_info.get("show_kpis", False)
    question_category = question_info.get("question_category", "general")
    question_goal = question_info.get(
        "question_goal",
        "Understand the most important pattern in the dataset."
    )

    print(f"✅ Fallback intent: {fallback_intent} | Show KPIs: {show_kpis}")

    print("📊 Running PlannerAgent")
    planner = PlannerAgent()
    plan = planner.run(question, columns)

    target = plan.get("target")
    drivers = plan.get("drivers", [])
    planner_intent = plan.get("analysis_type")
    time_column = plan.get("time_column")
    aggregation = plan.get("aggregation", "none")
    preferred_chart = plan.get("chart", "table")
    planner_reasoning = plan.get("reasoning", {}) or {}

    intent = normalize_intent(planner_intent or fallback_intent)
    question_category = normalize_question_category(intent, question_category)

    numeric_cols = df.select_dtypes(include=["int64", "float64", "int32", "float32"]).columns.tolist()

    if target is None or target not in columns:
        if numeric_cols:
            target = numeric_cols[0]
        else:
            target = columns[-1]

    if time_column and time_column not in columns:
        time_column = None

    print(
        f"✅ Target: {target} | Drivers: {drivers} | "
        f"Intent: {intent} | Time column: {time_column} | "
        f"Aggregation: {aggregation} | Preferred chart: {preferred_chart}"
    )

    print("📌 Running KPIAgent")
    kpis = {}
    if show_kpis:
        try:
            kpi_agent = KPIAgent()
            try:
                kpis = kpi_agent.run(
                    df,
                    target,
                    time_column=time_column,
                    aggregation=aggregation,
                    drivers=drivers
)
            except TypeError:
                kpis = kpi_agent.run(df, target)
        except Exception as e:
            print(f"⚠️ KPIAgent failed: {e}")
            kpis = {}

    print("✅ KPIs done")

    print("📈 Running AnalysisAgent")
    analysis_results = {}
    try:
        analysis_agent = AnalysisAgent()
        try:
            analysis_results = analysis_agent.run(
                df=df,
                target=target,
                drivers=drivers,
                intent=intent,
                time_column=time_column,
                aggregation=aggregation
            )
        except TypeError:
            analysis_results = analysis_agent.run(df, target)
    except Exception as e:
        print(f"⚠️ AnalysisAgent failed: {e}")
        analysis_results = {
            "correlations": {},
            "categorical_drivers": {},
            "time_summary": {},
            "top_segments": [],
            "bottom_segments": [],
            "distribution_summary": {},
            "outlier_summary": {}
        }

    print("✅ Statistical analysis done")

    print("📊 Running VisualizationAgent")
    charts = []
    try:
        viz_agent = VisualizationAgent()
        try:
            charts = viz_agent.run(
                df=df,
                target=target,
                question=question,
                intent=intent,
                drivers=drivers,
                time_column=time_column,
                aggregation=aggregation,
                preferred_chart=preferred_chart,
                plan=plan
            )
        except TypeError:
            charts = viz_agent.run(
                df=df,
                target=target,
                question=question,
                intent=intent,
                drivers=drivers
            )
    except Exception as e:
        print(f"⚠️ VisualizationAgent failed: {e}")
        charts = []

    print(f"✅ {len(charts)} chart(s) generated")

    print("💼 Building decision-support layer")
    business_layer = build_business_layer(
        df=df,
        question=question,
        intent=intent,
        question_category=question_category,
        question_goal=question_goal,
        target=target,
        drivers=drivers,
        kpis=kpis,
        analysis=analysis_results,
        charts=charts,
        plan=plan
    )
    print("✅ Decision-support layer done")

    print("🧩 Building Phase 1 product layer")
    phase1 = build_phase1_product_layer(
        df=df,
        question=question,
        intent=intent,
        target=target,
        drivers=drivers,
        kpis=kpis,
        analysis=analysis_results,
        charts=charts,
        question_category=question_category,
        question_goal=question_goal
    )
    print("✅ Phase 1 product layer done")

    print("📝 Running NarrativeAgent")
    narrative = None
    try:
        narrative_agent = NarrativeAgent()
        try:
            narrative = narrative_agent.run(
                question=question,
                analysis=analysis_results,
                kpis=kpis,
                target=target,
                business_layer=business_layer
            )
        except TypeError:
            narrative = narrative_agent.run(
                question=question,
                analysis=analysis_results,
                kpis=kpis,
                target=target
            )
    except Exception as e:
        print(f"⚠️ NarrativeAgent failed: {e}")
        narrative = {
            "title": "Analyst Narrative",
            "summary": "A narrative could not be generated for this analysis.",
            "paragraphs": []
        }

    print("✅ Narrative done")

    print("📚 Running StorytellingAgent")
    story = None
    try:
        storytelling_agent = StorytellingAgent()
        try:
            story = storytelling_agent.run(
                question=question,
                target=target,
                kpis=kpis,
                analysis=analysis_results,
                business_layer=business_layer
            )
        except TypeError:
            story = storytelling_agent.run(
                question=question,
                target=target,
                kpis=kpis,
                analysis=analysis_results
            )
    except Exception as e:
        print(f"⚠️ StorytellingAgent failed: {e}")
        story = {
            "title": "Data Story",
            "headline": "A data story could not be generated for this analysis.",
            "key_points": [],
            "business_view": []
        }

    print("✅ Story done")
    print("🎉 ANALYSIS PIPELINE COMPLETE")

    return {
        "question": question,
        "intent": intent,
        "question_category": question_category,
        "question_goal": question_goal,
        "show_kpis": show_kpis,
        "target": target,
        "drivers": drivers,
        "plan": plan,
        "time_column": time_column,
        "aggregation": aggregation,
        "preferred_chart": preferred_chart,
        "planner_reasoning": planner_reasoning,
        "kpis": kpis,
        "analysis": analysis_results,
        "charts": charts,
        "executive_summary": business_layer["executive_summary"],
        "direct_answer": business_layer["direct_answer"],
        "business_impact": business_layer["business_impact"],
        "recommended_actions": business_layer["recommended_actions"],
        "risks_or_limitations": business_layer["risks_or_limitations"],
        "dataset_summary": phase1["dataset_summary"],
        "top_insights": phase1["top_insights"],
        "follow_up_questions": phase1["follow_up_questions"],
        "data_quality_summary": phase1["data_quality_summary"],
        "narrative": narrative,
        "story": story
    }


def build_business_layer(
    df,
    question,
    intent,
    question_category,
    question_goal,
    target,
    drivers,
    kpis,
    analysis,
    charts,
    plan=None
):
    executive_summary = build_executive_summary(
        question=question,
        question_goal=question_goal,
        target=target,
        kpis=kpis,
        analysis=analysis,
        intent=intent
    )

    direct_answer = build_direct_answer(
        question=question,
        intent=intent,
        target=target,
        kpis=kpis,
        analysis=analysis
    )

    business_impact = build_business_impact(
        target=target,
        kpis=kpis,
        analysis=analysis,
        charts=charts,
        intent=intent
    )

    recommended_actions = build_recommended_actions(
        intent=intent,
        target=target,
        kpis=kpis,
        analysis=analysis
    )

    risks_or_limitations = build_risks_and_limitations(
        df=df,
        intent=intent,
        target=target,
        drivers=drivers,
        analysis=analysis,
        plan=plan
    )

    return {
        "executive_summary": executive_summary,
        "direct_answer": direct_answer,
        "business_impact": business_impact,
        "recommended_actions": recommended_actions,
        "risks_or_limitations": risks_or_limitations
    }


def build_executive_summary(question, question_goal, target, kpis, analysis, intent):
    parts = []
    time_summary = analysis.get("time_summary", {}) or {}
    top_segments = analysis.get("top_segments", []) or []
    correlations = analysis.get("correlations", {}) or {}

    if target:
        parts.append(
            f"This analysis is centered on {format_label(target).lower()} as the primary business metric."
        )

    if question_goal:
        parts.append(question_goal)

    if intent == "trend_analysis" and time_summary:
        first_period = time_summary.get("first_period")
        last_period = time_summary.get("last_period")
        change_pct = time_summary.get("change_pct")
        best_period = time_summary.get("best_period")

        if first_period and last_period and change_pct is not None:
            direction = "increased" if change_pct >= 0 else "decreased"
            parts.append(
                f"{format_label(target)} {direction} by {abs(change_pct):.1f}% from {first_period} to {last_period}."
            )

        if best_period:
            parts.append(f"The strongest observed period was {best_period}.")

    elif top_segments:
        best = top_segments[0]
        parts.append(
            f"The clearest visible leader is {best['segment']} within {format_label(best['dimension']).lower()}."
        )

    elif kpis.get("top_dimension_name") and kpis.get("top_dimension_value"):
        dim_name = str(kpis["top_dimension_name"]).lower()
        dim_value = str(kpis["top_dimension_value"])
        dim_metric = format_number(kpis.get("top_dimension_metric"))
        parts.append(
            f"The clearest visible leader is {dim_value} within {dim_name}, contributing {dim_metric}."
        )

    if correlations and intent != "trend_analysis":
        top_corr = sorted(correlations.items(), key=lambda x: abs(x[1]), reverse=True)[0]
        relation = "moves with" if top_corr[1] > 0 else "moves opposite to"
        parts.append(
            f"{format_label(top_corr[0]).lower()} is the strongest measurable numeric signal and {relation} the target metric."
        )

    if not parts:
        parts.append(
            "The dataset was analyzed successfully and the strongest visible patterns were summarized into visuals and business interpretation."
        )

    return " ".join(parts)


def build_direct_answer(question, intent, target, kpis, analysis):
    time_summary = analysis.get("time_summary", {}) or {}
    top_segments = analysis.get("top_segments", []) or []
    correlations = analysis.get("correlations", {}) or {}

    if intent == "trend_analysis" and time_summary:
        first_period = time_summary.get("first_period")
        last_period = time_summary.get("last_period")
        first_value = time_summary.get("first_value")
        last_value = time_summary.get("last_value")
        change_pct = time_summary.get("change_pct")
        best_period = time_summary.get("best_period")
        best_period_value = time_summary.get("best_period_value")

        if first_period and last_period and first_value is not None and last_value is not None:
            change_text = ""
            if change_pct is not None:
                direction = "up" if change_pct >= 0 else "down"
                change_text = f", moving {direction} by {abs(change_pct):.1f}% overall"

            best_period_text = ""
            if best_period and best_period_value is not None:
                best_period_text = f" The strongest period was {best_period} at {format_number(best_period_value)}."

            return (
                f"{format_label(target)} changed from {format_number(first_value)} in {first_period} "
                f"to {format_number(last_value)} in {last_period}{change_text}.{best_period_text}"
            )

    if intent == "relationship_analysis" and correlations:
        top_corr = sorted(correlations.items(), key=lambda x: abs(x[1]), reverse=True)[0]
        direction = "positively associated with" if top_corr[1] > 0 else "negatively associated with"
        return (
            f"The strongest numeric relationship is that {format_label(top_corr[0]).lower()} is "
            f"{direction} {format_label(target).lower()} with a correlation of {top_corr[1]}."
        )

    if top_segments:
        best = top_segments[0]
        return (
            f"The clearest answer is that {best['segment']} is currently the leading "
            f"{format_label(best['dimension']).lower()} for {format_label(target).lower()}, "
            f"with a measured contribution of {format_number(best.get('total_target'))}."
        )

    if kpis.get("top_dimension_name") and kpis.get("top_dimension_value"):
        metric = format_number(kpis.get("top_dimension_metric"))
        return (
            f"The clearest answer is that {kpis['top_dimension_value']} is currently the leading "
            f"{str(kpis['top_dimension_name']).lower()} for {format_label(target).lower()}, "
            f"with a measured contribution of {metric}."
        )

    if target:
        return (
            f"The answer is centered on {format_label(target).lower()}, with the visuals showing where performance is concentrated, how it differs across groups, and which signals matter most."
        )

    return "The analysis completed successfully, but the answer could not be narrowed to a single target metric."


def build_business_impact(target, kpis, analysis, charts, intent):
    lines = []
    top_segments = analysis.get("top_segments", []) or []
    categorical_drivers = analysis.get("categorical_drivers", {}) or {}
    time_summary = analysis.get("time_summary", {}) or {}

    if intent == "trend_analysis" and time_summary:
        change_pct = time_summary.get("change_pct")
        best_period = time_summary.get("best_period")
        if change_pct is not None:
            direction = "growth" if change_pct >= 0 else "decline"
            lines.append(
                f"The time pattern shows overall {direction} in {format_label(target).lower()}, which is important for planning, forecasting, and performance monitoring."
            )
        if best_period:
            lines.append(
                f"{best_period} stands out as the strongest period and can be used as a benchmark when comparing weaker periods."
            )

    elif top_segments:
        best = top_segments[0]
        lines.append(
            f"Performance is not evenly distributed: {best['segment']} is a strong benchmark segment that can be compared against weaker groups."
        )

    elif kpis.get("top_dimension_name") and kpis.get("top_dimension_value"):
        lines.append(
            f"Performance is not evenly distributed: {kpis['top_dimension_value']} is a strong benchmark segment that can be compared against weaker groups."
        )

    if categorical_drivers and intent != "trend_analysis":
        top_cat = sorted(categorical_drivers.items(), key=lambda x: x[1], reverse=True)[0][0]
        lines.append(
            f"The variation across {format_label(top_cat).lower()} suggests that segment-level decisions will likely be more useful than one-size-fits-all actions."
        )

    if charts and len(charts) >= 4:
        lines.append(
            "The visual set combines a primary answer chart, supporting breakdowns, and a diagnostic view, which gives better decision support than a single chart alone."
        )

    if target and not lines:
        lines.append(
            f"{format_label(target)} should be monitored through both overall scale and segment-level differences, not just headline totals."
        )

    return lines


def build_recommended_actions(intent, target, kpis, analysis):
    actions = []
    time_summary = analysis.get("time_summary", {}) or {}
    correlations = analysis.get("correlations", {}) or {}

    if intent == "trend_analysis":
        actions.append(
            "Review the time-based chart to determine whether the pattern is stable, improving, or driven by a limited number of spikes."
        )
        if time_summary.get("best_period") and time_summary.get("worst_period"):
            actions.append(
                f"Compare {time_summary['best_period']} and {time_summary['worst_period']} to understand what drove the performance gap across periods."
            )

    if kpis.get("top_dimension_name") and kpis.get("top_dimension_value") and intent != "trend_analysis":
        actions.append(
            f"Use {kpis['top_dimension_value']} as a benchmark segment and compare the rest of the groups against it."
        )

    if intent == "comparison":
        actions.append(
            "Investigate why the highest-performing groups are ahead and test whether those conditions can be replicated in weaker segments."
        )

    if correlations and intent != "trend_analysis":
        top_corr = sorted(correlations.items(), key=lambda x: abs(x[1]), reverse=True)[0]
        actions.append(
            f"Investigate {format_label(top_corr[0]).lower()} further as a potential driver of {format_label(target).lower()}, while treating the current result as directional rather than causal."
        )

    if not actions:
        actions.append(
            f"Use the primary chart to validate the main answer, then use the supporting visuals to check which dimensions explain differences in {format_label(target).lower()}."
        )

    return actions[:4]


def build_risks_and_limitations(df, intent, target, drivers, analysis, plan=None):
    risks = []

    if target not in df.columns:
        risks.append("The selected target metric could not be validated cleanly against the dataset columns.")

    if target in df.columns:
        target_null_pct = round(float(df[target].isna().mean() * 100), 1)
        if target_null_pct > 0:
            risks.append(
                f"The target metric contains {target_null_pct}% missing values, so some records were excluded from the analysis."
            )

        usable_rows = int(df[target].notna().sum())
        if usable_rows < 20:
            risks.append(
                "The usable sample for the target metric is relatively small, so findings should be treated with caution."
            )

    datetime_cols = df.select_dtypes(include=["datetime64[ns]"]).columns.tolist()
    if intent == "trend_analysis" and not datetime_cols:
        risks.append(
            "A trend-style question was asked, but no reliable date column was detected, so time-based conclusions may be limited."
        )

    correlations = analysis.get("correlations", {})
    if intent in ["relationship_analysis", "general_analysis"] and correlations:
        risks.append(
            "Correlation helps identify directional relationships, but it does not prove causation."
        )

    object_cols = df.select_dtypes(include=["object"]).columns.tolist()
    long_tail_cols = [col for col in object_cols if df[col].nunique(dropna=True) > max(25, int(len(df) * 0.5))]
    if long_tail_cols:
        risks.append(
            f"Some categorical fields have very high cardinality, such as {long_tail_cols[0]}, which can make group-level comparisons less stable."
        )

    duplicate_rows = int(df.duplicated().sum())
    if duplicate_rows > 0:
        risks.append(
            f"The dataset contains {duplicate_rows} duplicate rows, which may affect aggregate totals if duplicates are not expected."
        )

    if plan and plan.get("reasoning", {}).get("warnings"):
        risks.extend(plan["reasoning"]["warnings"][:2])

    if not risks:
        risks.append(
            "This analysis is strong for descriptive insight, but results should still be validated against business context before making high-stakes decisions."
        )

    return dedupe_list(risks)[:5]


def preprocess_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    df.columns = [str(col).strip() for col in df.columns]

    money_keywords = ["amount", "revenue", "sales_value", "price", "cost", "profit"]

    for col in df.columns:
        col_lower = col.lower().strip()
        if col_lower in money_keywords:
            df[col] = (
                df[col]
                .astype(str)
                .str.replace(r"[^\d\.\-]", "", regex=True)
                .str.strip()
            )
            df[col] = pd.to_numeric(df[col], errors="coerce")

    numeric_keywords = ["boxes shipped", "boxes", "quantity", "qty", "sales", "units", "count", "volume"]

    for col in df.columns:
        col_lower = col.lower().strip()
        if col_lower in numeric_keywords:
            df[col] = (
                df[col]
                .astype(str)
                .str.replace(r"[^\d\.\-]", "", regex=True)
                .str.strip()
            )
            df[col] = pd.to_numeric(df[col], errors="coerce")

    for col in df.columns:
        col_lower = col.lower().strip()
        if "date" in col_lower or "time" in col_lower:
            df[col] = pd.to_datetime(df[col], errors="coerce")

    return df


def normalize_intent(intent):
    mapping = {
        "trend": "trend_analysis",
        "trend_analysis": "trend_analysis",
        "comparison": "comparison",
        "distribution": "distribution_analysis",
        "distribution_analysis": "distribution_analysis",
        "ranking": "ranking_analysis",
        "ranking_analysis": "ranking_analysis",
        "relationship": "relationship_analysis",
        "relationship_analysis": "relationship_analysis",
        "composition": "contribution_analysis",
        "contribution_analysis": "contribution_analysis",
        "diagnostic": "general_analysis",
        "general_analysis": "general_analysis",
        "summary_analysis": "summary_analysis",
        "segment_analysis": "segment_analysis",
    }
    return mapping.get(str(intent or "").strip().lower(), "general_analysis")


def normalize_question_category(intent, fallback_category):
    mapping = {
        "trend_analysis": "trend",
        "comparison": "comparison",
        "distribution_analysis": "distribution",
        "ranking_analysis": "ranking",
        "relationship_analysis": "relationship",
        "contribution_analysis": "contribution",
        "summary_analysis": "summary",
        "segment_analysis": "segment",
        "general_analysis": fallback_category or "general",
    }
    return mapping.get(intent, fallback_category or "general")


def dedupe_list(items):
    seen = set()
    result = []
    for item in items:
        key = str(item).strip().lower()
        if key and key not in seen:
            result.append(item)
            seen.add(key)
    return result


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