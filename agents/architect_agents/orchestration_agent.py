from typing import Dict, Any, Optional
from llm.openai_client import OpenAIClient


class OrchestrationAgent:
    def __init__(self, context: Dict[str, Any], rag_context: Optional[str] = None):
        self.context = context
        self.rag_context = rag_context or ""
        self.llm = OpenAIClient()

    def run(self) -> Dict[str, Any]:
        prompt = self._build_prompt()
        doc = self.llm.generate(prompt)
        return {"markdown": doc}

    def _build_prompt(self) -> str:
        return f"""{self.rag_context}

You are a Senior Data Engineer designing orchestration and scheduling for a
production data platform.

You have been given retrieved reference architecture patterns above.
Choose the orchestration approach (Airflow, Step Functions, Prefect, Databricks Workflows,
dbt Cloud, etc.) that best fits the ingestion strategy and complexity level
indicated by the reference patterns. Cite your pattern choice.

Your job:
- Design DAG/workflow structure
- Define task dependencies
- Define retries, backfills, SLAs
- Define monitoring hooks
- Define failure handling strategy

Output MUST be in Markdown with sections:
1. Overview & Tool Choice (cite which reference pattern and why)
2. Orchestration Tool Recommendation with justification
3. DAG / Workflow Design (with task breakdown)
4. Task Dependencies (include a dependency diagram or table)
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