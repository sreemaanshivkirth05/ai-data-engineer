from datetime import datetime
import os
from typing import Dict, Any

from llm.openai_client import OpenAIClient

from agents.engineer_agents.dataset_profiler import DatasetProfilerAgent
from agents.engineer_agents.schema_contract_agent import SchemaContractAgent
from agents.engineer_agents.ingestion_strategy_agent import IngestionStrategyAgent
from agents.engineer_agents.storage_layout_agent import StorageLayoutAgent
from agents.engineer_agents.orchestration_agent import OrchestrationAgent

from agents.architect_agents.security_governance_agent import SecurityGovernanceAgent
from agents.architect_agents.cost_estimation_agent import CostEstimationAgent
from agents.architect_agents.mermaid_ai_agent import MermaidAIAgent

from agents.system_agents.analytics_bi_agent import AnalyticsBIAgent
from agents.system_agents.reviewer_agent import ReviewerAgent
from agents.system_agents.validator_agent import ValidatorAgent

# Optional dataset visualization agent
try:
    from agents.analyst_agents.dataset_visualization_agent import DatasetVisualizationAgent
    HAS_DATASET_VIZ = True
except Exception:
    HAS_DATASET_VIZ = False


# -----------------------
# Helpers
# -----------------------
def log(msg: str):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)


def safe_read_file(path: str, default: str = "") -> str:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read().strip()
    except FileNotFoundError:
        return default


def ensure_output_dirs():
    os.makedirs("outputs", exist_ok=True)
    os.makedirs("outputs/engineer", exist_ok=True)
    os.makedirs("outputs/architect", exist_ok=True)
    os.makedirs("outputs/analyst", exist_ok=True)
    os.makedirs("outputs/analyst/charts", exist_ok=True)


def write_output(filename: str, content: str):
    ensure_output_dirs()
    with open(f"outputs/{filename}", "w", encoding="utf-8") as f:
        f.write(content)


