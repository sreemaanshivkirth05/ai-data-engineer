from typing import Dict, Any, Optional


class CostEstimationAgent:
    """
    Monthly cost estimator for the designed data platform.
    Uses heuristics based on dataset size, ingestion frequency, complexity
    level detected from RAG patterns, and domain-specific cost drivers.
    """

    # Rough service cost multipliers by architecture complexity
    COMPLEXITY_MULTIPLIERS = {
        "low-medium":  1.0,
        "medium":      1.5,
        "medium-high": 2.5,
        "high":        4.0,
        "very high":   7.0,
    }

    def __init__(
        self,
        context: Dict[str, Any],
        rag_context: Optional[str] = None,
        detected_complexity: Optional[str] = None
    ):
        self.context = context
        self.rag_context = rag_context or ""
        self.complexity = detected_complexity or "medium"

    def run(self) -> Dict[str, Any]:
        profile = self.context.get("dataset_profile", {})
        ingestion = (self.context.get("ingestion_strategy") or "").lower()
        storage = (self.context.get("storage_layout") or "").lower()

        # 1) Estimate data size
        total_rows = profile.get("row_count", 1_000_000)
        total_cols = len(profile.get("columns", [])) or 10
        estimated_gb = max(1.0, (total_rows * total_cols * 0.0001) / 1024)

        # 2) Storage cost
        storage_cost_per_gb = 0.023
        storage_layers = 3 if "gold" in storage or "silver" in storage else 1
        storage_cost = estimated_gb * storage_cost_per_gb * storage_layers

        # 3) Ingestion / ETL compute
        if any(k in ingestion for k in ["stream", "cdc", "real-time", "kinesis", "kafka"]):
            etl_cost = 200.0
            ingestion_type = "streaming / CDC"
        elif "hourly" in ingestion:
            etl_cost = 90.0
            ingestion_type = "hourly batch"
        else:
            etl_cost = 60.0
            ingestion_type = "daily batch"

        # 4) Warehouse / Query cost
        if any(k in storage for k in ["snowflake", "bigquery", "redshift"]):
            warehouse_cost = 80.0
        else:
            warehouse_cost = 40.0

        # 5) Orchestration cost
        if any(k in ingestion for k in ["airflow", "step functions", "prefect"]):
            orchestration_cost = 25.0
        else:
            orchestration_cost = 10.0

        # 6) Compliance / security tooling (domain-specific add-on)
        compliance_cost = 0.0
        rag_lower = self.rag_context.lower()
        if any(k in rag_lower for k in ["hipaa", "healthcare", "phi"]):
            compliance_cost = 150.0
        elif any(k in rag_lower for k in ["financial", "sox", "pci", "gdpr"]):
            compliance_cost = 100.0
        elif "gdpr" in rag_lower:
            compliance_cost = 50.0

        # 7) Apply complexity multiplier from RAG context
        multiplier = self.COMPLEXITY_MULTIPLIERS.get(self.complexity, 1.5)
        base_total = storage_cost + etl_cost + warehouse_cost + orchestration_cost
        scaled_total = base_total * multiplier + compliance_cost

        # Build report
        md = f"""
# 💸 Estimated Monthly Cost Report

## Architecture Assessment
- Detected complexity level: **{self.complexity}**
- Cost multiplier applied: **{multiplier}x** (accounts for HA, redundancy, ops overhead)
- Estimated dataset size: **{estimated_gb:.2f} GB** ({storage_layers} storage layers)
- Ingestion type: **{ingestion_type}**

## Cost Breakdown (Monthly)

| Component | Base Cost | Notes |
|-----------|-----------|-------|
| 🪣 Storage (Data Lake, {storage_layers} layers) | ${storage_cost:.2f} | S3/GCS at $0.023/GB |
| 🔄 ETL / Ingestion Compute | ${etl_cost:.2f} | {ingestion_type} processing |
| 🏬 Warehouse / Query Engine | ${warehouse_cost:.2f} | Analytical query compute |
| ⏱️ Orchestration / Scheduling | ${orchestration_cost:.2f} | Workflow management |
| 🔒 Compliance / Security Tooling | ${compliance_cost:.2f} | Domain-specific controls |

**Base subtotal:** ${base_total:.2f}
**Complexity adjustment ({multiplier}x):** +${(base_total * multiplier - base_total):.2f}
**Compliance add-on:** +${compliance_cost:.2f}

---

## ✅ Estimated Total Monthly Cost

> 💰 **${scaled_total:.2f} / month**

---

## Cost Drivers by Architecture Layer

Based on the retrieved reference patterns for this domain:
{self._cost_drivers_from_rag()}

---

## ⚠️ Important Caveats

- This is a **rough-order-of-magnitude estimate** (±50% accuracy typical).
- Actual cost depends on: cloud provider, region, data growth rate,
  query patterns, team size, and SLA requirements.
- The complexity multiplier ({multiplier}x) accounts for HA setup,
  cross-region replication, monitoring tools, and operational overhead.

## 💡 Optimisation Recommendations

- **Storage:** Use columnar formats (Parquet/Iceberg) + lifecycle tiering
  to move cold data to cheaper storage classes (e.g. S3 Glacier).
- **Compute:** Use incremental/CDC loads instead of full refreshes.
  Right-size warehouse clusters and use auto-pause/suspend.
- **Query cost:** Cache BI queries, materialise frequently-used aggregations,
  use result caching in the warehouse.
- **Streaming cost:** If real-time is not essential, downgrade to micro-batch
  (5–15 min) to cut streaming infrastructure costs by 60–70%.
"""

        return {
            "markdown": md,
            "estimated_gb": estimated_gb,
            "total_monthly": round(scaled_total, 2),
            "complexity": self.complexity,
            "multiplier": multiplier,
            "breakdown": {
                "storage": round(storage_cost, 2),
                "etl": round(etl_cost, 2),
                "warehouse": round(warehouse_cost, 2),
                "orchestration": round(orchestration_cost, 2),
                "compliance": round(compliance_cost, 2),
                "complexity_adjustment": round(base_total * multiplier - base_total, 2)
            }
        }

    def _cost_drivers_from_rag(self) -> str:
        """Extract cost driver hints from the RAG context."""
        rag = self.rag_context
        hints = []

        if "kafka" in rag.lower() or "kinesis" in rag.lower():
            hints.append("- Streaming infrastructure (Kafka/Kinesis) is the primary cost driver — partition count and retention period have the most impact.")
        if "iceberg" in rag.lower() or "delta" in rag.lower():
            hints.append("- Table format (Iceberg/Delta) adds metadata overhead but reduces query scan costs significantly.")
        if "dbt" in rag.lower():
            hints.append("- dbt compute costs scale with model complexity and run frequency — use incremental models where possible.")
        if "snowflake" in rag.lower() or "bigquery" in rag.lower() or "redshift" in rag.lower():
            hints.append("- Warehouse compute is pay-per-query — query optimisation and result caching are the highest-ROI cost controls.")
        if "hipaa" in rag.lower() or "healthcare" in rag.lower():
            hints.append("- HIPAA compliance tooling (Macie, Comprehend Medical, CloudTrail) adds $100–$200/month baseline.")
        if "financial" in rag.lower() or "sox" in rag.lower():
            hints.append("- Financial compliance audit logging and cross-region DR can double baseline infrastructure costs.")

        if not hints:
            hints.append("- Storage and compute are typically 70% of total cost. Focus optimisation effort there first.")

        return "\n".join(hints)