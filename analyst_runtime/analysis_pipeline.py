import os
import re
import pandas as pd

from agents.analyst_agents.legacy.question_agent import QuestionAgent
from agents.analyst_agents.legacy.planner_agent import PlannerAgent
from agents.analyst_agents.legacy.analysis_agent import AnalysisAgent
from agents.analyst_agents.legacy.kpi_agent import KPIAgent
from agents.analyst_agents.legacy.visualization_agent import VisualizationAgent
from agents.analyst_agents.legacy.narrative_agent import NarrativeAgent
from agents.analyst_agents.legacy.storytelling_agent import StorytellingAgent
from agents.analyst_agents.legacy.review_agent import ReviewAgent

# These are used later in the pipeline, so keep them imported too.
from agents.analyst_agents.legacy.dataset_understanding_agent import DatasetUnderstandingAgent
from agents.analyst_agents.legacy.column_selector_agent import ColumnSelectorAgent

# Keep your existing loader import path if it already works in your project.
# If your project uses a different loader module, update only this import line.
from engineer_runtime.dataset_loader import load_dataset


def run_analysis_pipeline(dataset_path, question, question_history=None, dataset_context=None):
    question_history = question_history or []

    print("🚀 ANALYSIS PIPELINE STARTED")
    print(f"📂 Loading dataset: {dataset_path}")

    os.makedirs("outputs/analyst/charts", exist_ok=True)

    bundle = load_dataset(dataset_path)
    df = bundle.dataframe

    if not isinstance(df, pd.DataFrame):
        raise ValueError("Dataset failed to load")

    print(
        f"✅ Dataset loaded — {len(df):,} rows × {len(df.columns)} columns "
        f"| format={bundle.dataset_format}"
    )

    if bundle.warnings:
        print(f"⚠️ Loader warnings: {bundle.warnings}")

    df = preprocess_dataframe(df)
    columns = df.columns.tolist()
    column_profiles = build_column_profiles(df)

    print(f"✅ Preprocessing complete — columns: {columns}")
    print("🧾 Built column profiles for planner")

    if dataset_context is None:
        print("🔍 Running DatasetUnderstandingAgent")
        try:
            understanding_agent = DatasetUnderstandingAgent()
            dataset_context = understanding_agent.run(df)
        except Exception as e:
            print(f"⚠️ DatasetUnderstandingAgent failed: {e}")
            dataset_context = {}
    else:
        print("✅ Using cached dataset context")

    print("🧠 Running QuestionAgent")
    question_agent = QuestionAgent()
    question_info = question_agent.run(question)

    fallback_intent = question_info.get("intent", "general_analysis")
    show_kpis = question_info.get("show_kpis", False)
    question_category = question_info.get("question_category", "general")
    question_goal = question_info.get(
        "question_goal",
        "Understand the most important pattern in the dataset."
    )

    print(f"✅ Fallback intent: {fallback_intent} | Show KPIs: {show_kpis}")

    print("🎯 Running ColumnSelectorAgent")
    column_selector = ColumnSelectorAgent()
    relevant_profiles = column_selector.run(question, column_profiles, dataset_context=dataset_context)

    llm_target_hint = None
    for profile in relevant_profiles:
        if profile.get("llm_target_hint"):
            llm_target_hint = profile["name"]
            break

    print("📊 Running PlannerAgent")
    planner = PlannerAgent()
    plan = planner.run(question, relevant_profiles)

    target = plan.get("target")
    drivers = plan.get("drivers", [])
    planner_intent = plan.get("analysis_type")
    time_column = plan.get("time_column")
    aggregation = plan.get("aggregation", "none")
    preferred_chart = plan.get("chart", "table")
    planner_reasoning = plan.get("reasoning", {}) or {}

    intent = normalize_intent(planner_intent or fallback_intent)
    question_category = normalize_question_category(intent, question_category)

    if target is not None and target in columns:
        pass
    elif llm_target_hint and llm_target_hint in columns:
        target = llm_target_hint
        planner_reasoning.setdefault("warnings", []).append(
            f"Target set from ColumnSelectorAgent hint: {target}"
        )
    else:
        target = resolve_best_target_from_profiles(column_profiles, question)

    if target is None and columns:
        target = columns[0]

    drivers = resolve_valid_drivers(
        drivers=drivers,
        column_profiles=column_profiles,
        target=target,
        question=question,
        max_drivers=5
    )

    if time_column and time_column not in columns:
        time_column = None

    if time_column is None and is_trend_like_question(question):
        time_column = resolve_best_time_column(column_profiles)

    if intent == "trend_analysis":
        if aggregation == "none":
            aggregation = "sum"
        if preferred_chart == "table":
            preferred_chart = "line" if time_column else "bar"

    resolved_plan = dict(plan)
    resolved_plan["target"] = target
    resolved_plan["drivers"] = drivers
    resolved_plan["time_column"] = time_column
    resolved_plan["analysis_type"] = planner_intent
    resolved_plan["aggregation"] = aggregation
    resolved_plan["chart"] = preferred_chart

    print(
        f"✅ Target: {target} | Drivers: {drivers} | "
        f"Intent: {intent} | Time column: {time_column} | "
        f"Aggregation: {aggregation} | Preferred chart: {preferred_chart}"
    )

    if should_defer_ambiguous_question(
        question=question,
        resolved_plan=resolved_plan,
        planner_reasoning=planner_reasoning,
        question_info=question_info
    ):
        print("⚠️ Ambiguous question detected — returning safe exploratory response")
        result = build_ambiguous_response(
            df=df,
            question=question,
            question_category=question_category,
            question_goal=question_goal,
            intent=intent,
            resolved_plan=resolved_plan,
            planner_reasoning=planner_reasoning,
            question_history=question_history
        )
        result["dataset_loader"] = {
            "format": bundle.dataset_format,
            "warnings": bundle.warnings,
            "metadata": bundle.metadata,
        }
        return result

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
                    drivers=drivers,
                    dataset_context=dataset_context
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
            "top_segments": [],
            "bottom_segments": [],
            "top_bottom_segments": {},
            "distribution_summary": {},
            "time_summary": {},
            "concentration_summary": {},
            "outlier_summary": {},
            "performance_diagnostics": {},
            "analysis_metadata": {
                "intent": intent,
                "time_column_used": None,
                "aggregation_used": aggregation,
                "driver_priority": drivers
            }
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
                plan=resolved_plan,
                dataset_context=dataset_context
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
        plan=resolved_plan
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
        question_goal=question_goal,
        question_history=question_history,
        plan=resolved_plan
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
        "plan": resolved_plan,
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
        "story": story,
        "dataset_context": dataset_context,
        "dataset_loader": {
            "format": bundle.dataset_format,
            "warnings": bundle.warnings,
            "metadata": bundle.metadata,
        },
    }


