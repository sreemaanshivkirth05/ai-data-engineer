from typing import Dict, Any

class CostEstimationAgent:
    """
    Rough monthly cost estimator for the designed data platform.
    Uses simple heuristics based on dataset size, ingestion frequency, and architecture choices.
    """

    def __init__(self, context: Dict[str, Any]):
        self.context = context

    def run(self) -> Dict[str, Any]:
        profile = self.context.get("dataset_profile", {})
        ingestion = (self.context.get("ingestion_strategy") or "").lower()
        storage = (self.context.get("storage_layout") or "").lower()
        orchestration = (self.context.get("orchestration") or "").lower()

        # -----------------------------
        # 1) Estimate data size
        # -----------------------------
        total_rows = profile.get("row_count", 1_000_000)
        total_cols = len(profile.get("columns", [])) or 10

        # Very rough heuristic: 1 row ~ 1 KB per 10 columns
        estimated_gb = max(1.0, (total_rows * total_cols * 0.0001) / 1024)

        # -----------------------------
        # 2) Storage cost (S3-like)
        # -----------------------------
        storage_cost_per_gb = 0.023  # $/GB/month (S3 standard ballpark)
        storage_cost = estimated_gb * storage_cost_per_gb

        # -----------------------------
        # 3) Ingestion / ETL compute cost
        # -----------------------------
        # Assume:
        # - Batch daily job: $2 per run
        # - Streaming: $150/month baseline
        if "stream" in ingestion or "cdc" in ingestion:
            etl_cost = 150.0
            ingestion_type = "streaming / CDC"
        else:
            runs_per_month = 30
            etl_cost = runs_per_month * 2.0
            ingestion_type = "batch"

        # -----------------------------
        # 4) Warehouse / Query cost
        # -----------------------------
        # Very rough: $50/month baseline for small usage
        warehouse_cost = 50.0

        # -----------------------------
        # 5) Orchestration cost
        # -----------------------------
        # Airflow/Step Functions small usage
        orchestration_cost = 10.0

        # -----------------------------
        # Total
        # -----------------------------
        total_monthly = storage_cost + etl_cost + warehouse_cost + orchestration_cost

        # -----------------------------
        # Build Markdown report
        # -----------------------------
        md = f"""
# 💸 Estimated Monthly Cost Report

## Assumptions
- Estimated dataset size: **{estimated_gb:.2f} GB**
- Ingestion type: **{ingestion_type}**
- Rough, conservative cloud pricing assumptions (S3/Glue/Warehouse-style)

## Cost Breakdown (Monthly)

- 🪣 Storage (Data Lake): **${storage_cost:.2f}**
- 🔄 ETL / Ingestion Compute: **${etl_cost:.2f}**
- 🏬 Warehouse / Query Engine: **${warehouse_cost:.2f}**
- ⏱️ Orchestration / Scheduling: **${orchestration_cost:.2f}**

---

## ✅ Estimated Total Monthly Cost

> 💰 **${total_monthly:.2f} / month**

---

## ⚠️ Notes

- This is a **rough-order-of-magnitude estimate**, not a billing quote.
- Actual cost depends on:
  - Cloud provider (AWS/GCP/Azure)
  - Region
  - Data growth rate
  - Query patterns
  - SLA requirements

## 💡 Optimization Ideas

- Use partitioning + columnar formats to reduce scan costs
- Use incremental loads instead of full refreshes
- Downsample or archive cold data
- Cache BI queries / use aggregates
"""

        return {
            "markdown": md,
            "estimated_gb": estimated_gb,
            "total_monthly": total_monthly,
            "breakdown": {
                "storage": storage_cost,
                "etl": etl_cost,
                "warehouse": warehouse_cost,
                "orchestration": orchestration_cost
            }
        }