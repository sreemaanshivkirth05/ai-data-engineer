from typing import Dict, Any, Optional


class ValidatorAgent:
    """
    Rule-based validator. No LLM call — checks the pipeline outputs
    against a set of deterministic rules and produces a pass/fail report.

    Validates:
    - Required sections are present in each output
    - Key fields are non-empty
    - Consistency between outputs (e.g. ingestion approach matches storage)
    - Data contract completeness
    - Cost estimate is present
    """

    REQUIRED_SECTIONS = {
        "data_contract":        ["Schema", "Keys", "Constraints"],
        "ingestion_strategy":   ["Ingestion", "Frequency", "Failure"],
        "storage_layout":       ["Bronze", "Silver", "Gold"],
        "orchestration":        ["DAG", "Schedule", "Retry"],
        "security_governance":  ["IAM", "Encryption", "Audit"],
        "data_model":           ["Fact", "Dimension", "Grain"],
        "data_quality_plan":    ["Check", "SLA", "Alert"],
        "analytics_bi":         ["KPI", "Dashboard", "BI"],
    }

    def __init__(self, context: Dict[str, Any], rag_context: Optional[str] = None):
        self.context = context

    def run(self) -> Dict[str, Any]:
        results = []
        passed = 0
        failed = 0

        for field, keywords in self.REQUIRED_SECTIONS.items():
            content = self.context.get(field, "") or ""
            content_lower = content.lower()

            missing = [kw for kw in keywords if kw.lower() not in content_lower]

            if not content.strip():
                results.append({
                    "field": field,
                    "status": "FAIL",
                    "reason": "Output is empty or missing"
                })
                failed += 1
            elif missing:
                results.append({
                    "field": field,
                    "status": "WARN",
                    "reason": f"Expected keywords not found: {', '.join(missing)}"
                })
                failed += 1
            else:
                results.append({
                    "field": field,
                    "status": "PASS",
                    "reason": "All expected keywords found"
                })
                passed += 1

        # Extra checks
        ingestion = (self.context.get("ingestion_strategy") or "").lower()
        storage = (self.context.get("storage_layout") or "").lower()

        streaming_in_ingestion = any(k in ingestion for k in ["stream", "cdc", "kinesis", "kafka"])
        streaming_in_storage = any(k in storage for k in ["stream", "kinesis", "kafka", "hot"])

        if streaming_in_ingestion and not streaming_in_storage:
            results.append({
                "field": "consistency_check",
                "status": "WARN",
                "reason": "Ingestion mentions streaming but storage layout does not reference a hot/streaming layer"
            })
            failed += 1
        else:
            results.append({
                "field": "consistency_check",
                "status": "PASS",
                "reason": "Ingestion and storage approaches appear consistent"
            })
            passed += 1

        cost = self.context.get("cost_estimate")
        if not cost:
            results.append({
                "field": "cost_estimate",
                "status": "FAIL",
                "reason": "Cost estimate is missing"
            })
            failed += 1
        else:
            results.append({
                "field": "cost_estimate",
                "status": "PASS",
                "reason": "Cost estimate is present"
            })
            passed += 1

        total = passed + failed
        score_pct = round((passed / total) * 100) if total > 0 else 0

        # Build markdown report
        lines = [
            "# Validation Report\n",
            f"**Overall: {passed}/{total} checks passed ({score_pct}%)**\n",
            "| Check | Status | Notes |",
            "|-------|--------|-------|"
        ]

        for r in results:
            status_icon = "PASS" if r["status"] == "PASS" else ("WARN" if r["status"] == "WARN" else "FAIL")
            lines.append(f"| {r['field']} | {status_icon} | {r['reason']} |")

        lines.append("")
        if score_pct == 100:
            lines.append("All validation checks passed. The pipeline output looks complete.")
        elif score_pct >= 70:
            lines.append("Most checks passed. Review warnings before deploying to production.")
        else:
            lines.append("Several checks failed. Review the critical issues before proceeding.")

        return {
            "markdown": "\n".join(lines),
            "passed": passed,
            "failed": failed,
            "score_pct": score_pct,
            "results": results
        }