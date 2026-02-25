from typing import Dict, Any
from llm.openai_client import OpenAIClient

class ArchitectureDiagramAgent:
    def __init__(self, context: Dict[str, Any]):
        self.context = context
        self.llm = OpenAIClient()

    def run(self) -> Dict[str, Any]:
        prompt = self._build_prompt()
        diagram = self.llm.generate(prompt)
        return {"markdown": diagram}

    def _build_prompt(self) -> str:
        return f"""
You are a Data Platform Architect generating a diagram-as-code.

Your job:
- Produce a Mermaid diagram of the full data platform
- Show: Sources -> Ingestion -> Storage Layers -> Warehouse -> BI
- Include orchestration and monitoring
- Keep it clean and readable

Output MUST be ONLY a Mermaid code block.

Context Summary:
Ingestion:
{self.context.get("ingestion_strategy")}

Storage:
{self.context.get("storage_layout")}

Orchestration:
{self.context.get("orchestration")}

Analytics:
{self.context.get("analytics_bi")}
"""