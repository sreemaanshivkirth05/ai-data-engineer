import json
import os
import sys
from pathlib import Path


# ============================================================
# Ensure project root is importable when running this file directly
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


# ============================================================
# Universal Planner Imports
# ============================================================

from analyst_runtime.universal_planner.predict import predict_plan
from analyst_runtime.universal_planner.column_mapper import map_columns_to_plan
from analyst_runtime.universal_planner.planner_schema_validator import attach_schema_validation
from analyst_runtime.universal_planner.planner_output_adapter import adapt_mapped_plan_for_platform


# ============================================================
# Smoke Test Metadata
# ============================================================

def build_fake_metadata():
    """
    Small dataset metadata for testing Universal Planner integration
    inside the main ai_data_engineer project.
    """

    return {
        "source_type": "manual_test",
        "row_count": 5,
        "column_count": 4,
        "has_numeric": True,
        "has_category": True,
        "has_datetime": True,
        "has_text": False,
        "columns": [
            {
                "name": "Sales",
                "semantic_type": "numeric",
                "role": "measure",
                "business_type": "currency_or_amount",
                "cardinality_type": "continuous_or_measure",
                "unique_ratio": 1.0,
            },
            {
                "name": "Profit",
                "semantic_type": "numeric",
                "role": "measure",
                "business_type": "currency_or_amount",
                "cardinality_type": "continuous_or_measure",
                "unique_ratio": 1.0,
            },
            {
                "name": "Region",
                "semantic_type": "category",
                "role": "dimension",
                "business_type": "categorical_dimension",
                "cardinality_type": "low_cardinality_category",
                "unique_ratio": 0.4,
            },
            {
                "name": "Order Date",
                "semantic_type": "datetime",
                "role": "time",
                "business_type": "date_or_time",
                "cardinality_type": "continuous_or_measure",
                "unique_ratio": 1.0,
            },
        ],
    }


# ============================================================
# Smoke Test Runner
# ============================================================

def main():
    print("\n================ UNIVERSAL PLANNER SMOKE TEST ================\n")

    metadata = build_fake_metadata()
    question = "Compare sales by region"

    print(f"Project root: {PROJECT_ROOT}")
    print(f"Question: {question}")

    # --------------------------------------------------------
    # 1. Planner
    # --------------------------------------------------------

    plan = predict_plan(question, metadata)

    assert isinstance(plan, dict), "predict_plan did not return a dictionary."
    assert "operation" in plan, "predict_plan output missing operation."
    assert "best_chart" in plan, "predict_plan output missing best_chart."

    print("\nPlanner output:")
    print(json.dumps(plan, indent=2))

    # --------------------------------------------------------
    # 2. Column Mapper
    # --------------------------------------------------------

    mapped_plan = map_columns_to_plan(
        question=question,
        metadata=metadata,
        plan=plan,
    )

    assert isinstance(mapped_plan, dict), "map_columns_to_plan did not return a dictionary."
    assert "selected_columns" in mapped_plan, "mapped_plan missing selected_columns."

    print("\nMapped plan before schema validation:")
    print(json.dumps(mapped_plan, indent=2))

    # --------------------------------------------------------
    # 3. Schema Validation
    # --------------------------------------------------------

    mapped_plan = attach_schema_validation(mapped_plan)

    assert mapped_plan.get("is_valid_schema") is True, (
        f"Schema validation failed: {mapped_plan.get('schema_errors')}"
    )

    print("\nMapped plan after schema validation:")
    print(json.dumps(mapped_plan, indent=2))

    # --------------------------------------------------------
    # 4. Platform Contract Adapter
    # --------------------------------------------------------

    contract = adapt_mapped_plan_for_platform(mapped_plan)

    assert isinstance(contract, dict), "Adapter did not return a dictionary."
    assert "operation" in contract, "Contract missing operation."
    assert "chart_type" in contract, "Contract missing chart_type."
    assert "columns" in contract, "Contract missing columns."
    assert "safe_to_execute" in contract, "Contract missing safe_to_execute."
    assert "main_chart" in contract, "Contract missing main_chart."
    assert "main_aggregation" in contract, "Contract missing main_aggregation."

    print("\nFinal planner contract:")
    print(json.dumps(contract, indent=2))

    # --------------------------------------------------------
    # 5. Expected Contract Checks
    # --------------------------------------------------------

    assert contract["safe_to_execute"] is True, "Expected safe_to_execute=True."
    assert contract["needs_fallback"] is False, "Expected needs_fallback=False."

    assert contract["columns"]["measure"] == "Sales", (
        f"Expected measure column Sales, got {contract['columns']['measure']}"
    )

    assert contract["columns"]["dimension"] == "Region", (
        f"Expected dimension column Region, got {contract['columns']['dimension']}"
    )

    assert contract["main_chart"] == "bar", (
        f"Expected main_chart=bar, got {contract['main_chart']}"
    )

    assert contract["main_aggregation"] == "sum", (
        f"Expected main_aggregation=sum, got {contract['main_aggregation']}"
    )

    print("\nSMOKE TEST PASSED")
    print("Universal Planner imports, model loading, column mapping, schema validation, and platform adapter are working inside the main project.")


if __name__ == "__main__":
    main()