from typing import Dict, Any
from llm.openai_client import OpenAIClient

class AnalyticsBIAgent:
    def __init__(self, context: Dict[str, Any]):
        self.context = context
        self.llm = OpenAIClient()

    def run(self) -> Dict[str, Any]:
        prompt = self._build_prompt()
        doc = self.llm.generate(prompt)
        return {"markdown": doc}

    def _build_prompt(self) -> str:
        return f"""
You are a Senior Analytics Engineer designing the analytics and BI layer.

Inputs:
- Data Model
- Business Requirements
- Storage Layout

Your job:
- Design data marts
- Define metrics and KPIs
- Define semantic layer / metrics layer
- Define BI consumption patterns
- Suggest BI tools and access patterns
- Optimize for self-service analytics

Output MUST be in Markdown with sections:
1. Overview
2. Data Marts Design
3. Metrics & KPIs
4. Semantic / Metrics Layer
5. BI Tools & Access Patterns
6. Performance Considerations
7. Governance & Metric Consistency
8. Risks & Tradeoffs

Business Requirements:
{self.context.get("business_requirements")}

Data Model:
{self.context.get("data_model")}

Storage Layout:
{self.context.get("storage_layout")}
"""