from typing import Dict, Any
from llm.openai_client import OpenAIClient

class StorageLayoutAgent:
    def __init__(self, context: Dict[str, Any]):
        self.context = context
        self.llm = OpenAIClient()

    def run(self) -> Dict[str, Any]:
        prompt = self._build_prompt()
        doc = self.llm.generate(prompt)
        return {"markdown": doc}

    def _build_prompt(self) -> str:
        return f"""
You are a Senior Data Engineer designing storage and table layout for a production data platform on AWS.

Inputs:
- Dataset Profile
- Data Contract
- Ingestion Strategy

Your job:
- Design Bronze / Silver / Gold layers
- Choose file formats (Parquet, Iceberg, Delta, etc.)
- Define partitioning strategy
- Define table layout in S3 and warehouse
- Define retention and lifecycle policies
- Optimize for analytics and cost

Output MUST be in Markdown with sections:
1. Overview
2. Layered Architecture (Bronze/Silver/Gold)
3. File Formats & Table Types
4. Partitioning Strategy
5. Storage Layout (S3 + Warehouse)
6. Data Retention & Lifecycle
7. Performance Considerations
8. Risks & Tradeoffs

Dataset Profile:
{self.context.get("dataset_profile")}

Data Contract:
{self.context.get("data_contract")}

Ingestion Strategy:
{self.context.get("ingestion_strategy")}
"""