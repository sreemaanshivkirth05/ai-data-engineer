from typing import Dict, Any
from llm.openai_client import OpenAIClient

class OrchestrationAgent:
    def __init__(self, context: Dict[str, Any]):
        self.context = context
        self.llm = OpenAIClient()

    def run(self) -> Dict[str, Any]:
        prompt = self._build_prompt()
        doc = self.llm.generate(prompt)
        return {"markdown": doc}

    def _build_prompt(self) -> str:
        return f"""
You are a Senior Data Engineer designing orchestration and scheduling for a production data platform.

Inputs:
- Ingestion Strategy
- Storage Layout
- Data Quality Requirements

Your job:
- Design DAG/workflow (Airflow or Step Functions)
- Define task dependencies
- Define retries, backfills, SLAs
- Define monitoring hooks
- Define failure handling strategy

Output MUST be in Markdown with sections:
1. Overview
2. Orchestration Tool Choice
3. DAG / Workflow Design
4. Task Dependencies
5. Scheduling & SLAs
6. Retries, Backfills & Recovery
7. Monitoring & Observability
8. Risks & Tradeoffs

Ingestion Strategy:
{self.context.get("ingestion_strategy")}

Storage Layout:
{self.context.get("storage_layout")}

Data Quality Plan:
{self.context.get("data_quality_plan")}
"""