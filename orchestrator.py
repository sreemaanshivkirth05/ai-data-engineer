from datetime import datetime
from llm.openai_client import OpenAIClient

# Deterministic / Python agents
from agents.dataset_profiler import DatasetProfilerAgent
from agents.schema_contract_agent import SchemaContractAgent
from agents.ingestion_strategy_agent import IngestionStrategyAgent
from agents.storage_layout_agent import StorageLayoutAgent
from agents.orchestration_agent import OrchestrationAgent
from agents.security_governance_agent import SecurityGovernanceAgent
from agents.analytics_bi_agent import AnalyticsBIAgent
from agents.architecture_diagram_agent import ArchitectureDiagramAgent
from agents.reviewer_agent import ReviewerAgent

# Diagram renderer (API-based)
from utils.diagram_renderer import render_mermaid_via_api


# -----------------------
# Helpers
# -----------------------
def log(msg: str):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)

def read_file(path: str) -> str:
    with open(path, "r", encoding="utf-8") as f:
        return f.read().strip()

def write_output(filename: str, content: str):
    with open(f"outputs/{filename}", "w", encoding="utf-8") as f:
        f.write(content)


# -----------------------
# Main Orchestrator
# -----------------------
def run():
    log("🚀 Starting Multi-Agent AI Data Engineer Pipeline")

    # LLMs
    design_llm = OpenAIClient()
    review_llm = OpenAIClient(model="gpt-4.1")

    # -----------------------
    # Load shared system + skills
    # -----------------------
    log("📥 Loading system rules and skills...")
    system_rules = read_file("system/SYSTEM.md")
    skill_pipeline = read_file("skills/good_pipeline_design.md")
    skill_model = read_file("skills/good_data_model.md")

    # -----------------------
    # Load inputs
    # -----------------------
    log("📥 Loading user inputs...")
    requirements_text = read_file("inputs/requirements.md")
    schemas_text = read_file("inputs/schemas.md")
    dataset_path = read_file("inputs/dataset_path.txt")

    # Shared context between agents
    context = {}
    context["business_requirements"] = requirements_text
    context["source_schemas"] = schemas_text

    # =========================================================
    # Agent 0: Dataset Profiler
    # =========================================================
    log("▶️ Running Dataset Profiler Agent...")
    profiler = DatasetProfilerAgent(dataset_path)
    profile_result = profiler.run()
    write_output("dataset_profile.md", profile_result["markdown"])
    context["dataset_profile"] = profile_result["profile"]
    log("✅ Dataset Profiler Agent completed.")

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
    req_agent = read_file("agents/requirements_interpreter.txt")

    prompt_1 = f"""
SYSTEM RULES:
{system_rules}

AGENT ROLE:
{req_agent}

SKILL: GOOD PIPELINE DESIGN:
{skill_pipeline}

SKILL: GOOD DATA MODEL:
{skill_model}

USER INPUT:
{user_input}

TASK:
Produce the structured requirements analysis as instructed.
"""

    architecture = design_llm.generate(prompt_1)
    write_output("architecture.md", architecture)
    context["requirements_analysis"] = architecture
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
    pipeline_agent = read_file("agents/pipeline_architect.txt")

    prompt_2 = f"""
SYSTEM RULES:
{system_rules}

AGENT ROLE:
{pipeline_agent}

INPUT: REQUIREMENTS ANALYSIS:
{architecture}

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
    data_modeler_agent = read_file("agents/data_modeler.txt")

    prompt_3 = f"""
SYSTEM RULES:
{system_rules}

AGENT ROLE:
{data_modeler_agent}

INPUT: PIPELINE DESIGN:
{pipeline_design}

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
    dq_agent = read_file("agents/data_quality_engineer.txt")

    prompt_4 = f"""
SYSTEM RULES:
{system_rules}

AGENT ROLE:
{dq_agent}

INPUT: PIPELINE DESIGN:
{pipeline_design}

INPUT: DATA MODEL:
{data_model}

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
    perf_agent = read_file("agents/performance_cost_optimizer.txt")

    prompt_5 = f"""
SYSTEM RULES:
{system_rules}

AGENT ROLE:
{perf_agent}

INPUT: PIPELINE DESIGN:
{pipeline_design}

INPUT: DATA MODEL:
{data_model}

INPUT: DATA QUALITY PLAN:
{dq_plan}

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
    # Agent 12: Architecture Diagram Agent
    # =========================================================
    log("▶️ Running Architecture Diagram Agent...")
    diagram_agent = ArchitectureDiagramAgent(context)
    diagram_result = diagram_agent.run()
    write_output("architecture_diagram.md", diagram_result["markdown"])
    context["architecture_diagram"] = diagram_result["markdown"]
    log("✅ Architecture Diagram Agent completed.")

    # Render Mermaid -> PNG
    log("🖼️ Rendering architecture diagram via Mermaid API...")
    try:
        render_mermaid_via_api(
            context["architecture_diagram"],
            "outputs/architecture_diagram.png"
        )
        log("✅ Architecture diagram rendered to outputs/architecture_diagram.png")
    except Exception as e:
        log(f"⚠️ Failed to render architecture diagram: {e}")

    # =========================================================
    # Agent 13: Documentation Writer
    # =========================================================
    log("▶️ Running Documentation Writer Agent...")
    doc_agent = read_file("agents/documentation_writer.txt")

    prompt_6 = f"""
SYSTEM RULES:
{system_rules}

AGENT ROLE:
{doc_agent}

INPUT: REQUIREMENTS ANALYSIS:
{architecture}

INPUT: PIPELINE DESIGN:
{pipeline_design}

INPUT: DATA MODEL:
{data_model}

INPUT: DATA QUALITY PLAN:
{dq_plan}

INPUT: PERFORMANCE REVIEW:
{perf_review}

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
    # Agent 14: Reviewer / Validator
    # =========================================================
    log("▶️ Running Reviewer / Validator Agent...")
    reviewer_agent = ReviewerAgent(context, model="gpt-4.1")
    review_result = reviewer_agent.run()
    write_output("reviewer_report.md", review_result["markdown"])
    context["reviewer_report"] = review_result["markdown"]
    log("✅ Reviewer / Validator Agent completed.")

    log("🎉 Multi-agent AI Data Engineer pipeline completed successfully.")


if __name__ == "__main__":
    run()