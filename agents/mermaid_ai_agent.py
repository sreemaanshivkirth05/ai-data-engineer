from typing import Dict, Any
from llm.openai_client import OpenAIClient

class MermaidAIAgent:
    """
    Uses an LLM to generate a Mermaid architecture diagram based on the full design context.
    Outputs ONLY valid Mermaid code.
    """

    def __init__(self, context: Dict[str, Any], model: str = None):
        self.context = context
        self.llm = OpenAIClient(model=model) if model else OpenAIClient()

    def run(self) -> Dict[str, Any]:
        # Gather relevant context pieces
        requirements = self.context.get("requirements_analysis", "")
        ingestion = self.context.get("ingestion_strategy", "")
        storage = self.context.get("storage_layout", "")
        orchestration = self.context.get("orchestration", "")
        security = self.context.get("security_governance", "")
        analytics = self.context.get("analytics_bi", "")
        data_model = self.context.get("data_model", "")

        prompt = f"""
You are a senior data platform architect.

Your task:
Generate a CLEAR, PROFESSIONAL Mermaid diagram that represents the full data platform architecture.

Rules:
- Output ONLY valid Mermaid code
- Use Mermaid "flowchart LR" or "flowchart TD"
- Include:
  - Data sources
  - Ingestion layer
  - Storage layers (bronze/silver/gold or equivalent)
  - Orchestration
  - Data quality / governance
  - Analytics / BI consumption
- Use short, readable node names
- Group layers using subgraphs where appropriate
- Show main data flows with arrows
- Do NOT include explanations or markdown fences

Context:

# Requirements
{requirements}

# Ingestion Strategy
{ingestion}

# Storage Layout
{storage}

# Orchestration
{orchestration}

# Security & Governance
{security}

# Data Model
{data_model}

# Analytics / BI
{analytics}

Now generate the Mermaid diagram.
"""

        mermaid_code = self.llm.generate(prompt).strip()

        # Safety: ensure it starts with a mermaid directive
        if not mermaid_code.lower().startswith("flowchart"):
            mermaid_code = "flowchart LR\n" + mermaid_code

        return {
            "markdown": mermaid_code
        }