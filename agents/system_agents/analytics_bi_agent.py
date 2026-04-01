from typing import Dict, Any, Optional
from llm.openai_client import OpenAIClient


class AnalyticsBIAgent:
    """
    Designs the Analytics and Business Intelligence layer for the data platform.
    Recommends BI tools, semantic layer design, KPI definitions, and
    self-service analytics patterns based on the full pipeline context.
    """

    def __init__(self, context: Dict[str, Any], rag_context: Optional[str] = None):
        self.context = context
        self.rag_context = rag_context or ""
        self.llm = OpenAIClient()

    def run(self) -> Dict[str, Any]:
        prompt = self._build_prompt()
        doc = self.llm.generate(prompt)
        return {"markdown": doc}

    def _build_prompt(self) -> str:
        rag_block = f"{self.rag_context}\n\n" if self.rag_context else ""

        return f"""{rag_block}You are a Senior Analytics Engineer designing the Analytics and BI layer
for a production data platform.

You are given the full pipeline design, data model, and business requirements.

Your job:
- Recommend BI tools appropriate to the domain and team size
- Design the semantic layer (metrics, dimensions, KPIs)
- Define the gold/serving layer tables that power dashboards
- Define self-service analytics patterns for business users
- Recommend dashboard structure and key reports
- Define data freshness SLAs for BI consumers
- Call out risks and tradeoffs

Output MUST be in Markdown with sections:
1. Overview
2. BI Tool Recommendation (with justification)
3. Semantic Layer Design (metrics, dimensions, hierarchies)
4. Key KPIs and Business Metrics
5. Serving Layer Tables (gold layer structure for BI)
6. Dashboard & Report Structure
7. Self-Service Analytics Approach
8. Data Freshness SLAs
9. Risks & Tradeoffs

Business Requirements:
{self.context.get("business_requirements", "")}

Data Model:
{self.context.get("data_model", "")}

Storage Layout:
{self.context.get("storage_layout", "")}

Pipeline Design:
{self.context.get("pipeline_design", "")}
"""