def should_defer_ambiguous_question(question, resolved_plan, planner_reasoning, question_info):
    q = (question or "").strip().lower()
    warnings = [str(w).lower() for w in planner_reasoning.get("warnings", [])]
    target = resolved_plan.get("target")
    drivers = resolved_plan.get("drivers", []) or []
    intent = normalize_intent(resolved_plan.get("analysis_type") or question_info.get("intent"))

    token_count = len([t for t in re.split(r"\s+", q) if t.strip()])

    ambiguity_phrases = [
        "too ambiguous",
        "does not specify a measurable business metric",
        "no explicit kpi",
        "no explicit pki",
        "cannot be selected confidently",
        "specify the metric of interest"
    ]

    has_ambiguity_warning = any(
        phrase in warning for phrase in ambiguity_phrases for warning in warnings
    )

    very_short_question = token_count <= 3
    vague_question = q in {
        "kpi insights", "pki insights", "insights", "kpis", "summary", "analysis", "show insights"
    }

    weak_plan = (not target) or (intent == "general_analysis" and len(drivers) <= 1)

    return bool(has_ambiguity_warning and (very_short_question or vague_question or weak_plan))


def build_ambiguous_response(
    df,
    question,
    question_category,
    question_goal,
    intent,
    resolved_plan,
    planner_reasoning,
    question_history=None
):
    question_history = question_history or []
    target = resolved_plan.get("target")
    drivers = resolved_plan.get("drivers", [])
    warnings = planner_reasoning.get("warnings", []) or []

    dataset_summary = build_ambiguous_dataset_summary(df, target, intent, drivers)
    data_quality_summary = build_ambiguous_data_quality_summary(df, target)
    follow_up_questions = build_metric_refinement_questions(df, target)

    direct_answer = (
        "Your question is too broad to choose one reliable KPI automatically. "
        "Please refine it by naming a metric such as Sales, Revenue, Profit, Quantity, or Transaction Count."
    )

    executive_summary = (
        "The system detected that the question does not clearly specify a measurable target. "
        "Instead of forcing a confident answer, it is returning a safe exploratory response and suggested follow-up questions."
    )

    business_impact = [
        "A refined metric will make the analysis more accurate, more interpretable, and more defensible in front of stakeholders.",
        "Choosing a clear KPI first helps the system generate better charts, more relevant group comparisons, and stronger recommendations."
    ]

    recommended_actions = [
        "Ask the question again with a specific KPI, such as 'Which region is contributing the most to sales?'",
        "If you want overall exploration, ask for a specific metric summary such as 'Give me a business summary of sales performance.'",
        "Use one of the suggested follow-up questions below to continue with a clearer analytical target."
    ]

    risks_or_limitations = list(warnings[:3]) if warnings else []
    if not risks_or_limitations:
        risks_or_limitations = [
            "No explicit KPI or measurable business metric was provided in the question.",
            "Proceeding with a fallback target would risk producing a misleading or weak business answer."
        ]

    top_insights = [
        {
            "title": "Question needs refinement",
            "value": "Metric not explicit",
            "detail": "The current question does not clearly identify the KPI the analysis should optimize for.",
            "type": "risk"
        },
        {
            "title": "Safe mode applied",
            "value": "Exploratory response",
            "detail": "The system avoided returning an overconfident answer from a weak fallback target.",
            "type": "signal"
        },
        {
            "title": "Next best step",
            "value": "Choose a KPI",
            "detail": "Refine the question using a target like Sales, Revenue, Profit, Quantity, or Transaction Count.",
            "type": "info"
        }
    ]

    narrative = {
        "title": "Analyst Narrative",
        "summary": executive_summary,
        "paragraphs": [
            "The question is too broad to support a strong business conclusion because it does not specify the metric that should anchor the analysis.",
            "Rather than forcing a potentially misleading answer, the system is returning a safe exploratory response and asking for a clearer KPI.",
            "Once a specific target is named, the analysis can generate a stronger direct answer, more relevant charts, and more reliable recommendations."
        ]
    }

    story = {
        "title": "Data Story",
        "headline": direct_answer,
        "key_points": [
            "The question does not specify a reliable KPI.",
            "A fallback target was not promoted into a confident business answer.",
            "The next step is to ask again using a named metric."
        ],
        "business_view": [
            "This safeguard improves trustworthiness by preventing the system from bluffing a precise answer from an ambiguous prompt.",
            "Clear KPI framing leads to better planning, better charts, and better executive interpretation."
        ]
    }

    kpis = {
        "row_count": int(len(df)),
        "column_count": int(len(df.columns)),
        "target_coverage_pct": None,
        "aggregation_used": resolved_plan.get("aggregation", "none")
    }

    return {
        "question": question,
        "intent": intent,
        "question_category": question_category,
        "question_goal": question_goal,
        "show_kpis": False,
        "target": target,
        "drivers": drivers,
        "plan": resolved_plan,
        "time_column": resolved_plan.get("time_column"),
        "aggregation": resolved_plan.get("aggregation"),
        "preferred_chart": resolved_plan.get("chart"),
        "planner_reasoning": planner_reasoning,
        "kpis": kpis,
        "analysis": {
            "correlations": {},
            "categorical_drivers": {},
            "top_segments": [],
            "bottom_segments": [],
            "top_bottom_segments": {},
            "distribution_summary": {},
            "time_summary": {},
            "concentration_summary": {},
            "outlier_summary": {},
            "performance_diagnostics": {},
            "analysis_metadata": {
                "intent": intent,
                "time_column_used": resolved_plan.get("time_column"),
                "aggregation_used": resolved_plan.get("aggregation"),
                "driver_priority": drivers
            }
        },
        "charts": [],
        "executive_summary": executive_summary,
        "direct_answer": direct_answer,
        "business_impact": business_impact,
        "recommended_actions": recommended_actions,
        "risks_or_limitations": risks_or_limitations,
        "dataset_summary": dataset_summary,
        "top_insights": top_insights,
        "follow_up_questions": follow_up_questions,
        "data_quality_summary": data_quality_summary,
        "narrative": narrative,
        "story": story
    }


