from typing import Dict, Any, Optional
from llm.openai_client import OpenAIClient


class MermaidAIAgent:
    """
    Uses an LLM to generate a Mermaid architecture diagram based on the
    full design context, grounded by RAG-retrieved reference patterns.
    """

    def __init__(
        self,
        context: Dict[str, Any],
        model: str = None,
        rag_context: Optional[str] = None
    ):
        self.context = context
        self.rag_context = rag_context or ""
        self.llm = OpenAIClient(model=model) if model else OpenAIClient()

    def run(self) -> Dict[str, Any]:
        prompt = self._build_prompt()
        mermaid_code = self.llm.generate(prompt).strip()

        # Strip markdown fences if LLM wrapped the code
        if "```mermaid" in mermaid_code:
            mermaid_code = mermaid_code.split("```mermaid")[-1].split("```")[0].strip()
        elif "```" in mermaid_code:
            mermaid_code = mermaid_code.split("```")[1].split("```")[0].strip()

        # Ensure valid Mermaid directive
        if not mermaid_code.lower().startswith(("flowchart", "graph")):
            mermaid_code = "flowchart LR\n" + mermaid_code

        return {"markdown": mermaid_code}

    def _build_prompt(self) -> str:
        requirements = self.context.get("requirements_analysis", "")
        ingestion = self.context.get("ingestion_strategy", "")
        storage = self.context.get("storage_layout", "")
        orchestration = self.context.get("orchestration", "")
        security = self.context.get("security_governance", "")
        analytics = self.context.get("analytics_bi", "")
        data_model = self.context.get("data_model", "")

        return f"""{self.rag_context}

You are a senior data platform architect generating a Mermaid diagram.

You have been given retrieved reference architecture patterns above.
Use the structure of the most relevant pattern as your diagram's foundation,
adapted to the specific design decisions made in the sections below.

Rules:
- Output ONLY valid Mermaid code — no markdown fences, no explanations
- Use "flowchart LR" or "flowchart TD"
- Include clearly labelled subgraphs for each layer:
  - Sources → Ingestion → Storage (Bronze/Silver/Gold or equivalent)
  - Orchestration, Data Quality, Security
  - Analytics / BI consumption
- Use short readable node names (max 4 words)
- Show data flow direction with arrows
- Reflect the actual design decisions below (not generic defaults)
- Use the reference pattern's node structure as inspiration

# Business Requirements
{requirements}

# Ingestion Strategy
{ingestion[:800]}

# Storage Layout
{storage[:800]}

# Orchestration
{orchestration[:600]}

# Security & Governance
{security[:400]}

# Data Model
{data_model[:400]}

# Analytics / BI
{analytics[:400]}

Generate the Mermaid diagram now. Output ONLY the Mermaid code.
"""