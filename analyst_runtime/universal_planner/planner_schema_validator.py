from typing import Dict, Any, List, Optional


# ============================================================
# Allowed Values
# ============================================================

ALLOWED_INTENTS = {
    "aggregation",
    "comparison",
    "ranking",
    "trend_analysis",
    "correlation",
    "distribution",
    "data_quality",
    "text_analysis",
    "summary_analysis",
    "diagnostic_analysis",
    "forecasting",
}

ALLOWED_ANSWER_DEPTHS = {
    "direct_answer",
    "small_summary",
    "visual_answer",
    "deep_analysis",
    "data_quality_answer",
}

ALLOWED_OPERATIONS = {
    # Scalar / KPI
    "mean",
    "sum",
    "min",
    "max",
    "count",

    # Grouped numeric operations
    "groupby_sum",
    "groupby_mean",
    "groupby_sum_sort_desc",
    "groupby_mean_sort_desc",

    # Target-rate / outcome-rate operations
    "groupby_target_rate",
    "groupby_target_rate_sort_desc",

    # Time-series operations
    "time_groupby_sum",
    "time_groupby_mean",

    # Distribution / outlier operations
    "distribution",
    "outlier_check",

    # Correlation operations
    "correlation",
    "correlation_heatmap",

    # Data quality operations
    "null_check",
    "duplicate_check",
    "data_quality_summary",

    # Text operations
    "word_frequency",
    "sentiment_summary",
    "text_summary",

    # Higher-level operations
    "full_dataset_analysis",
    "diagnostic_analysis",
    "forecast",
}

ALLOWED_CHARTS = {
    "none",
    "table",
    "kpi_card",
    "bar_chart",
    "horizontal_bar_chart",
    "line_chart",
    "area_chart",
    "histogram",
    "box_plot",
    "scatter_plot",
    "heatmap",
    "correlation_heatmap",
    "multi_chart_dashboard",
}

REQUIRED_SELECTED_COLUMN_KEYS = {
    "measure_column",
    "secondary_measure_column",
    "dimension_column",
    "target_column",
    "time_column",
    "text_column",
}

REQUIRED_DATA_ROLE_KEYS = {
    "needs_numeric",
    "needs_category",
    "needs_datetime",
    "needs_text",
}

ALLOWED_CONFIDENCE_STATUSES = {
    "high_confidence",
    "rule_high_confidence",
    "medium_confidence",
    "low_confidence",
}

ALLOWED_ROUTE_TO = {
    "ml_planner",
    "llm_router",
}


# ============================================================
# Helpers
# ============================================================

def _is_bool(value: Any) -> bool:
    return isinstance(value, bool)


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _is_optional_string(value: Any) -> bool:
    return value is None or isinstance(value, str)


def _add_error(errors: List[str], message: str) -> None:
    errors.append(message)


def _add_warning(warnings: List[str], message: str) -> None:
    warnings.append(message)


def get_selected_columns(plan: Dict[str, Any]) -> Dict[str, Any]:
    selected_columns = plan.get("selected_columns")

    if isinstance(selected_columns, dict):
        return selected_columns

    return {}


def get_required_roles(plan: Dict[str, Any]) -> Dict[str, Any]:
    required_roles = plan.get("required_data_roles")

    if isinstance(required_roles, dict):
        return required_roles

    return {}


# ============================================================
# Core Schema Validation
# ============================================================

def validate_required_top_level_fields(plan: Dict[str, Any]) -> List[str]:
    errors = []

    required_fields = [
        "intent",
        "answer_depth",
        "operation",
        "best_chart",
        "chart_required",
        "required_data_roles",
    ]

    for field in required_fields:
        if field not in plan:
            _add_error(errors, f"Missing required field: {field}")

    return errors


