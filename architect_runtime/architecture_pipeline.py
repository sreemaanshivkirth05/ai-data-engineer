import os

from agents.architect_agents.security_governance_agent import SecurityGovernanceAgent
from agents.architect_agents.cost_estimation_agent import CostEstimationAgent
from agents.architect_agents.architecture_diagram_agent import ArchitectureDiagramAgent
from agents.architect_agents.mermaid_ai_agent import MermaidAIAgent
from agents.architect_agents.pipeline_architect import PipelineArchitectAgent


def run_architecture_pipeline(requirements_text, schemas_text):
    os.makedirs("outputs/architect", exist_ok=True)

    context = {
        "business_requirements": requirements_text,
        "requirements_analysis": requirements_text,
        "source_schemas": schemas_text,
        "schemas": schemas_text,
        "dataset_profile": {
            "row_count": 1000000,
            "columns": []
        },
        "data_contract": f"Source schema summary:\n{schemas_text}",
        "ingestion_strategy": "Batch ingestion via Airflow or streaming via Kafka depending on source requirements.",
        "storage_layout": "Bronze / Silver / Gold architecture using a lakehouse design on AWS.",
        "orchestration": "Airflow DAG orchestration with monitoring, retries, and backfills.",
        "analytics_bi": "Serve curated gold data to BI dashboards and analytics users."
    }

    # -------------------------------------------------
    # Agent 1 — Pipeline Architecture Design
    # -------------------------------------------------
    pipeline_agent = PipelineArchitectAgent()
    pipeline_result = pipeline_agent.run(context)

    context["pipeline_architecture"] = pipeline_result["markdown"]

    with open("outputs/architect/pipeline_architecture.md", "w", encoding="utf-8") as f:
        f.write(context["pipeline_architecture"])

    # -------------------------------------------------
    # Agent 2 — Security & Governance
    # -------------------------------------------------
    security_agent = SecurityGovernanceAgent(context)
    security_result = security_agent.run()

    context["security_governance"] = security_result["markdown"]

    with open("outputs/architect/security_governance.md", "w", encoding="utf-8") as f:
        f.write(context["security_governance"])

    # -------------------------------------------------
    # Agent 3 — Cost Estimation
    # -------------------------------------------------
    cost_agent = CostEstimationAgent(context)
    cost_result = cost_agent.run()

    context["cost_estimation"] = cost_result["markdown"]

    with open("outputs/architect/cost_estimate.md", "w", encoding="utf-8") as f:
        f.write(context["cost_estimation"])

    # -------------------------------------------------
    # Agent 4 — Architecture Diagram Generation
    # -------------------------------------------------
    diagram_agent = ArchitectureDiagramAgent(context)
    diagram_result = diagram_agent.run()

    context["architecture_diagram"] = diagram_result["markdown"]

    with open("outputs/architect/architecture_diagram.md", "w", encoding="utf-8") as f:
        f.write(context["architecture_diagram"])

    # -------------------------------------------------
    # Agent 5 — Mermaid Diagram Code
    # -------------------------------------------------
    mermaid_agent = MermaidAIAgent(context)
    mermaid_result = mermaid_agent.run()

    context["mermaid_diagram"] = mermaid_result["markdown"]

    with open("outputs/architect/architecture_mermaid.md", "w", encoding="utf-8") as f:
        f.write(context["mermaid_diagram"])

    return {
        "status": "success",
        "pipeline_architecture": context["pipeline_architecture"],
        "security": context["security_governance"],
        "cost": context["cost_estimation"],
        "diagram": context["architecture_diagram"],
        "mermaid": context["mermaid_diagram"]
    }