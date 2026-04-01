import os
import re
import pandas as pd

from agents.analyst_agents.question_agent import QuestionAgent
from agents.analyst_agents.planner_agent import PlannerAgent
from agents.analyst_agents.column_selector_agent import ColumnSelectorAgent
from agents.analyst_agents.dataset_understanding_agent import DatasetUnderstandingAgent
from agents.analyst_agents.analysis_agent import AnalysisAgent
from agents.analyst_agents.visualization_agent import VisualizationAgent
from agents.analyst_agents.narrative_agent import NarrativeAgent
from agents.analyst_agents.storytelling_agent import StorytellingAgent
from agents.analyst_agents.kpi_agent import KPIAgent

from analyst_runtime.phase1_product_layer import build_phase1_product_layer


def run_analysis_pipeline(dataset_path, question, question_history=None, dataset_context=None):
    question_history = question_history or []

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
    column_profiles = build_column_profiles(df)

    print(f"✅ Preprocessing complete — columns: {columns}")
    print("🧾 Built column profiles for planner")

    # --------------------------------------------------
    # DatasetUnderstandingAgent — run once per dataset upload.
    # If dataset_context is passed in (session cache), skip the LLM call.
    # This gives all downstream agents semantic knowledge about the dataset
    # (domain, primary metric, column meanings) before any question is asked.
    # --------------------------------------------------
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

    # --------------------------------------------------
    # LLM-guided column selection
    # Runs before PlannerAgent so the planner only sees columns
    # relevant to the question. This handles datasets where column
    # names do not match standard business keywords
    # (e.g. "adr" for revenue, "los" for length of stay).
    # --------------------------------------------------
    print("🎯 Running ColumnSelectorAgent")
    column_selector = ColumnSelectorAgent()
    relevant_profiles = column_selector.run(question, column_profiles, dataset_context=dataset_context)

    # Extract LLM target hint if provided
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

    # --------------------------------------------------
    # FIX: Trust the LLM target if it returned a valid column.
    # Only fall back to rule-based scoring if LLM returned None
    # or an unrecognised column name.
    #
    # The old code always ran resolve_best_target_from_profiles which
    # overwrote the LLM's correct answer (e.g. "adr" for a hotel dataset)
    # with a keyword-matched column (e.g. "stays_in_weekend_nights").
    # --------------------------------------------------
    if target is not None and target in columns:
        # LLM chose a valid column — respect it
        pass
    elif llm_target_hint and llm_target_hint in columns:
        # ColumnSelectorAgent provided a hint — use it
        target = llm_target_hint
        planner_reasoning.setdefault("warnings", []).append(
            f"Target set from ColumnSelectorAgent hint: {target}"
        )
    else:
        # LLM failed or returned unknown column — use scored heuristic
        target = resolve_best_target_from_profiles(column_profiles, question)

    if target is None and columns:
        target = columns[0]

    # Driver resolution uses full column_profiles so all columns are available
    drivers = resolve_valid_drivers(
        drivers=drivers,
        column_profiles=column_profiles,
        target=target,
        question=question,
        max_drivers=5
    )

    # Time column resolution
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

    # Ambiguity guard
    if should_defer_ambiguous_question(
        question=question,
        resolved_plan=resolved_plan,
        planner_reasoning=planner_reasoning,
        question_info=question_info
    ):
        print("⚠️ Ambiguous question detected — returning safe exploratory response")
        return build_ambiguous_response(
            df=df,
            question=question,
            question_category=question_category,
            question_goal=question_goal,
            intent=intent,
            resolved_plan=resolved_plan,
            planner_reasoning=planner_reasoning,
            question_history=question_history
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
        "dataset_context": dataset_context
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
                # Guard: skip if dates are epoch (1970) — means they were parsed from integers
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

    # For totals questions lead with the aggregate, not question_goal
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
    """Detect questions asking for a single aggregate total."""
    q = (question or "").lower()
    return any(w in q for w in [
        "total revenue", "total bookings", "total sales", "total profit",
        "total amount", "overall revenue", "overall total",
        "grand total", "sum of", "how much revenue", "how much profit"
    ])


def _is_count_question(question):
    """Detect questions asking for a count of records."""
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

    q_lower = (question or "").lower()
    target_label = format_label(target).lower()

    # Case 1: totals question (e.g. "What is the total revenue?")
    # Lead with the aggregate total, not a segment headline.
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

    # Case 2: count question (e.g. "How many bookings were made each month?")
    # Lead with the total record count, not a segment.
    if _is_count_question(question) and intent not in {"trend_analysis"}:
        row_count = kpis.get("row_count")
        if row_count:
            rows_fmt = format_number(row_count)
            return (
                f"A total of {rows_fmt} records are in the dataset. "
                f"The trend chart above shows how the count varies across time periods."
            )

    # Case 3: binary/rate target + rate-style question.
    # Lead with the aggregate percentage, not a segment headline.
    # e.g. "What is the overall cancellation rate?" → "27.0% (24,020 of 87,380)"
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

    # FIX: use best_headline_segment to get a consistent dimension-segment pair
    # from the most discriminating dimension, rather than mixing segments across dimensions
    best = best_headline_segment(top_bottom_segments, categorical_drivers)
    if best:
        return (
            f"The clearest answer is that {best['segment']} is currently the leading "
            f"{format_label(best['dimension']).lower()} for {format_label(target).lower()}, "
            f"with a measured contribution of {format_number(best.get('total_target'))}."
        )

    # Fallback to flat list when top_bottom_segments not available
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


def _synthesise_date_columns(df: pd.DataFrame) -> pd.DataFrame:
    """
    GENERIC: Find any split year/month/day integer columns and synthesise
    a single full datetime column from them.

    Works for any dataset — not just hotel bookings. Examples:
      hotel:      arrival_date_year + arrival_date_month + arrival_date_day_of_month
      e-commerce: order_year + order_month + order_day
      healthcare: admit_year + admit_month + admit_day
      logistics:  ship_year + ship_month + ship_day

    Detection logic:
    1. Find all integer columns whose name contains 'year' and values are plausible
       calendar years (1900–2100).
    2. For each year column, look for a matching month column and day column by
       checking for columns with the same name prefix or similar suffix pattern.
    3. If found, synthesise a datetime column named <prefix>_date (or 'synthetic_date'
       if no clean prefix). Skip if a full datetime column with the same prefix exists.
    """
    df = df.copy()
    cols_lower = {c: c.lower().strip() for c in df.columns}

    # Normalise column name: strip prefix pattern, return just the semantic part
    def _norm(name):
        return re.sub(r"[_\-\s]+", "_", name.lower().strip())

    # Find all candidate year columns
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

        # Derive the prefix by removing the 'year' suffix/part
        prefix = re.sub(r"_?year_?", "_", year_norm).strip("_")

        # Look for matching month column: same prefix, contains 'month'
        month_col = None
        for col in df.columns:
            n = _norm(col)
            if "month" in n and pd.api.types.is_numeric_dtype(df[col]):
                # Prefix match: either same prefix or just contains 'month'
                col_prefix = re.sub(r"_?month_?.*", "", n).strip("_")
                if col_prefix == prefix or (prefix == "" and "month" in n):
                    month_col = col
                    break

        # Look for matching day column: same prefix, contains 'day'
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

        # Name for the synthesised column
        synth_name = (prefix + "_date").strip("_") if prefix else "synthetic_date"
        # Normalise: replace multiple underscores
        synth_name = re.sub(r"_+", "_", synth_name)

        # Skip if a full datetime column with this name already exists
        already_exists = any(
            c.lower().strip().replace(" ", "_") == synth_name.lower()
            and pd.api.types.is_datetime64_any_dtype(df[c])
            for c in df.columns
        )
        if already_exists:
            continue

        # Skip if a column with this name exists but is not datetime — don't overwrite
        if synth_name in df.columns and not pd.api.types.is_datetime64_any_dtype(df[synth_name]):
            continue

        try:
            synthesised = pd.to_datetime(dict(
                year=pd.to_numeric(df[year_col], errors="coerce"),
                month=pd.to_numeric(df[month_col], errors="coerce"),
                day=pd.to_numeric(df[day_col], errors="coerce")
            ), errors="coerce")

            # Validate: at least 50% non-null and dates span more than 30 days
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

    # Date coercion: only apply to columns containing full date strings.
    # Integer date-part columns (arrival_date_year, arrival_date_month,
    # arrival_date_day_of_month, arrival_date_week_number) must NOT be coerced —
    # pandas interprets the integer as milliseconds since epoch, producing
    # dates like 0001-01-01 or 1970-01-01.
    date_part_keywords = [
        "year", "month", "week_number", "week number",
        "day_of_month", "day of month", "hour", "minute", "second"
    ]

    for col in df.columns:
        col_lower = col.lower().strip()
        if "date" in col_lower or "time" in col_lower:
            if any(kw in col_lower for kw in date_part_keywords):
                continue  # skip integer date-part columns
            if pd.api.types.is_datetime64_any_dtype(df[col]):
                continue  # already datetime
            if pd.api.types.is_numeric_dtype(df[col]):
                continue  # numeric column with date-like name — leave as-is
            df[col] = pd.to_datetime(df[col], errors="coerce")

    # GENERIC: Synthesise a full datetime column from split year/month/day integer columns.
    # This handles any dataset that stores date parts as separate numeric columns
    # (e.g. hotel: arrival_date_year/month/day, e-commerce: order_year/order_month/order_day,
    #  healthcare: admit_year/admit_month/admit_day).
    #
    # Strategy: find the first set of columns whose normalised names contain
    # 'year', 'month', and 'day' respectively, share a common prefix, and
    # are all integer-typed. Synthesise a single datetime column from them.
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

    # FIX: integer columns that look like calendar year values (e.g. arrival_date_year
    # with values 2015, 2016, 2017) were being treated as numeric metrics and then
    # displayed as epoch dates (1970-01-01) in the date coverage section.
    # Detect by checking if all sample values fall within a plausible year range.
    if pd.api.types.is_integer_dtype(series):
        sample_vals = series.dropna().unique()[:20].tolist()
        try:
            if sample_vals and all(1900 <= int(v) <= 2100 for v in sample_vals):
                if any(k in col_norm for k in ["year", "month", "quarter", "week", "day"]):
                    return "datetime"
        except (TypeError, ValueError):
            pass

    # Columns with date/time in the name are treated as datetime dimensions
    # even if they are stored as numeric (e.g. arrival_date_year as int64)
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

    # FIX: year/month integer columns were being flagged as IDs because
    # arrival_date_year has a unique_ratio of ~3/119k which is not actually
    # high, but arrival_date_month has only 12 unique values so this was fine.
    # The real issue was columns like "agent" (integer, ~300 unique values)
    # being treated as IDs. Exclude columns with date-like names from the
    # high-unique-ratio ID detection.
    date_like_names = ["year", "month", "quarter", "week", "day", "date", "time"]
    if any(k in col_norm for k in date_like_names):
        return False

    if unique_ratio >= 0.98 and not pd.api.types.is_datetime64_any_dtype(series):
        if pd.api.types.is_object_dtype(series) or pd.api.types.is_integer_dtype(series):
            return True

    return False


def is_probable_metric_column(col_name, series):
    col_norm = normalize_text(col_name)
    # Expanded to include domain-specific metric column names that appear in
    # non-standard datasets (e.g. hotel, healthcare, logistics)
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
    """
    Fallback target selection using heuristic scoring.
    Only called when the LLM planner did not return a valid column name.
    """
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
    """
    Select the best time column for trend analysis.
    Priority:
    1. Actual datetime64 dtype columns — these have full date precision.
       This includes any synthesised date column regardless of its name.
    2. Date-named non-part columns (contain "date"/"timestamp" but NOT "year"/"month"/"day")
    3. Integer year/month/day components — last resort, produce incomplete period labels

    Detection is fully generic — no dataset-specific column names assumed.
    """
    datetime_candidates = []

    for col in column_profiles:
        name = col["name"]
        norm = normalize_text(name)
        semantic_type = col.get("semantic_type", "unknown")
        is_probable_datetime = bool(col.get("is_probable_datetime", False))
        non_null_pct = float(col.get("non_null_pct", 1.0))
        dtype = str(col.get("dtype", "")).lower()

        score = 0.0

        # Actual datetime64 dtype columns score highest regardless of name
        if "datetime" in dtype:
            score += 12.0
        elif is_probable_datetime:
            score += 5.0
        elif semantic_type == "datetime":
            score += 3.0

        # Full date column names (contain "date"/"timestamp" but NOT a date-part word)
        date_part_words = {"year", "month", "week", "day", "quarter", "hour", "minute", "second"}
        norm_tokens = set(norm.split())
        if "date" in norm and not norm_tokens.intersection(date_part_words):
            score += 4.0
        if "timestamp" in norm:
            score += 3.0
        if "time" in norm and "datetime" not in dtype:
            score += 1.0

        # Integer date-part columns score very low — incomplete period labels
        if norm_tokens.intersection(date_part_words):
            score += 0.5  # last resort only

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
    """
    Returns top segment from the most discriminating AND useful dimension.

    Two-pass approach:
    Pass 1: prefer dimensions where top segment share is 1-80%.
    A dimension where one segment holds >80% (e.g. No Deposit at 95%)
    is not useful as a headline — it shows no real contrast.

    Pass 2: fallback to highest variance dimension if nothing passes.
    """
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

    # Pass 1: skip dominant dimensions (top segment share > 80% or < 1%)
    for dim_name, _ in ranked_dims:
        top_seg = _get_top_seg(dim_name)
        if top_seg is None:
            continue
        share = top_seg.get("share_pct")
        if share is not None and (share > 80 or share < 1):
            continue
        return top_seg

    # Pass 2: fallback — use highest variance dimension regardless
    for dim_name, _ in ranked_dims:
        top_seg = _get_top_seg(dim_name)
        if top_seg is not None:
            return top_seg

    return None


def best_non_placeholder_segment(top_segments):
    """Legacy fallback — used when top_bottom_segments is not populated."""
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