def validate_allowed_values(plan: Dict[str, Any]) -> List[str]:
    errors = []

    intent = plan.get("intent")
    answer_depth = plan.get("answer_depth")
    operation = plan.get("operation")
    best_chart = plan.get("best_chart")
    confidence_status = plan.get("confidence_status")
    route_to = plan.get("route_to")

    if intent is not None and intent not in ALLOWED_INTENTS:
        _add_error(errors, f"Invalid intent: {intent}")

    if answer_depth is not None and answer_depth not in ALLOWED_ANSWER_DEPTHS:
        _add_error(errors, f"Invalid answer_depth: {answer_depth}")

    if operation is not None and operation not in ALLOWED_OPERATIONS:
        _add_error(errors, f"Invalid operation: {operation}")

    if best_chart is not None and best_chart not in ALLOWED_CHARTS:
        _add_error(errors, f"Invalid best_chart: {best_chart}")

    if confidence_status is not None and confidence_status not in ALLOWED_CONFIDENCE_STATUSES:
        _add_error(errors, f"Invalid confidence_status: {confidence_status}")

    if route_to is not None and route_to not in ALLOWED_ROUTE_TO:
        _add_error(errors, f"Invalid route_to: {route_to}")

    return errors


def validate_types(plan: Dict[str, Any]) -> List[str]:
    errors = []

    if "chart_required" in plan and not _is_bool(plan.get("chart_required")):
        _add_error(errors, "chart_required must be a boolean.")

    if "requires_llm_fallback" in plan and not _is_bool(plan.get("requires_llm_fallback")):
        _add_error(errors, "requires_llm_fallback must be a boolean.")

    if "min_confidence" in plan and not _is_number(plan.get("min_confidence")):
        _add_error(errors, "min_confidence must be a number.")

    if "raw_min_confidence" in plan and not _is_number(plan.get("raw_min_confidence")):
        _add_error(errors, "raw_min_confidence must be a number.")

    if "recommended_charts" in plan and not isinstance(plan.get("recommended_charts"), list):
        _add_error(errors, "recommended_charts must be a list.")

    if "rules_fired" in plan and not isinstance(plan.get("rules_fired"), list):
        _add_error(errors, "rules_fired must be a list.")

    if "low_confidence" in plan and not isinstance(plan.get("low_confidence"), list):
        _add_error(errors, "low_confidence must be a list.")

    if "raw_low_confidence" in plan and not isinstance(plan.get("raw_low_confidence"), list):
        _add_error(errors, "raw_low_confidence must be a list.")

    if "validation_messages" in plan and not isinstance(plan.get("validation_messages"), list):
        _add_error(errors, "validation_messages must be a list.")

    return errors


def validate_required_data_roles(plan: Dict[str, Any]) -> List[str]:
    errors = []

    required_roles = get_required_roles(plan)

    if not required_roles:
        _add_error(errors, "required_data_roles must be present and must be a dictionary.")
        return errors

    for key in REQUIRED_DATA_ROLE_KEYS:
        if key not in required_roles:
            _add_error(errors, f"required_data_roles missing key: {key}")
        elif not _is_bool(required_roles.get(key)):
            _add_error(errors, f"required_data_roles.{key} must be boolean.")

    return errors


def validate_selected_columns(plan: Dict[str, Any]) -> List[str]:
    errors = []

    selected_columns = get_selected_columns(plan)

    # Raw predict_plan() may not have selected_columns yet.
    # But mapped plans must have it. So this validator allows missing selected_columns
    # only before column mapping.
    if not selected_columns:
        return errors

    for key in REQUIRED_SELECTED_COLUMN_KEYS:
        if key not in selected_columns:
            _add_error(errors, f"selected_columns missing key: {key}")
        elif not _is_optional_string(selected_columns.get(key)):
            _add_error(errors, f"selected_columns.{key} must be string or null.")

    return errors


# ============================================================
# Logical Validation
# ============================================================