def build_ambiguous_dataset_summary(df, target, intent, drivers):
    numeric_cols = df.select_dtypes(include=["number"]).columns.tolist()
    categorical_cols = df.select_dtypes(include=["object"]).columns.tolist()
    datetime_cols = df.select_dtypes(include=["datetime64[ns]", "datetime64[ns, UTC]"]).columns.tolist()

    date_range_start = None
    date_range_end = None
    if datetime_cols:
        series = df[datetime_cols[0]].dropna()
        if len(series) > 0:
            try:
                min_date = series.min()
                max_date = series.max()
                if not (min_date.year == 1970 and max_date.year == 1970):
                    date_range_start = str(min_date.date())
                    date_range_end = str(max_date.date())
            except Exception:
                pass

    return {
        "row_count": int(len(df)),
        "column_count": int(len(df.columns)),
        "target_metric": target,
        "analysis_type": intent,
        "numeric_column_count": int(len(numeric_cols)),
        "categorical_column_count": int(len(categorical_cols)),
        "datetime_column_count": int(len(datetime_cols)),
        "date_range_start": date_range_start,
        "date_range_end": date_range_end,
        "driver_columns": drivers or []
    }


def build_ambiguous_data_quality_summary(df, target):
    overall_missing_pct = round(float(df.isna().mean().mean() * 100), 1) if len(df.columns) > 0 else 0.0
    duplicate_rows = int(df.duplicated().sum())

    target_null_pct = None
    if target and target in df.columns:
        target_null_pct = round(float(df[target].isna().mean() * 100), 1)

    date_range = None
    datetime_cols = df.select_dtypes(include=["datetime64[ns]", "datetime64[ns, UTC]"]).columns.tolist()
    if datetime_cols:
        series = df[datetime_cols[0]].dropna()
        if len(series) > 0:
            try:
                min_date = series.min()
                max_date = series.max()
                if not (min_date.year == 1970 and max_date.year == 1970):
                    date_range = {
                        "start": str(min_date.date()),
                        "end": str(max_date.date())
                    }
            except Exception:
                pass

    high_cardinality_columns = []
    for col in df.select_dtypes(include=["object"]).columns.tolist():
        unique_values = int(df[col].nunique(dropna=True))
        if unique_values > max(25, int(len(df) * 0.5)):
            high_cardinality_columns.append({
                "column": col,
                "unique_values": unique_values
            })

    return {
        "overall_missing_pct": overall_missing_pct,
        "duplicate_rows": duplicate_rows,
        "target_null_pct": target_null_pct,
        "confidence_level": "Needs refinement",
        "confidence_note": "The data is available, but the question needs a clearer KPI before a reliable business answer can be generated.",
        "date_range": date_range,
        "high_cardinality_columns": high_cardinality_columns[:3]
    }


def build_metric_refinement_questions(df, target=None):
    candidates = []

    numeric_cols = df.select_dtypes(include=["number"]).columns.tolist()
    preferred_keywords = ["sales", "revenue", "profit", "amount", "cost", "quantity", "score", "count", "total"]

    ranked = []
    for col in numeric_cols:
        score = 0
        lower = str(col).lower()
        for kw in preferred_keywords:
            if kw in lower:
                score += 3
        if lower == str(target or "").lower():
            score += 1
        ranked.append((col, score))

    ranked.sort(key=lambda x: x[1], reverse=True)

    top_metrics = [col for col, _ in ranked[:3]] if ranked else []
    if not top_metrics:
        top_metrics = ["Sales", "Revenue", "Quantity"]

    for metric in top_metrics:
        candidates.append(f"Give me a business summary of {metric}.")
        candidates.append(f"Which groups are driving the highest {metric}?")

    seen = set()
    final = []
    for q in candidates:
        if q not in seen:
            final.append(q)
            seen.add(q)

    return final[:5]


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
    top_bottom_segments = analysis.get("top_bottom_segments", {}) or {}
    categorical_drivers = analysis.get("categorical_drivers", {}) or {}
    correlations = analysis.get("correlations", {}) or {}
    target_label = format_label(target).lower() if target else "the metric"

    if target:
        parts.append(
            f"This analysis is centered on {target_label} as the primary business metric."
        )

    if _is_totals_question(question) and kpis.get("total_target") is not None:
        total = format_number(kpis["total_target"])
        row_count = format_number(kpis.get("row_count"))
        parts.append(
            f"The total {target_label} across {row_count} records is {total}. "
            f"Note: this uses {target_label} as a proxy — no exact revenue column exists in the schema."
        )
    elif _is_count_question(question) and kpis.get("row_count") is not None:
        row_count = format_number(kpis["row_count"])
        parts.append(
            f"A total of {row_count} records are in the dataset."
        )
    elif question_goal:
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

    elif not _is_totals_question(question) and not _is_count_question(question):
        best = best_headline_segment(top_bottom_segments, categorical_drivers)
        if best:
            parts.append(
                f"The clearest visible leader is {best['segment']} within {format_label(best['dimension']).lower()}."
            )

    if correlations and intent != "trend_analysis":
        meaningful = meaningful_correlations(correlations)
        if meaningful:
            top_corr = meaningful[0]
            relation = "moves with" if top_corr[1] > 0 else "moves opposite to"
            parts.append(
                f"{format_label(top_corr[0]).lower()} is the strongest measurable numeric signal and {relation} the target metric."
            )

    if not parts:
        parts.append(
            "The dataset was analyzed successfully and the strongest visible patterns were summarized into visuals and business interpretation."
        )

    return " ".join(parts)


