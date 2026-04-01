from typing import Dict, Any, Optional
from llm.openai_client import OpenAIClient


class StorageLayoutAgent:
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

You are a Senior Data Engineer designing storage and table layout for a
production data platform.

You have been given retrieved reference architecture patterns above.
Use the layering strategy (Bronze/Silver/Gold or equivalent) from the most
relevant pattern. Adapt it to the specific dataset profile and business requirements.
Cite which pattern influenced your storage design.

Your job:
- Design layered storage architecture (Bronze/Silver/Gold or equivalent)
- Choose file formats (Parquet, Iceberg, Delta, etc.)
- Define partitioning strategy based on the dataset's time and dimension columns
- Define table layout
- Define retention and lifecycle policies
- Optimise for analytics and cost

Output MUST be in Markdown with sections:
1. Overview & Pattern Choice (cite which reference architecture you drew from)
2. Layered Architecture (Bronze/Silver/Gold or equivalent)
3. File Formats & Table Types (with justification)
4. Partitioning Strategy (based on actual dataset columns)
5. Storage Layout (path structure + table definitions)
6. Data Retention & Lifecycle Policies
7. Performance Considerations
8. Risks & Tradeoffs

Dataset Profile:
{self.context.get("dataset_profile")}

Data Contract:
{self.context.get("data_contract")}

Ingestion Strategy:
{self.context.get("ingestion_strategy")}
"""