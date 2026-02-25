from typing import Dict, Any
from llm.openai_client import OpenAIClient

class SecurityGovernanceAgent:
    def __init__(self, context: Dict[str, Any]):
        self.context = context
        self.llm = OpenAIClient()

    def run(self) -> Dict[str, Any]:
        prompt = self._build_prompt()
        doc = self.llm.generate(prompt)
        return {"markdown": doc}

    def _build_prompt(self) -> str:
        return f"""
You are a Senior Data Platform Architect responsible for security and governance.

Inputs:
- Dataset Profile (PII hints)
- Data Contract
- Storage Layout

Your job:
- Design IAM and access control
- Define PII handling and masking
- Define encryption (at rest, in transit)
- Define audit logging and lineage
- Define data governance practices
- Define compliance considerations

Output MUST be in Markdown with sections:
1. Overview
2. Data Classification & PII Handling
3. Access Control & IAM
4. Encryption & Secrets Management
5. Audit Logging & Lineage
6. Governance Processes
7. Compliance Considerations
8. Risks & Gaps

Dataset Profile:
{self.context.get("dataset_profile")}

Data Contract:
{self.context.get("data_contract")}

Storage Layout:
{self.context.get("storage_layout")}
"""