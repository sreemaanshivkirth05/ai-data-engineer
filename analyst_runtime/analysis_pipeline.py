import os
import pandas as pd

from agents.analyst_agents.question_agent import QuestionAgent
from agents.analyst_agents.planner_agent import PlannerAgent
from agents.analyst_agents.analysis_agent import AnalysisAgent
from agents.analyst_agents.visualization_agent import VisualizationAgent
from agents.analyst_agents.narrative_agent import NarrativeAgent
from agents.analyst_agents.storytelling_agent import StorytellingAgent
from agents.analyst_agents.kpi_agent import KPIAgent


def run_analysis_pipeline(dataset_path, question):
    print("🚀 ANALYSIS PIPELINE STARTED")
    print(f"📂 Loading dataset: {dataset_path}")

    os.makedirs("outputs/analyst/charts", exist_ok=True)

    # ==========================================================
    # 1 LOAD DATASET
    # ==========================================================
    if dataset_path.endswith(".csv"):
        df = pd.read_csv(dataset_path)
    elif dataset_path.endswith(".xlsx"):
        df = pd.read_excel(dataset_path)
    else:
        raise ValueError("Unsupported dataset format")

    if not isinstance(df, pd.DataFrame):
        raise ValueError("Dataset failed to load")

    print(f"✅ Dataset loaded — {len(df):,} rows × {len(df.columns)} columns")

    # ==========================================================
    # 1.5 BASIC PREPROCESSING
    # ==========================================================
    df = preprocess_dataframe(df)
    columns = df.columns.tolist()

    print(f"✅ Preprocessing complete — columns: {columns}")

    # ==========================================================
    # 2 QUESTION UNDERSTANDING
    # ==========================================================
    print("🧠 Running QuestionAgent")

    question_agent = QuestionAgent()
    question_info = question_agent.run(question)

    intent = question_info["intent"]
    show_kpis = question_info.get("show_kpis", False)

    print(f"✅ Intent: {intent} | Show KPIs: {show_kpis}")

    # ==========================================================
    # 3 ANALYSIS PLANNING
    # ==========================================================
    print("📊 Running PlannerAgent")

    planner = PlannerAgent()
    plan = planner.run(question, columns)

    target = plan.get("target")
    drivers = plan.get("drivers", [])

    # fallback target selection
    if target is None or target not in columns:
        numeric_cols = df.select_dtypes(include=["int64", "float64", "int32", "float32"]).columns.tolist()
        if numeric_cols:
            target = numeric_cols[0]
        else:
            target = columns[-1]

    print(f"✅ Target: {target} | Drivers: {drivers}")

    # ==========================================================
    # 4 KPI ENGINE
    # ==========================================================
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

    # ==========================================================
    # 5 ANALYSIS ENGINE
    # ==========================================================
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

    # ==========================================================
    # 6 VISUALIZATION ENGINE
    # ==========================================================
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
        print(f"⚠️  VisualizationAgent failed: {e}")
        charts = []

    print(f"✅ {len(charts)} chart(s) generated")

    # ==========================================================
    # 7 NARRATIVE ENGINE
    # ==========================================================
    print("📝 Running NarrativeAgent")

    narrative = None
    try:
        narrative_agent = NarrativeAgent()
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

    # ==========================================================
    # 8 STORYTELLING ENGINE
    # ==========================================================
    print("📚 Running StorytellingAgent")

    story = None
    try:
        storytelling_agent = StorytellingAgent()
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
        "show_kpis": show_kpis,
        "target": target,
        "drivers": drivers,
        "kpis": kpis,
        "analysis": analysis_results,
        "charts": charts,
        "narrative": narrative,
        "story": story
    }


def preprocess_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    # clean column names
    df.columns = [str(col).strip() for col in df.columns]

    # likely money columns
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

    # likely numeric columns
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

    # likely date columns
    for col in df.columns:
        col_lower = col.lower().strip()
        if "date" in col_lower or "time" in col_lower:
            df[col] = pd.to_datetime(df[col], errors="coerce")

    return df