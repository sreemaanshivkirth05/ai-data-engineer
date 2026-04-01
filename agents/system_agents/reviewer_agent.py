from typing import Dict, Any, Optional
from llm.openai_client import OpenAIClient


class ReviewerAgent:
    """
    Senior architecture reviewer. Reads all pipeline outputs and produces
    a structured critique covering correctness, completeness, risks,
    and concrete recommendations for improvement.
    """

    def __init__(
        self,
        context: Dict[str, Any],
        model: Optional[str] = None,
        rag_context: Optional[str] = None
    ):
        self.context = context
        self.rag_context = rag_context or ""
        self.llm = OpenAIClient(model=model) if model else OpenAIClient()

    def run(self) -> Dict[str, Any]:
        prompt = self._build_prompt()
        doc = self.llm.generate(prompt)
        return {"markdown": doc}

    def _build_prompt(self) -> str:
        rag_block = f"{self.rag_context}\n\n" if self.rag_context else ""

        return f"""{rag_block}You are a Principal Data Architect conducting a senior technical review
of a full data platform design.

You have been given every output produced by the pipeline agents below.
Your job is to review the ENTIRE design holistically and produce a structured
critique that a real engineering team could act on.

Review criteria:
- Correctness: Are the design decisions technically sound?
- Completeness: Are there gaps, missing components, or unanswered questions?
- Consistency: Do the layers (ingestion → storage → model → BI) align?
- Scalability: Will this design hold as data volume grows 10x?
- Operability: Is it maintainable by a real team in production?
- Cost: Are there obvious cost risks or inefficiencies?
- Security: Are compliance and access control requirements met?

Output MUST be in Markdown with sections:
1. Executive Summary (3-5 sentence overall verdict)
2. Strengths (what the design does well)
3. Critical Issues (must-fix before production)
4. Recommendations (nice-to-have improvements)
5. Consistency Checks (mismatches between layers)
6. Risk Register (top 5 risks with likelihood and impact)
7. Final Score (out of 10 with justification)

Pipeline outputs to review:

Requirements Analysis:
{self.context.get("requirements_analysis", "")[:800]}

Data Contract:
{self.context.get("data_contract", "")[:600]}

Ingestion Strategy:
{self.context.get("ingestion_strategy", "")[:600]}

Storage Layout:
{self.context.get("storage_layout", "")[:600]}

Orchestration:
{self.context.get("orchestration", "")[:600]}

Security & Governance:
{self.context.get("security_governance", "")[:600]}

Data Model:
{self.context.get("data_model", "")[:600]}

Data Quality Plan:
{self.context.get("data_quality_plan", "")[:500]}

Analytics / BI:
{self.context.get("analytics_bi", "")[:500]}
"""