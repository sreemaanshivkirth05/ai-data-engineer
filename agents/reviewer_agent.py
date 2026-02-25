from typing import Dict, Any
from llm.openai_client import OpenAIClient

class ReviewerAgent:
    def __init__(self, context: Dict[str, Any], model: str = "gpt-4.1"):
        self.context = context
        self.llm = OpenAIClient(model=model)

    def run(self) -> Dict[str, Any]:
        prompt = self._build_prompt()
        review = self.llm.generate(prompt)
        return {"markdown": review}

    def _build_prompt(self) -> str:
        return f"""
You are a Principal Data Architect reviewing a proposed data platform design.

Your job:
- Critically review the full design
- Identify risks, gaps, and bad assumptions
- Identify scalability issues
- Identify cost risks
- Suggest concrete improvements
- Call out missing components

Output MUST be in Markdown with sections:
1. Overall Assessment
2. Strengths
3. Weaknesses & Risks
4. Scalability Review
5. Cost Review
6. Security & Governance Gaps
7. Missing Pieces
8. Actionable Recommendations

Full Design Context:
Dataset Profile:
{self.context.get("dataset_profile")}

Data Contract:
{self.context.get("data_contract")}

Ingestion:
{self.context.get("ingestion_strategy")}

Storage:
{self.context.get("storage_layout")}

Orchestration:
{self.context.get("orchestration")}

Analytics:
{self.context.get("analytics_bi")}

Security:
{self.context.get("security_governance")}
"""