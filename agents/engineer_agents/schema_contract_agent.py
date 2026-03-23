from typing import Dict, Any
from llm.openai_client import OpenAIClient

class SchemaContractAgent:
    def __init__(self, dataset_profile: Dict[str, Any]):
        self.dataset_profile = dataset_profile
        self.llm = OpenAIClient()

    def run(self) -> Dict[str, Any]:
        prompt = self._build_prompt()
        schema_doc = self.llm.generate(prompt)

        return {
            "markdown": schema_doc
        }

    def _build_prompt(self) -> str:
        return f"""
You are a Senior Data Engineer designing a production data contract.

You are given a dataset profile extracted from a CSV.

Your job:
- Propose a canonical schema
- Define data types
- Define nullability
- Identify primary keys
- Identify possible foreign keys (if any)
- Define constraints (uniqueness, ranges, enums if applicable)
- Define data contract rules:
  - Versioning strategy
  - Backward compatibility
  - Breaking vs non-breaking changes

Output MUST be in Markdown with these sections:

1. Overview
2. Canonical Schema (table with columns, types, nullable, description)
3. Keys & Constraints
4. Data Quality Expectations
5. Data Contract Rules (Versioning & Evolution)
6. Assumptions & Risks

Dataset Profile:
{self.dataset_profile}
"""