def _is_rate_question(question):
    q = (question or "").lower()
    return any(w in q for w in [
        "overall", "rate", "percentage", "percent", "proportion",
        "cancellation rate", "booking rate"
    ])


def _is_totals_question(question):
    q = (question or "").lower()
    return any(w in q for w in [
        "total revenue", "total bookings", "total sales", "total profit",
        "total amount", "overall revenue", "overall total",
        "grand total", "sum of", "how much revenue", "how much profit"
    ])


def _is_count_question(question):
    q = (question or "").lower()
    return any(w in q for w in [
        "how many", "number of", "total number", "count of",
        "how many bookings", "how many customers", "how many guests",
        "how many records"
    ])


def _is_binary_target(target, kpis):
    avg = kpis.get("average_target")
    median = kpis.get("median_target")
    if avg is None or median is None:
        return False
    try:
        return median in (0, 1, 0.0, 1.0) and 0 < float(avg) < 1
    except Exception:
        return False


def build_direct_answer(question, intent, target, kpis, analysis):
    time_summary = analysis.get("time_summary", {}) or {}
    top_segments = analysis.get("top_segments", []) or []
    top_bottom_segments = analysis.get("top_bottom_segments", {}) or {}
    categorical_drivers = analysis.get("categorical_drivers", {}) or {}
    correlations = analysis.get("correlations", {}) or {}

    target_label = format_label(target).lower() if target else "the metric"

    if _is_totals_question(question) and intent not in {"trend_analysis"}:
        total = kpis.get("total_target")
        avg = kpis.get("average_target")
        row_count = kpis.get("row_count")
        if total is not None:
            total_fmt = format_number(total)
            rows_fmt = format_number(row_count)
            avg_fmt = format_number(avg)
            return (
                f"The total {target_label} across all {rows_fmt} records is {total_fmt}, "
                f"with an average of {avg_fmt} per record. "
                f"Note: this is a proxy estimate — {target_label} is used as the closest available metric."
            )

    if _is_count_question(question) and intent not in {"trend_analysis"}:
        row_count = kpis.get("row_count")
        if row_count:
            rows_fmt = format_number(row_count)
            return (
                f"A total of {rows_fmt} records are in the dataset. "
                f"The trend chart above shows how the count varies across time periods."
            )

    if _is_rate_question(question) and _is_binary_target(target, kpis) and intent != "trend_analysis":
        avg = kpis.get("average_target")
        total = kpis.get("total_target")
        row_count = kpis.get("row_count")
        if avg is not None:
            rate_pct = round(float(avg) * 100, 1)
            total_fmt = format_number(total)
            rows_fmt = format_number(row_count)
            try:
                ratio = round(1 / float(avg))
                ratio_text = f" This means roughly 1 in {ratio:,} records is flagged."
            except Exception:
                ratio_text = ""
            return (
                f"The overall {target_label} rate is {rate_pct}% "
                f"({total_fmt} out of {rows_fmt} records).{ratio_text}"
            )

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
        meaningful = meaningful_correlations(correlations)
        if meaningful:
            top_corr = meaningful[0]
            direction = "positively associated with" if top_corr[1] > 0 else "negatively associated with"
            return (
                f"The strongest numeric relationship is that {format_label(top_corr[0]).lower()} is "
                f"{direction} {format_label(target).lower()} with a correlation of {top_corr[1]}."
            )

    best = best_headline_segment(top_bottom_segments, categorical_drivers)
    if best:
        return (
            f"The clearest answer is that {best['segment']} is currently the leading "
            f"{format_label(best['dimension']).lower()} for {format_label(target).lower()}, "
            f"with a measured contribution of {format_number(best.get('total_target'))}."
        )

    flat_best = best_non_placeholder_segment(top_segments)
    if flat_best:
        return (
            f"The clearest answer is that {flat_best['segment']} is currently the leading "
            f"{format_label(flat_best['dimension']).lower()} for {format_label(target).lower()}, "
            f"with a measured contribution of {format_number(flat_best.get('total_target'))}."
        )

    if kpis.get("top_dimension_name") and kpis.get("top_dimension_value"):
        if str(kpis["top_dimension_value"]).strip().lower() not in {"unknown", "error", "n/a", "na", "null", "none", ""}:
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
    top_bottom_segments = analysis.get("top_bottom_segments", {}) or {}
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

    else:
        best = best_headline_segment(top_bottom_segments, categorical_drivers)
        if not best:
            best = best_non_placeholder_segment(top_segments)
        if best:
            lines.append(
                f"Performance is not evenly distributed: {best['segment']} is a strong benchmark segment that can be compared against weaker groups."
            )
        elif kpis.get("top_dimension_name") and kpis.get("top_dimension_value"):
            if str(kpis["top_dimension_value"]).strip().lower() not in {"unknown", "error", "n/a", "na", "null", "none", ""}:
                lines.append(
                    f"Performance is not evenly distributed: {kpis['top_dimension_value']} is a strong benchmark segment that can be compared against weaker groups."
                )

    if categorical_drivers and intent != "trend_analysis":
        cleaned = [
            format_label(name).lower()
            for name, _ in sorted(categorical_drivers.items(), key=lambda x: x[1], reverse=True)
            if not any(bad in str(name).lower() for bad in ["id", "postal", "zip", "row"])
        ]
        if cleaned:
            lines.append(
                f"The variation across {cleaned[0]} suggests that segment-level decisions will likely be more useful than one-size-fits-all actions."
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

    if kpis.get("top_dimension_name") and kpis.get("top_dimension_value"):
        if str(kpis["top_dimension_value"]).strip().lower() not in {"unknown", "error", "n/a", "na", "null", "none", ""}:
            actions.append(
                f"Use {kpis['top_dimension_value']} as a benchmark segment and compare the rest of the groups against it."
            )

    if intent == "comparison":
        actions.append(
            "Investigate why the highest-performing groups are ahead and test whether those conditions can be replicated in weaker segments."
        )

    meaningful = meaningful_correlations(correlations)
    if meaningful and intent != "trend_analysis":
        top_corr = meaningful[0]
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

    datetime_cols = df.select_dtypes(include=["datetime64[ns]", "datetime64[ns, UTC]"]).columns.tolist()
    if intent == "trend_analysis" and not datetime_cols:
        risks.append(
            "A trend-style question was asked, but no reliable date column was detected, so time-based conclusions may be limited."
        )

    correlations = analysis.get("correlations", {})
    if intent in ["relationship_analysis", "general_analysis"] and meaningful_correlations(correlations):
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


def build_phase1_product_layer(
    df,
    question,
    intent,
    target,
    drivers,
    kpis,
    analysis,
    charts,
    question_category,
    question_goal,
    question_history=None,
    plan=None
):
    question_history = question_history or []

    dataset_summary = build_dataset_summary_layer(df, target, intent, drivers)
    top_insights = build_top_insights_layer(question, target, kpis, analysis, intent)
    follow_up_questions = build_follow_up_questions(
        question=question,
        target=target,
        drivers=drivers,
        question_category=question_category,
        intent=intent,
        question_history=question_history
    )
    data_quality_summary = build_data_quality_summary_layer(df, target, plan)

    return {
        "dataset_summary": dataset_summary,
        "top_insights": top_insights,
        "follow_up_questions": follow_up_questions,
        "data_quality_summary": data_quality_summary
    }


def build_dataset_summary_layer(df, target, intent, drivers):
    numeric_cols = df.select_dtypes(include=["number"]).columns.tolist()
    categorical_cols = df.select_dtypes(include=["object"]).columns.tolist()
    datetime_cols = df.select_dtypes(include=["datetime64[ns]", "datetime64[ns, UTC]"]).columns.tolist()

    date_range_start = None
    date_range_end = None
    if datetime_cols:
        series = df[datetime_cols[0]].dropna()
        if len(series) > 0:
            try:
                min_date = series.min()
                max_date = series.max()
                if not (min_date.year == 1970 and max_date.year == 1970):
                    date_range_start = str(min_date.date())
                    date_range_end = str(max_date.date())
            except Exception:
                pass

    return {
        "row_count": int(len(df)),
        "column_count": int(len(df.columns)),
        "target_metric": target,
        "analysis_type": intent,
        "numeric_column_count": int(len(numeric_cols)),
        "categorical_column_count": int(len(categorical_cols)),
        "datetime_column_count": int(len(datetime_cols)),
        "date_range_start": date_range_start,
        "date_range_end": date_range_end,
        "driver_columns": drivers or []
    }


def build_top_insights_layer(question, target, kpis, analysis, intent):
    insights = []

    top_segments = analysis.get("top_segments", []) or []
    top_bottom_segments = analysis.get("top_bottom_segments", {}) or {}
    time_summary = analysis.get("time_summary", {}) or {}

    if intent == "trend_analysis" and time_summary:
        if time_summary.get("best_period") and time_summary.get("best_period_value") is not None:
            insights.append({
                "title": "Strongest period",
                "value": time_summary["best_period"],
                "detail": f"{format_label(target)} peaked at {format_number(time_summary['best_period_value'])}.",
                "type": "positive"
            })

        if time_summary.get("worst_period") and time_summary.get("worst_period_value") is not None:
            insights.append({
                "title": "Weakest period",
                "value": time_summary["worst_period"],
                "detail": f"{format_label(target)} was lowest at {format_number(time_summary['worst_period_value'])}.",
                "type": "risk"
            })

        if time_summary.get("change_pct") is not None:
            change_pct = float(time_summary["change_pct"])
            insights.append({
                "title": "Net change",
                "value": f"{change_pct:+.1f}%",
                "detail": f"Overall change from {time_summary.get('first_period', 'start')} to {time_summary.get('last_period', 'end')}.",
                "type": "signal"
            })

    else:
        best = best_headline_segment(top_bottom_segments, analysis.get("categorical_drivers", {}) or {})
        if not best:
            best = best_non_placeholder_segment(top_segments)

        if best:
            insights.append({
                "title": f"Top {format_label(best['dimension'])}",
                "value": str(best["segment"]),
                "detail": f"Leads with {format_number(best.get('total_target'))} "
                          f"({str(best.get('share_pct')) + '%' if best.get('share_pct') is not None else 'share unavailable'}).",
                "type": "signal"
            })

        if kpis.get("total_target") is not None:
            insights.append({
                "title": f"Total {format_label(target)}",
                "value": format_number(kpis["total_target"]),
                "detail": "Overall scale of the primary metric across the loaded dataset.",
                "type": "positive"
            })

        if kpis.get("average_target") is not None:
            insights.append({
                "title": f"Average {format_label(target)}",
                "value": format_number(kpis["average_target"]),
                "detail": "Typical value per usable record for the selected target metric.",
                "type": "info"
            })

    if not insights:
        insights.append({
            "title": "Analysis complete",
            "value": "Ready",
            "detail": "The dataset has been processed and the main visuals and narrative are available.",
            "type": "signal"
        })

    return insights[:4]


def build_follow_up_questions(question, target, drivers, question_category, intent, question_history=None):
    question_history = question_history or []
    suggestions = []

    driver_label = format_label(drivers[0]) if drivers else "segment"
    target_label = format_label(target) if target else "the target metric"

    if intent == "trend_analysis":
        suggestions.extend([
            f"Which {driver_label.lower()} contributed most during the strongest period?",
            f"Break down the {target_label.lower()} trend by {driver_label.lower()}.",
            f"What changed between the strongest and weakest periods?"
        ])
    elif question_category in {"comparison", "ranking", "segment"}:
        suggestions.extend([
            f"Which {driver_label.lower()} is contributing the most to {target_label.lower()}?",
            f"Which {driver_label.lower()} is underperforming on {target_label.lower()}?",
            f"Show the monthly trend for the top {driver_label.lower()} by {target_label.lower()}."
        ])
    elif question_category == "relationship":
        suggestions.extend([
            f"What other fields are correlated with {target_label.lower()}?",
            f"Which groups show the strongest differences in {target_label.lower()}?",
            f"How does {target_label.lower()} change over time?"
        ])
    else:
        suggestions.extend([
            f"Give me a business summary of {target_label.lower()}.",
            f"Which segments are driving the highest {target_label.lower()}?",
            f"Show the trend of {target_label.lower()} over time."
        ])

    generic = [
        "What is the strongest visible pattern in this dataset?",
        "Which chart should I focus on first and why?",
        "What follow-up analysis would be most useful for decision-making?"
    ]
    suggestions.extend(generic)

    cleaned = []
    seen = set()
    history_lower = {q.strip().lower() for q in question_history if isinstance(q, str)}
    for s in suggestions:
        key = s.strip().lower()
        if not key or key == question.strip().lower() or key in history_lower or key in seen:
            continue
        cleaned.append(s)
        seen.add(key)

    return cleaned[:5]


def build_data_quality_summary_layer(df, target, plan=None):
    overall_missing_pct = round(float(df.isna().mean().mean() * 100), 1) if len(df.columns) > 0 else 0.0
    duplicate_rows = int(df.duplicated().sum())

    target_null_pct = None
    if target and target in df.columns:
        target_null_pct = round(float(df[target].isna().mean() * 100), 1)

    confidence_level = "High"
    confidence_note = "The result is based on the usable records available for the selected target metric."
    if target_null_pct is not None and target_null_pct > 10:
        confidence_level = "Medium"
        confidence_note = "The target metric has some missing values, so results should be interpreted with moderate caution."
    if target_null_pct is not None and target_null_pct > 25:
        confidence_level = "Low"
        confidence_note = "A large share of target values is missing, so conclusions may be directionally useful but less reliable."

    date_range = None
    datetime_cols = df.select_dtypes(include=["datetime64[ns]", "datetime64[ns, UTC]"]).columns.tolist()
    if datetime_cols:
        series = df[datetime_cols[0]].dropna()
        if len(series) > 0:
            try:
                min_date = series.min()
                max_date = series.max()
                if not (min_date.year == 1970 and max_date.year == 1970):
                    date_range = {
                        "start": str(min_date.date()),
                        "end": str(max_date.date())
                    }
            except Exception:
                pass

    high_cardinality_columns = []
    for col in df.select_dtypes(include=["object"]).columns.tolist():
        unique_values = int(df[col].nunique(dropna=True))
        if unique_values > max(25, int(len(df) * 0.5)):
            high_cardinality_columns.append({
                "column": col,
                "unique_values": unique_values
            })

    if plan and plan.get("reasoning", {}).get("warnings"):
        confidence_note += " Planner warnings were also detected and should be reviewed."

    return {
        "overall_missing_pct": overall_missing_pct,
        "duplicate_rows": duplicate_rows,
        "target_null_pct": target_null_pct,
        "confidence_level": confidence_level,
        "confidence_note": confidence_note,
        "date_range": date_range,
        "high_cardinality_columns": high_cardinality_columns[:3]
    }


def _synthesise_date_columns(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    def _norm(name):
        return re.sub(r"[_\-\s]+", "_", name.lower().strip())

    year_cols = []
    for col in df.columns:
        norm = _norm(col)
        if "year" not in norm:
            continue
        if not pd.api.types.is_numeric_dtype(df[col]):
            continue
        sample = df[col].dropna().head(20)
        if len(sample) == 0:
            continue
        try:
            if all(1900 <= int(v) <= 2100 for v in sample):
                year_cols.append(col)
        except (TypeError, ValueError):
            continue

    for year_col in year_cols:
        year_norm = _norm(year_col)
        prefix = re.sub(r"_?year_?", "_", year_norm).strip("_")

        month_col = None
        for col in df.columns:
            n = _norm(col)
            if "month" in n and pd.api.types.is_numeric_dtype(df[col]):
                col_prefix = re.sub(r"_?month_?.*", "", n).strip("_")
                if col_prefix == prefix or (prefix == "" and "month" in n):
                    month_col = col
                    break

        day_col = None
        for col in df.columns:
            n = _norm(col)
            if "day" in n and pd.api.types.is_numeric_dtype(df[col]):
                col_prefix = re.sub(r"_?day_?.*", "", n).strip("_")
                if col_prefix == prefix or (prefix == "" and "day" in n):
                    day_col = col
                    break

        if not month_col or not day_col:
            continue

        synth_name = (prefix + "_date").strip("_") if prefix else "synthetic_date"
        synth_name = re.sub(r"_+", "_", synth_name)

        already_exists = any(
            c.lower().strip().replace(" ", "_") == synth_name.lower()
            and pd.api.types.is_datetime64_any_dtype(df[c])
            for c in df.columns
        )
        if already_exists:
            continue

        if synth_name in df.columns and not pd.api.types.is_datetime64_any_dtype(df[synth_name]):
            continue

        try:
            synthesised = pd.to_datetime(dict(
                year=pd.to_numeric(df[year_col], errors="coerce"),
                month=pd.to_numeric(df[month_col], errors="coerce"),
                day=pd.to_numeric(df[day_col], errors="coerce")
            ), errors="coerce")

            valid = synthesised.dropna()
            if len(valid) < len(df) * 0.5:
                continue
            if len(valid) > 1:
                range_days = (valid.max() - valid.min()).days
                if range_days < 30:
                    continue

            df[synth_name] = synthesised
            print(f"✅ Synthesised {synth_name} from {year_col} + {month_col} + {day_col}")
        except Exception as e:
            print(f"⚠️ Could not synthesise {synth_name}: {e}")

    return df


def preprocess_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    df.columns = [str(col).strip() for col in df.columns]

    money_keywords = ["amount", "revenue", "sales_value", "price", "cost", "profit", "sales"]
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

    date_part_keywords = [
        "year", "month", "week_number", "week number",
        "day_of_month", "day of month", "hour", "minute", "second"
    ]

    for col in df.columns:
        col_lower = col.lower().strip()
        if "date" in col_lower or "time" in col_lower:
            if any(kw in col_lower for kw in date_part_keywords):
                continue
            if pd.api.types.is_datetime64_any_dtype(df[col]):
                continue
            if pd.api.types.is_numeric_dtype(df[col]):
                continue
            df[col] = pd.to_datetime(df[col], errors="coerce")

    df = _synthesise_date_columns(df)

    return df


def build_column_profiles(df: pd.DataFrame):
    profiles = []
    total_rows = max(len(df), 1)

    for col in df.columns:
        series = df[col]
        dtype = str(series.dtype)
        non_null_pct = float(series.notna().mean())
        unique_count = int(series.nunique(dropna=True))
        unique_ratio = float(unique_count / total_rows) if total_rows else 0.0

        sample_values = []
        for v in series.dropna().head(3).tolist():
            try:
                sample_values.append(str(v)[:50])
            except Exception:
                sample_values.append("")

        semantic_type = infer_semantic_type_from_series(col, series, unique_ratio)

        profiles.append({
            "name": col,
            "dtype": dtype,
            "semantic_type": semantic_type,
            "non_null_pct": round(non_null_pct, 4),
            "unique_count": unique_count,
            "unique_ratio": round(unique_ratio, 4),
            "sample_values": sample_values,
            "is_probable_id": is_probable_id_column(col, series, unique_ratio),
            "is_probable_metric": is_probable_metric_column(col, series),
            "is_probable_datetime": bool(pd.api.types.is_datetime64_any_dtype(series)),
        })

    return profiles


def infer_semantic_type_from_series(col_name, series, unique_ratio):
    col_norm = normalize_text(col_name)

    if is_probable_id_column(col_name, series, unique_ratio):
        return "id"

    if pd.api.types.is_datetime64_any_dtype(series):
        return "datetime"

    if pd.api.types.is_integer_dtype(series):
        sample_vals = series.dropna().unique()[:20].tolist()
        try:
            if sample_vals and all(1900 <= int(v) <= 2100 for v in sample_vals):
                if any(k in col_norm for k in ["year", "month", "quarter", "week", "day"]):
                    return "datetime"
        except (TypeError, ValueError):
            pass

    if any(k in col_norm for k in ["date", "time", "timestamp", "year", "month", "quarter", "week", "day"]):
        return "datetime"

    if pd.api.types.is_bool_dtype(series):
        return "boolean"

    if pd.api.types.is_numeric_dtype(series):
        return "metric"

    if pd.api.types.is_object_dtype(series):
        if any(k in col_norm for k in ["comment", "comments", "note", "notes", "description", "message", "text", "address"]):
            return "text"

        if any(
            k in col_norm for k in
            ["region", "country", "state", "city", "category", "segment", "product", "sub category",
             "channel", "customer", "ship mode", "department", "type", "group", "class", "market",
             "brand", "status", "item", "location"]
        ):
            return "categorical"

        if unique_ratio >= 0.95:
            return "text"

        return "categorical"

    return "unknown"


def is_probable_id_column(col_name, series, unique_ratio):
    col_norm = normalize_text(col_name)
    id_keywords = [
        "id", "uuid", "key", "row number", "rownum",
        "transaction id", "order id", "customer id", "product id",
        "postal", "zip", "zipcode", "row id"
    ]

    if any(k in col_norm for k in id_keywords):
        return True

    date_like_names = ["year", "month", "quarter", "week", "day", "date", "time"]
    if any(k in col_norm for k in date_like_names):
        return False

    if unique_ratio >= 0.98 and not pd.api.types.is_datetime64_any_dtype(series):
        if pd.api.types.is_object_dtype(series) or pd.api.types.is_integer_dtype(series):
            return True

    return False


def is_probable_metric_column(col_name, series):
    col_norm = normalize_text(col_name)
    metric_keywords = [
        "sales", "revenue", "profit", "amount", "price", "cost",
        "income", "margin", "quantity", "qty", "units", "discount",
        "value", "score", "rate", "count", "total"
    ]

    if any(k in col_norm for k in metric_keywords):
        return True

    if pd.api.types.is_numeric_dtype(series) and not pd.api.types.is_bool_dtype(series):
        return True

    return False


def resolve_best_target_from_profiles(column_profiles, question):
    question_lower = (question or "").strip().lower()
    ranked = []

    for col in column_profiles:
        name = col["name"]
        norm = normalize_text(name)
        semantic_type = col.get("semantic_type", "unknown")
        non_null_pct = float(col.get("non_null_pct", 1.0))
        unique_ratio = float(col.get("unique_ratio", 0.0))
        is_probable_id = bool(col.get("is_probable_id", False))
        is_probable_metric = bool(col.get("is_probable_metric", False))

        score = 0.0

        if is_probable_id:
            score -= 100.0

        if semantic_type == "metric":
            score += 8.0
        elif semantic_type == "categorical":
            score += 1.5
        elif semantic_type == "datetime":
            score -= 3.0
        elif semantic_type == "text":
            score -= 5.0

        if is_probable_metric:
            score += 4.0

        metric_keywords = [
            "sales", "revenue", "profit", "amount", "price", "cost",
            "income", "margin", "quantity", "qty", "units", "discount",
            "value", "score", "rate", "count", "total"
        ]
        for kw in metric_keywords:
            if kw in norm:
                score += 2.0
            if kw in question_lower and kw in norm:
                score += 3.0

        score += non_null_pct * 2.0

        if non_null_pct < 0.60:
            score -= 2.5

        if unique_ratio > 0.98 and semantic_type != "metric":
            score -= 6.0

        ranked.append((name, score))

    ranked.sort(key=lambda x: x[1], reverse=True)
    return ranked[0][0] if ranked else None


def resolve_valid_drivers(drivers, column_profiles, target, question, max_drivers=5):
    valid_names = {c["name"] for c in column_profiles}
    selected = []

    for driver in drivers or []:
        if not driver or driver == target or driver not in valid_names:
            continue

        profile = next((c for c in column_profiles if c["name"] == driver), None)
        if not profile:
            continue

        if profile.get("is_probable_id", False):
            continue

        if profile.get("semantic_type") == "text" and float(profile.get("unique_ratio", 0.0)) > 0.50:
            continue

        if float(profile.get("unique_ratio", 0.0)) > 0.98 and profile.get("semantic_type") == "categorical":
            continue

        if driver not in selected:
            selected.append(driver)

    if len(selected) >= max_drivers:
        return selected[:max_drivers]

    fallback_ranked = []
    question_lower = (question or "").strip().lower()

    for col in column_profiles:
        name = col["name"]
        if name == target or name in selected:
            continue

        semantic_type = col.get("semantic_type", "unknown")
        unique_ratio = float(col.get("unique_ratio", 0.0))
        non_null_pct = float(col.get("non_null_pct", 1.0))
        norm = normalize_text(name)

        score = 0.0

        if col.get("is_probable_id", False):
            score -= 100.0

        if semantic_type == "categorical":
            score += 5.0
        elif semantic_type == "datetime":
            score += 4.0
        elif semantic_type == "metric":
            score += 2.0
        elif semantic_type == "text":
            score -= 4.0

        for kw in [
            "region", "country", "state", "city", "category", "segment",
            "product", "sub category", "channel", "department", "group",
            "market", "brand", "status", "item", "location", "date", "time",
            "month", "quarter", "year", "type"
        ]:
            if kw in norm:
                score += 1.5
            if kw in question_lower and kw in norm:
                score += 2.0

        if unique_ratio > 0.95 and semantic_type == "categorical":
            score -= 4.0

        if non_null_pct < 0.50:
            score -= 1.5

        fallback_ranked.append((name, score))

    fallback_ranked.sort(key=lambda x: x[1], reverse=True)

    for name, score in fallback_ranked:
        if score <= 0:
            continue
        if name not in selected:
            selected.append(name)
        if len(selected) >= max_drivers:
            break

    return selected[:max_drivers]


def resolve_best_time_column(column_profiles):
    datetime_candidates = []

    for col in column_profiles:
        name = col["name"]
        norm = normalize_text(name)
        semantic_type = col.get("semantic_type", "unknown")
        is_probable_datetime = bool(col.get("is_probable_datetime", False))
        non_null_pct = float(col.get("non_null_pct", 1.0))
        dtype = str(col.get("dtype", "")).lower()

        score = 0.0

        if "datetime" in dtype:
            score += 12.0
        elif is_probable_datetime:
            score += 5.0
        elif semantic_type == "datetime":
            score += 3.0

        date_part_words = {"year", "month", "week", "day", "quarter", "hour", "minute", "second"}
        norm_tokens = set(norm.split())
        if "date" in norm and not norm_tokens.intersection(date_part_words):
            score += 4.0
        if "timestamp" in norm:
            score += 3.0
        if "time" in norm and "datetime" not in dtype:
            score += 1.0

        if norm_tokens.intersection(date_part_words):
            score += 0.5

        score += non_null_pct

        datetime_candidates.append((name, score))

    datetime_candidates.sort(key=lambda x: x[1], reverse=True)
    return datetime_candidates[0][0] if datetime_candidates and datetime_candidates[0][1] > 0 else None


def meaningful_correlations(correlations):
    ranked = sorted(correlations.items(), key=lambda x: abs(x[1]), reverse=True)
    cleaned = []
    for name, corr in ranked:
        lower = str(name).lower()
        if any(bad in lower for bad in ["id", "postal", "zip", "row"]):
            continue
        if abs(float(corr)) < 0.05:
            continue
        cleaned.append((name, corr))
    return cleaned


def best_headline_segment(top_bottom_segments, categorical_drivers):
    if not top_bottom_segments or not categorical_drivers:
        return None

    ranked_dims = sorted(
        categorical_drivers.items(),
        key=lambda x: x[1],
        reverse=True
    )

    def _get_top_seg(dim_name):
        if any(bad in dim_name.lower() for bad in ["id", "postal", "zip", "row"]):
            return None
        dim_data = top_bottom_segments.get(dim_name)
        if not dim_data:
            return None
        top_seg = dim_data.get("top")
        if not top_seg:
            return None
        seg_label = str(top_seg.get("segment", "")).strip().lower()
        if seg_label in {"unknown", "error", "n/a", "na", "none", "null", ""}:
            return None
        return top_seg

    for dim_name, _ in ranked_dims:
        top_seg = _get_top_seg(dim_name)
        if top_seg is None:
            continue
        share = top_seg.get("share_pct")
        if share is not None and (share > 80 or share < 1):
            continue
        return top_seg

    for dim_name, _ in ranked_dims:
        top_seg = _get_top_seg(dim_name)
        if top_seg is not None:
            return top_seg

    return None


def best_non_placeholder_segment(top_segments):
    if not top_segments:
        return None

    valid = []
    for seg in top_segments:
        label = str(seg.get("segment", "")).strip().lower()
        if label in {"unknown", "error", "n/a", "na", "none", "null", ""}:
            continue
        valid.append(seg)

    if not valid:
        return None

    return sorted(
        valid,
        key=lambda x: (
            x.get("share_pct") if x.get("share_pct") is not None else x.get("total_target", 0),
            x.get("total_target", 0)
        ),
        reverse=True
    )[0]


def is_trend_like_question(question):
    q = (question or "").strip().lower()
    trend_words = [
        "trend", "over time", "by month", "by year", "by quarter",
        "timeline", "growth", "decline", "change over time", "time series"
    ]
    return any(word in q for word in trend_words)


def normalize_text(text):
    text = str(text or "").strip().lower()
    text = re.sub(r"[_\-/]+", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text


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