def validate_operation_requirements(plan: Dict[str, Any]) -> List[str]:
    """
    Validate whether the plan has the column roles needed by the chosen operation.

    This is strict only after column mapping, when selected_columns exists.
    """

    errors = []

    operation = plan.get("operation")
    selected = get_selected_columns(plan)

    if not selected:
        return errors

    measure_column = selected.get("measure_column")
    secondary_measure_column = selected.get("secondary_measure_column")
    dimension_column = selected.get("dimension_column")
    target_column = selected.get("target_column")
    time_column = selected.get("time_column")
    text_column = selected.get("text_column")

    scalar_measure_ops = {
        "mean",
        "sum",
        "min",
        "max",
    }

    grouped_measure_ops = {
        "groupby_sum",
        "groupby_mean",
        "groupby_sum_sort_desc",
        "groupby_mean_sort_desc",
    }

    target_rate_ops = {
        "groupby_target_rate",
        "groupby_target_rate_sort_desc",
    }

    time_ops = {
        "time_groupby_sum",
        "time_groupby_mean",
    }

    distribution_ops = {
        "distribution",
        "outlier_check",
    }

    text_ops = {
        "word_frequency",
        "sentiment_summary",
        "text_summary",
    }

    if operation in scalar_measure_ops:
        if not measure_column:
            _add_error(errors, f"{operation} requires selected_columns.measure_column.")

    if operation in grouped_measure_ops:
        if not measure_column:
            _add_error(errors, f"{operation} requires selected_columns.measure_column.")
        if not dimension_column:
            _add_error(errors, f"{operation} requires selected_columns.dimension_column.")

    if operation in target_rate_ops:
        if not target_column:
            _add_error(errors, f"{operation} requires selected_columns.target_column.")
        if not dimension_column:
            _add_error(errors, f"{operation} requires selected_columns.dimension_column.")

    if operation in time_ops:
        if not measure_column:
            _add_error(errors, f"{operation} requires selected_columns.measure_column.")
        if not time_column:
            _add_error(errors, f"{operation} requires selected_columns.time_column.")

    if operation in distribution_ops:
        if not measure_column:
            _add_error(errors, f"{operation} requires selected_columns.measure_column.")

    if operation == "correlation":
        if not measure_column:
            _add_error(errors, "correlation requires selected_columns.measure_column.")

        # secondary_measure_column is optional:
        # - present = scatter correlation
        # - missing = broad correlation summary
        # So do not require it here.

    if operation == "correlation_heatmap":
        # Heatmap can use all numeric columns. A specific measure column is optional.
        pass

    if operation in text_ops:
        if not text_column:
            _add_error(errors, f"{operation} requires selected_columns.text_column.")

    return errors


def validate_chart_operation_alignment(plan: Dict[str, Any]) -> List[str]:
    warnings = []

    operation = plan.get("operation")
    best_chart = plan.get("best_chart")

    expected_chart_groups = {
        "mean": {"kpi_card", "table"},
        "sum": {"kpi_card", "table"},
        "min": {"kpi_card", "table"},
        "max": {"kpi_card", "table"},
        "count": {"kpi_card", "table"},

        "groupby_sum": {"bar_chart", "horizontal_bar_chart", "table"},
        "groupby_mean": {"bar_chart", "horizontal_bar_chart", "table"},
        "groupby_sum_sort_desc": {"horizontal_bar_chart", "bar_chart", "table"},
        "groupby_mean_sort_desc": {"horizontal_bar_chart", "bar_chart", "table"},

        "groupby_target_rate": {"bar_chart", "horizontal_bar_chart", "table"},
        "groupby_target_rate_sort_desc": {"horizontal_bar_chart", "bar_chart", "table"},

        "time_groupby_sum": {"line_chart", "area_chart", "bar_chart", "table"},
        "time_groupby_mean": {"line_chart", "area_chart", "bar_chart", "table"},

        "distribution": {"histogram", "box_plot", "table"},
        "outlier_check": {"box_plot", "histogram", "table"},

        "correlation": {"scatter_plot", "table", "correlation_heatmap"},
        "correlation_heatmap": {"heatmap", "correlation_heatmap", "table"},

        "null_check": {"table"},
        "duplicate_check": {"table"},
        "data_quality_summary": {"table"},

        "word_frequency": {"bar_chart", "horizontal_bar_chart", "table"},
        "sentiment_summary": {"bar_chart", "table"},
        "text_summary": {"bar_chart", "table"},

        "full_dataset_analysis": {"multi_chart_dashboard", "table"},
        "diagnostic_analysis": {"multi_chart_dashboard", "bar_chart", "table"},
        "forecast": {"line_chart", "area_chart", "table"},
    }

    if operation in expected_chart_groups:
        allowed_charts = expected_chart_groups[operation]

        if best_chart not in allowed_charts:
            _add_warning(
                warnings,
                f"Chart '{best_chart}' may not align with operation '{operation}'. "
                f"Expected one of: {sorted(allowed_charts)}"
            )

    return warnings


