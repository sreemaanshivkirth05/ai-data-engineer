from typing import Dict, Any, List

class ValidatorAgent:
    """
    Rule-based consistency checker across the generated design artifacts.
    Produces a Markdown report with PASS/FAIL and recommendations.
    """

    def __init__(self, context: Dict[str, Any]):
        self.context = context

    def run(self) -> Dict[str, Any]:
        checks = []

        dataset_profile = self.context.get("dataset_profile", {})
        data_contract = (self.context.get("data_contract") or "").lower()
        ingestion = (self.context.get("ingestion_strategy") or "").lower()
        storage = (self.context.get("storage_layout") or "").lower()
        orchestration = (self.context.get("orchestration") or "").lower()
        security = (self.context.get("security_governance") or "").lower()
        data_model = (self.context.get("data_model") or "").lower()
        analytics = (self.context.get("analytics_bi") or "").lower()

        # Rule 1: PII → Security must mention masking/encryption
        pii_present = False
        for col in dataset_profile.get("columns", []):
            if col.get("possible_pii"):
                pii_present = True
                break

        if pii_present:
            ok = ("mask" in security) or ("encrypt" in security) or ("pii" in security)
            checks.append(self._check(
                "PII handling present when dataset contains PII",
                ok,
                "Dataset has PII-like columns. Security should mention masking/encryption/access controls."
            ))
        else:
            checks.append(self._check(
                "No PII detected → no mandatory masking requirement",
                True,
                "Dataset does not appear to contain PII."
            ))

        # Rule 2: CDC/Streaming → Orchestration must mention incremental/schedule
        cdc_or_streaming = ("cdc" in ingestion) or ("stream" in ingestion) or ("kinesis" in ingestion) or ("event" in ingestion)
        if cdc_or_streaming:
            ok = ("increment" in orchestration) or ("schedule" in orchestration) or ("dag" in orchestration) or ("trigger" in orchestration)
            checks.append(self._check(
                "CDC/Streaming ingestion has matching orchestration strategy",
                ok,
                "Ingestion uses CDC/streaming. Orchestration should describe incremental runs, triggers, or DAG scheduling."
            ))
        else:
            checks.append(self._check(
                "Batch ingestion orchestration consistency",
                True,
                "Ingestion appears batch-oriented; no special CDC orchestration required."
            ))

        # Rule 3: Partitioning → Partition keys should be mentioned
        mentions_partition = "partition" in storage
        if mentions_partition:
            ok = ("date" in storage) or ("key" in storage) or ("id" in storage)
            checks.append(self._check(
                "Partitioning strategy includes partition keys",
                ok,
                "Storage mentions partitioning. It should specify partition keys (e.g., date, id, region)."
            ))
        else:
            checks.append(self._check(
                "No partitioning mentioned",
                True,
                "No partitioning detected in storage design."
            ))

        # Rule 4: PK in contract → PK in data model
        mentions_pk_in_contract = ("primary key" in data_contract) or ("pk" in data_contract)
        if mentions_pk_in_contract:
            ok = ("primary key" in data_model) or ("pk" in data_model) or ("surrogate" in data_model)
            checks.append(self._check(
                "Primary keys in contract are reflected in data model",
                ok,
                "Data contract defines primary keys. Data model should explicitly include them."
            ))
        else:
            checks.append(self._check(
                "No explicit primary keys in contract",
                True,
                "No primary keys detected in contract."
            ))

        # Rule 5: Analytics should reference model/marts/metrics
        ok = ("mart" in analytics) or ("semantic" in analytics) or ("metric" in analytics) or ("model" in analytics)
        checks.append(self._check(
            "Analytics/BI layer references data model or marts",
            ok,
            "Analytics layer should reference data marts, semantic layer, or the data model."
        ))

        md = self._to_markdown(checks)

        return {
            "markdown": md,
            "checks": checks
        }

    def _check(self, name: str, passed: bool, recommendation: str) -> Dict[str, Any]:
        return {
            "name": name,
            "passed": passed,
            "recommendation": recommendation
        }

    def _to_markdown(self, checks: List[Dict[str, Any]]) -> str:
        lines = []
        lines.append("# ✅ Architecture Consistency Validation Report\n")

        passed_count = sum(1 for c in checks if c["passed"])
        total = len(checks)

        lines.append(f"**Summary:** {passed_count}/{total} checks passed.\n")
        lines.append("## Detailed Checks\n")

        for c in checks:
            status = "✅ PASS" if c["passed"] else "❌ FAIL"
            lines.append(f"### {status} — {c['name']}")
            lines.append(f"- Recommendation: {c['recommendation']}\n")

        if passed_count == total:
            lines.append("## Overall Verdict\n")
            lines.append("🎉 The architecture is **internally consistent** based on the current rule set.")
        else:
            lines.append("## Overall Verdict\n")
            lines.append("⚠️ The architecture has **consistency gaps**. Review the failed checks and update the design accordingly.")

        return "\n".join(lines)