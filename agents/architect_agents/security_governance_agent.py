from typing import Dict, Any, Optional
from llm.openai_client import OpenAIClient


class SecurityGovernanceAgent:
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

You are a Senior Data Platform Architect responsible for security and governance.

You have been given retrieved reference architecture patterns above.
Apply the security model from the most relevant pattern to this specific domain.
For example: if the domain is healthcare, apply HIPAA controls; if finance, apply
SOX/regulatory audit requirements. Cite which pattern informed your design.

Your job:
- Design IAM and access control appropriate to the detected domain
- Define PII/sensitive data handling and masking
- Define encryption (at rest, in transit)
- Define audit logging and lineage
- Define data governance practices
- Define compliance considerations specific to the domain

Output MUST be in Markdown with sections:
1. Overview & Compliance Framework (cite pattern + domain-specific regulations)
2. Data Classification & Sensitive Data Handling
3. Access Control & IAM (role definitions, least privilege)
4. Encryption & Secrets Management
5. Audit Logging & Data Lineage
6. Governance Processes (data catalog, data quality, ownership)
7. Compliance Considerations (GDPR/HIPAA/SOX/PCI-DSS as applicable)
8. Risks & Gaps

Dataset Profile:
{self.context.get("dataset_profile")}

Data Contract:
{self.context.get("data_contract")}

Storage Layout:
{self.context.get("storage_layout")}
"""