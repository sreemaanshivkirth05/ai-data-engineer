from typing import Dict, Any, Optional
from llm.openai_client import OpenAIClient


class IngestionStrategyAgent:
    def __init__(self, context: Dict[str, Any], rag_context: Optional[str] = None):
        self.context = context
        self.rag_context = rag_context or ""
        self.llm = OpenAIClient()

    def run(self) -> Dict[str, Any]:
        prompt = self._build_prompt()
        strategy_doc = self.llm.generate(prompt)
        return {"markdown": strategy_doc}

    def _build_prompt(self) -> str:
        dataset_profile = self.context.get("dataset_profile", {})
        data_contract = self.context.get("data_contract", "")
        business_requirements = self.context.get("business_requirements", "")

        return f"""{self.rag_context}

You are a Senior Data Engineer designing a production-grade data ingestion strategy.

You have been given retrieved reference architecture patterns and web research above.
Use them to inform your design — choose the ingestion approach that best matches
the detected domain and requirements. Cite which pattern influenced your choices.

You are given:
- Dataset profile (size, columns, nulls, keys, PII hints)
- Data contract (schema, constraints)
- Business requirements

Your job:
- Decide ingestion approach: Batch vs CDC vs Streaming (informed by the RAG context)
- Choose appropriate cloud services
- Define ingestion frequency
- Define file formats and landing zones
- Define idempotency and deduplication strategy
- Define failure handling, retries, and reprocessing
- Define SLAs and data freshness expectations
- Call out risks and tradeoffs

Output MUST be in Markdown with these sections:

1. Overview & Pattern Choice (cite which reference pattern you drew from)
2. Ingestion Sources
3. Ingestion Approach (Batch / CDC / Streaming) with justification
4. Cloud Services & Components
5. Load Frequency & Scheduling
6. Data Landing & File Formats
7. Idempotency, Deduplication & Backfills
8. Failure Handling & Retries
9. SLAs & Freshness Guarantees
10. Risks & Tradeoffs

Business Requirements:
{business_requirements}

Dataset Profile:
{dataset_profile}

Data Contract:
{data_contract}
"""