def validate_confidence_logic(plan: Dict[str, Any]) -> List[str]:
    warnings = []

    confidence_status = plan.get("confidence_status")
    requires_llm_fallback = plan.get("requires_llm_fallback")
    rule_strength = plan.get("rule_strength")
    rules_fired = plan.get("rules_fired", [])

    if confidence_status == "rule_high_confidence":
        if requires_llm_fallback:
            _add_warning(
                warnings,
                "rule_high_confidence plans should usually have requires_llm_fallback=false."
            )

        if rule_strength != "strong":
            _add_warning(
                warnings,
                "confidence_status is rule_high_confidence but rule_strength is not strong."
            )

        if not rules_fired:
            _add_warning(
                warnings,
                "confidence_status is rule_high_confidence but no rules_fired were recorded."
            )

    if confidence_status == "low_confidence":
        if requires_llm_fallback is False:
            _add_warning(
                warnings,
                "low_confidence plans should usually have requires_llm_fallback=true."
            )

    return warnings


# ============================================================
# Main Validator
# ============================================================

def validate_planner_schema(plan: Dict[str, Any]) -> Dict[str, Any]:
    """
    Validate a planner or mapped_plan dictionary.

    Returns:
    {
        "is_valid_schema": bool,
        "schema_errors": [...],
        "schema_warnings": [...]
    }
    """

    errors = []
    warnings = []

    if not isinstance(plan, dict):
        return {
            "is_valid_schema": False,
            "schema_errors": ["Plan must be a dictionary."],
            "schema_warnings": [],
        }

    errors.extend(validate_required_top_level_fields(plan))
    errors.extend(validate_allowed_values(plan))
    errors.extend(validate_types(plan))
    errors.extend(validate_required_data_roles(plan))
    errors.extend(validate_selected_columns(plan))
    errors.extend(validate_operation_requirements(plan))

    warnings.extend(validate_chart_operation_alignment(plan))
    warnings.extend(validate_confidence_logic(plan))

    return {
        "is_valid_schema": len(errors) == 0,
        "schema_errors": errors,
        "schema_warnings": warnings,
    }


def attach_schema_validation(plan: Dict[str, Any]) -> Dict[str, Any]:
    """
    Attach schema validation results directly to a plan.
    """

    validation = validate_planner_schema(plan)

    plan["is_valid_schema"] = validation["is_valid_schema"]
    plan["schema_errors"] = validation["schema_errors"]
    plan["schema_warnings"] = validation["schema_warnings"]

    return plan


# ============================================================
# Optional Convenience Gate
# ============================================================

def should_use_plan(plan: Dict[str, Any]) -> bool:
    """
    Decide if the main project should use this plan directly.

    For future merge:
    - True means safe to use directly.
    - False means route to fallback / main LLM PlannerAgent.
    """

    validation = validate_planner_schema(plan)

    if not validation["is_valid_schema"]:
        return False

    if plan.get("requires_llm_fallback") is True:
        return False

    if plan.get("confidence_status") in {
        "high_confidence",
        "rule_high_confidence",
        "medium_confidence",
    }:
        return True

    return False


# ============================================================
# Manual Test
# ============================================================

if __name__ == "__main__":
    sample_plan = {
        "intent": "correlation",
        "answer_depth": "visual_answer",
        "operation": "correlation",
        "best_chart": "scatter_plot",
        "chart_required": True,
        "required_data_roles": {
            "needs_numeric": True,
            "needs_category": False,
            "needs_datetime": False,
            "needs_text": False,
        },
        "selected_columns": {
            "measure_column": "MonthlyIncome",
            "secondary_measure_column": "Age",
            "dimension_column": None,
            "target_column": None,
            "time_column": None,
            "text_column": None,
        },
        "confidence_status": "rule_high_confidence",
        "requires_llm_fallback": False,
        "route_to": "ml_planner",
        "rules_fired": ["two_measure_relation_override"],
        "rule_strength": "strong",
    }

    print(validate_planner_schema(sample_plan))
    print("Should use plan:", should_use_plan(sample_plan))