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

    intent = question_info["intent"]
    show_kpis = question_info.get("show_kpis", False)
    question_category = question_info.get("question_category", "general")
    question_goal = question_info.get("question_goal", "Understand the most important pattern in the dataset.")

    print(f"✅ Intent: {intent} | Show KPIs: {show_kpis}")

    print("📊 Running PlannerAgent")
    planner = PlannerAgent()
    plan = planner.run(question, columns)

    target = plan.get("target")
    drivers = plan.get("drivers", [])

    numeric_cols = df.select_dtypes(include=["int64", "float64", "int32", "float32"]).columns.tolist()

    if target is None or target not in columns:
        if numeric_cols:
            target = numeric_cols[0]
        else:
            target = columns[-1]

    print(f"✅ Target: {target} | Drivers: {drivers}")

    print("📌 Running KPIAgent")
    kpis = {}
    if show_kpis:
        try:
            kpi_agent = KPIAgent()
            kpis = kpi_agent.run(df, target)
        except Exception as e:
            print(f"⚠️ KPIAgent failed: {e}")
            kpis = {}

    print("✅ KPIs done")

    print("📈 Running AnalysisAgent")
    analysis_results = {}
    try:
        analysis_agent = AnalysisAgent()
        analysis_results = analysis_agent.run(df, target)
    except Exception as e:
        print(f"⚠️ AnalysisAgent failed: {e}")
        analysis_results = {
            "correlations": {},
            "categorical_drivers": {}
        }

    print("✅ Statistical analysis done")

    print("📊 Running VisualizationAgent")
    charts = []
    try:
        viz_agent = VisualizationAgent()
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
        charts=charts
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
    charts
):
    executive_summary = build_executive_summary(
        question=question,
        question_goal=question_goal,
        target=target,
        kpis=kpis,
        analysis=analysis
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
        charts=charts
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
        analysis=analysis
    )

    return {
        "executive_summary": executive_summary,
        "direct_answer": direct_answer,
        "business_impact": business_impact,
        "recommended_actions": recommended_actions,
        "risks_or_limitations": risks_or_limitations
    }


def build_executive_summary(question, question_goal, target, kpis, analysis):
    parts = []

    if target:
        parts.append(
            f"This analysis is centered on {format_label(target).lower()} as the primary business metric."
        )

    if question_goal:
        parts.append(question_goal)

    if kpis.get("top_dimension_name") and kpis.get("top_dimension_value"):
        dim_name = str(kpis["top_dimension_name"]).lower()
        dim_value = str(kpis["top_dimension_value"])
        dim_metric = format_number(kpis.get("top_dimension_metric"))
        parts.append(
            f"The clearest visible leader is {dim_value} within {dim_name}, contributing {dim_metric}."
        )

    correlations = analysis.get("correlations", {})
    if correlations:
        top_corr = sorted(correlations.items(), key=lambda x: abs(x[1]), reverse=True)[0]
        relation = "moves with" if top_corr[1] > 0 else "moves opposite to"
        parts.append(
            f"{top_corr[0]} is the strongest measurable numeric signal and {relation} the target metric."
        )

    if not parts:
        parts.append("The dataset was analyzed successfully and the strongest visible patterns were summarized into visuals and business interpretation.")

    return " ".join(parts)


def build_direct_answer(question, intent, target, kpis, analysis):
    if kpis.get("top_dimension_name") and kpis.get("top_dimension_value"):
        metric = format_number(kpis.get("top_dimension_metric"))
        return (
            f"The clearest answer is that {kpis['top_dimension_value']} is currently the leading "
            f"{str(kpis['top_dimension_name']).lower()} for {format_label(target).lower()}, "
            f"with a measured contribution of {metric}."
        )

    correlations = analysis.get("correlations", {})
    if intent == "relationship_analysis" and correlations:
        top_corr = sorted(correlations.items(), key=lambda x: abs(x[1]), reverse=True)[0]
        direction = "positively associated with" if top_corr[1] > 0 else "negatively associated with"
        return (
            f"The strongest numeric relationship is that {top_corr[0]} is "
            f"{direction} {format_label(target).lower()} with a correlation of {top_corr[1]}."
        )

    if target:
        return (
            f"The answer is centered on {format_label(target).lower()}, with the visuals showing where performance is concentrated, how it differs across groups, and which signals matter most."
        )

    return "The analysis completed successfully, but the answer could not be narrowed to a single target metric."


def build_business_impact(target, kpis, analysis, charts):
    lines = []

    if kpis.get("top_dimension_name") and kpis.get("top_dimension_value"):
        lines.append(
            f"Performance is not evenly distributed: {kpis['top_dimension_value']} is a strong benchmark segment that can be compared against weaker groups."
        )

    categorical_drivers = analysis.get("categorical_drivers", {})
    if categorical_drivers:
        top_cat = sorted(categorical_drivers.items(), key=lambda x: x[1], reverse=True)[0][0]
        lines.append(
            f"The variation across {top_cat} suggests that segment-level decisions will likely be more useful than one-size-fits-all actions."
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

    if kpis.get("top_dimension_name") and kpis.get("top_dimension_value"):
        actions.append(
            f"Use {kpis['top_dimension_value']} as a benchmark segment and compare the rest of the groups against it."
        )

    if intent == "trend_analysis":
        actions.append(
            "Review the time-based chart to determine whether the pattern is stable, improving, or driven by a limited number of spikes."
        )

    if intent == "comparison":
        actions.append(
            "Investigate why the highest-performing groups are ahead and test whether those conditions can be replicated in weaker segments."
        )

    correlations = analysis.get("correlations", {})
    if correlations:
        top_corr = sorted(correlations.items(), key=lambda x: abs(x[1]), reverse=True)[0]
        actions.append(
            f"Investigate {top_corr[0]} further as a potential driver of {format_label(target).lower()}, while treating the current result as directional rather than causal."
        )

    if not actions:
        actions.append(
            f"Use the primary chart to validate the main answer, then use the supporting visuals to check which dimensions explain differences in {format_label(target).lower()}."
        )

    return actions[:4]


def build_risks_and_limitations(df, intent, target, drivers, analysis):
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

    if not risks:
        risks.append(
            "This analysis is strong for descriptive insight, but results should still be validated against business context before making high-stakes decisions."
        )

    return risks[:5]


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