# -----------------------
# Main Orchestrator
# -----------------------
def run_full_pipeline(
    dataset_path: str,
    requirements_text: str = "",
    schemas_text: str = ""
) -> Dict[str, Any]:
    """
    Unified AI Data Platform pipeline.
    Accepts inputs dynamically from API/UI and returns structured output.
    Also writes artifacts to /outputs for demo and download purposes.
    """

    log("🚀 Starting Unified Multi-Agent AI Data Platform Pipeline")
    ensure_output_dirs()

    # LLMs
    design_llm = OpenAIClient()
    _ = OpenAIClient(model="gpt-4.1")  # reserved for review-style flows if needed later

    # -----------------------
    # Load optional system files
    # -----------------------
    log("📥 Loading system rules and skills...")
    system_rules = safe_read_file("system/SYSTEM.md", "Follow best practices for data engineering, analytics, and architecture.")
    skill_pipeline = safe_read_file("skills/good_pipeline_design.md", "Design robust, scalable, and production-ready data pipelines.")
    skill_model = safe_read_file("skills/good_data_model.md", "Design practical analytical data models with clear grains and keys.")

    # -----------------------
    # Shared context
    # -----------------------
    context: Dict[str, Any] = {
        "business_requirements": requirements_text or "",
        "source_schemas": schemas_text or "",
        "dataset_path": dataset_path
    }

    # =========================================================
    # Agent 0: Dataset Profiler
    # =========================================================
    log("▶️ Running Dataset Profiler Agent...")
    profiler = DatasetProfilerAgent(dataset_path)
    profile_result = profiler.run()

    write_output("dataset_profile.md", profile_result["markdown"])
    context["dataset_profile"] = profile_result["profile"]
    context["dataset_profile_markdown"] = profile_result["markdown"]
    log("✅ Dataset Profiler Agent completed.")

    # =========================================================
    # Agent 0.5: Dataset Visualization Agent (optional)
    # =========================================================
    context["dataset_charts"] = []
    if HAS_DATASET_VIZ:
        try:
            log("▶️ Running Dataset Visualization Agent...")
            viz_agent = DatasetVisualizationAgent(dataset_path)
            viz_result = viz_agent.run()
            write_output("dataset_charts.md", viz_result.get("markdown", ""))
            context["dataset_charts"] = viz_result.get("charts", [])
            log("✅ Dataset Visualization Agent completed.")
        except Exception as e:
            log(f"⚠️ Dataset Visualization Agent skipped: {e}")

    # =========================================================
    # Agent 1: Schema & Data Contracts
    # =========================================================
    log("▶️ Running Schema & Data Contracts Agent...")
    schema_agent = SchemaContractAgent(context["dataset_profile"])
    schema_result = schema_agent.run()

    write_output("data_contract.md", schema_result["markdown"])
    context["data_contract"] = schema_result["markdown"]
    log("✅ Schema & Data Contracts Agent completed.")

    # =========================================================
    # Build combined user input for LLM design agents
    # =========================================================
    user_input = f"""
# Business Requirements
{requirements_text}

# Source Schemas
{schemas_text}

# Dataset Profile
{profile_result["markdown"]}

# Data Contract Draft
{schema_result["markdown"]}
"""

    # =========================================================
    # Agent 2: Requirements Interpreter
    # =========================================================
    log("▶️ Running Requirements Interpreter Agent...")
    req_agent_text = safe_read_file(
        "agents/requirements_interpreter.txt",
        """You are the Requirements Interpreter agent.
Read the business requirements and source schemas.
Extract business goals, key metrics, core entities, data sources, granularity, assumptions, and open questions."""
    )

    prompt_1 = f"""
SYSTEM RULES:
{system_rules}

AGENT ROLE:
{req_agent_text}

SKILL: GOOD PIPELINE DESIGN:
{skill_pipeline}

SKILL: GOOD DATA MODEL:
{skill_model}

USER INPUT:
{user_input}

TASK:
Produce the structured requirements analysis as instructed.
"""

    requirements_analysis = design_llm.generate(prompt_1)
    write_output("requirements_analysis.md", requirements_analysis)
    context["requirements_analysis"] = requirements_analysis
    log("✅ Requirements Interpreter Agent completed.")

    # =========================================================
    # Agent 3: Ingestion Strategy
    # =========================================================
    log("▶️ Running Ingestion Strategy Agent...")
    ingestion_agent = IngestionStrategyAgent(context)
    ingestion_result = ingestion_agent.run()

    write_output("ingestion_strategy.md", ingestion_result["markdown"])
    context["ingestion_strategy"] = ingestion_result["markdown"]
    log("✅ Ingestion Strategy Agent completed.")

    # =========================================================
    # Agent 4: Storage & Table Layout
    # =========================================================
    log("▶️ Running Storage Layout Agent...")
    storage_agent = StorageLayoutAgent(context)
    storage_result = storage_agent.run()

    write_output("storage_layout.md", storage_result["markdown"])
    context["storage_layout"] = storage_result["markdown"]
    log("✅ Storage Layout Agent completed.")

    # =========================================================
    # Agent 5: Orchestration & Scheduling
    # =========================================================
    log("▶️ Running Orchestration Agent...")
    orchestration_agent = OrchestrationAgent(context)
    orchestration_result = orchestration_agent.run()

    write_output("orchestration.md", orchestration_result["markdown"])
    context["orchestration"] = orchestration_result["markdown"]
    log("✅ Orchestration Agent completed.")

    # =========================================================
    # Agent 6: Security & Governance
    # =========================================================
    log("▶️ Running Security & Governance Agent...")
    security_agent = SecurityGovernanceAgent(context)
    security_result = security_agent.run()

    write_output("security_governance.md", security_result["markdown"])
    context["security_governance"] = security_result["markdown"]
    log("✅ Security & Governance Agent completed.")

    # =========================================================
    # Agent 7: Pipeline Architect
    # =========================================================
    log("▶️ Running Pipeline Architect Agent...")
    pipeline_agent_text = safe_read_file(
        "agents/pipeline_architect.txt",
        """You are the Pipeline Architect agent.
Design the end-to-end data pipeline architecture including sources, ingestion, processing, storage, orchestration, serving, and monitoring."""
    )

    prompt_2 = f"""
SYSTEM RULES:
{system_rules}

AGENT ROLE:
{pipeline_agent_text}

INPUT: REQUIREMENTS ANALYSIS:
{context["requirements_analysis"]}

INPUT: INGESTION STRATEGY:
{context["ingestion_strategy"]}

INPUT: STORAGE LAYOUT:
{context["storage_layout"]}

INPUT: ORCHESTRATION:
{context["orchestration"]}

TASK:
Design the data pipeline architecture as instructed.
"""

    pipeline_design = design_llm.generate(prompt_2)
    write_output("pipeline_design.md", pipeline_design)
    context["pipeline_design"] = pipeline_design
    log("✅ Pipeline Architect Agent completed.")

    # =========================================================
    # Agent 8: Data Modeler
    # =========================================================
    log("▶️ Running Data Modeler Agent...")
    data_modeler_text = safe_read_file(
        "agents/data_modeler.txt",
        """You are the Data Modeler agent.
Design the analytical data model, fact tables, dimension tables, grains, keys, relationships, and assumptions."""
    )

    prompt_3 = f"""
SYSTEM RULES:
{system_rules}

AGENT ROLE:
{data_modeler_text}

INPUT: PIPELINE DESIGN:
{context["pipeline_design"]}

INPUT: DATA CONTRACT:
{context["data_contract"]}

TASK:
Design the analytical data model as instructed.
"""

    data_model = design_llm.generate(prompt_3)
    write_output("data_model.md", data_model)
    context["data_model"] = data_model
    log("✅ Data Modeler Agent completed.")

    # =========================================================
    # Agent 9: Data Quality Engineer
    # =========================================================
    log("▶️ Running Data Quality Engineer Agent...")
    dq_agent_text = safe_read_file(
        "agents/data_quality_engineer.txt",
        """You are the Data Quality Engineer agent.
Define data quality checks, SLAs, freshness expectations, critical tables/columns, monitoring, alerting, failure handling, and risks."""
    )

    prompt_4 = f"""
SYSTEM RULES:
{system_rules}

AGENT ROLE:
{dq_agent_text}

INPUT: PIPELINE DESIGN:
{context["pipeline_design"]}

INPUT: DATA MODEL:
{context["data_model"]}

INPUT: DATA CONTRACT:
{context["data_contract"]}

TASK:
Design the data quality strategy and checks as instructed.
"""

    dq_plan = design_llm.generate(prompt_4)
    write_output("data_quality_plan.md", dq_plan)
    context["data_quality_plan"] = dq_plan
    log("✅ Data Quality Engineer Agent completed.")

    # =========================================================
    # Agent 10: Performance & Cost Optimization
    # =========================================================
    log("▶️ Running Performance & Cost Optimization Agent...")
    perf_agent_text = safe_read_file(
        "agents/performance_cost_optimizer.txt",
        """You are the Performance & Cost Optimization agent.
Review performance bottlenecks, storage and compute optimizations, query efficiency, cost strategies, tradeoffs, and final recommendations."""
    )

    prompt_5 = f"""
SYSTEM RULES:
{system_rules}

AGENT ROLE:
{perf_agent_text}

INPUT: PIPELINE DESIGN:
{context["pipeline_design"]}

INPUT: DATA MODEL:
{context["data_model"]}

INPUT: DATA QUALITY PLAN:
{context["data_quality_plan"]}

INPUT: STORAGE LAYOUT:
{context["storage_layout"]}

TASK:
Review the system and propose performance and cost optimizations as instructed.
"""

    perf_review = design_llm.generate(prompt_5)
    write_output("performance_review.md", perf_review)
    context["performance_review"] = perf_review
    log("✅ Performance & Cost Optimization Agent completed.")

    # =========================================================
    # Agent 11: Analytics / BI Layer
    # =========================================================
    log("▶️ Running Analytics / BI Agent...")
    analytics_agent = AnalyticsBIAgent(context)
    analytics_result = analytics_agent.run()

    write_output("analytics_bi.md", analytics_result["markdown"])
    context["analytics_bi"] = analytics_result["markdown"]
    log("✅ Analytics / BI Agent completed.")

    # =========================================================
    # Agent 12: Mermaid Architecture Diagram
    # =========================================================
    log("▶️ Running Mermaid AI Diagram Agent...")
    mermaid_agent = MermaidAIAgent(context)
    diagram_result = mermaid_agent.run()

    write_output("architecture_diagram.md", diagram_result["markdown"])
    context["architecture_diagram"] = diagram_result["markdown"]
    log("✅ Mermaid AI Diagram Agent completed.")

    # =========================================================
    # Agent 13: Documentation Writer
    # =========================================================
    log("▶️ Running Documentation Writer Agent...")
    doc_agent_text = safe_read_file(
        "agents/documentation_writer.txt",
        """You are the Documentation & Architecture Writer agent.
Produce a clean, professional README-style document explaining the system, architecture, design decisions, workflow, and future improvements."""
    )

    prompt_6 = f"""
SYSTEM RULES:
{system_rules}

AGENT ROLE:
{doc_agent_text}

INPUT: REQUIREMENTS ANALYSIS:
{context["requirements_analysis"]}

INPUT: PIPELINE DESIGN:
{context["pipeline_design"]}

INPUT: DATA MODEL:
{context["data_model"]}

INPUT: DATA QUALITY PLAN:
{context["data_quality_plan"]}

INPUT: PERFORMANCE REVIEW:
{context["performance_review"]}

INPUT: DATA CONTRACT:
{context["data_contract"]}

INPUT: INGESTION STRATEGY:
{context["ingestion_strategy"]}

INPUT: STORAGE LAYOUT:
{context["storage_layout"]}

INPUT: ORCHESTRATION:
{context["orchestration"]}

INPUT: SECURITY & GOVERNANCE:
{context["security_governance"]}

INPUT: ANALYTICS / BI:
{context["analytics_bi"]}

TASK:
Generate a complete, professional README-style documentation for this project.
"""

    documentation = design_llm.generate(prompt_6)
    write_output("README.md", documentation)
    context["documentation"] = documentation
    log("✅ Documentation Writer Agent completed.")

    # =========================================================
    # Agent 14: Reviewer
    # =========================================================
    log("▶️ Running Reviewer Agent...")
    reviewer_agent = ReviewerAgent(context, model="gpt-4.1")
    review_result = reviewer_agent.run()

    write_output("reviewer_report.md", review_result["markdown"])
    context["reviewer_report"] = review_result["markdown"]
    log("✅ Reviewer Agent completed.")

    # =========================================================
    # Agent 15: Rule-Based Validator
    # =========================================================
    log("▶️ Running Rule-Based Validator Agent...")
    validator_agent = ValidatorAgent(context)
    validation_result = validator_agent.run()

    write_output("validation_report.md", validation_result["markdown"])
    context["validation_report"] = validation_result["markdown"]
    log("✅ Rule-Based Validator Agent completed.")

    # =========================================================
    # Agent 16: Cost Estimation Agent
    # =========================================================
    log("▶️ Running Cost Estimation Agent...")
    cost_agent = CostEstimationAgent(context)
    cost_result = cost_agent.run()

    write_output("cost_estimate.md", cost_result["markdown"])
    context["cost_estimate"] = cost_result
    log("✅ Cost Estimation Agent completed.")

    log("🎉 Unified Multi-Agent AI Data Platform Pipeline completed successfully.")

    return {
        "status": "success",
        "dataset_profile": profile_result,
        "data_contract": schema_result["markdown"],
        "requirements_analysis": context["requirements_analysis"],
        "ingestion_strategy": context["ingestion_strategy"],
        "storage_layout": context["storage_layout"],
        "orchestration": context["orchestration"],
        "security_governance": context["security_governance"],
        "pipeline_design": context["pipeline_design"],
        "data_model": context["data_model"],
        "data_quality_plan": context["data_quality_plan"],
        "performance_review": context["performance_review"],
        "analytics_bi": context["analytics_bi"],
        "architecture_diagram": context["architecture_diagram"],
        "documentation": context["documentation"],
        "reviewer_report": context["reviewer_report"],
        "validation_report": context["validation_report"],
        "cost_estimate": cost_result,
        "dataset_charts": context.get("dataset_charts", [])
    }


if __name__ == "__main__":
    # Example local run
    # Update these paths/values if you want to test directly
    result = run_full_pipeline(
        dataset_path="inputs/sample.csv",
        requirements_text="Build a modern analytics platform for business reporting.",
        schemas_text="sales(id, region, product, revenue, date)"
    )
    print(result["status"])