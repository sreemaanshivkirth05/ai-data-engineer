from typing import Any, Dict

try:
    from .planner_schema_validator import should_use_plan
except ImportError:
    from planner_schema_validator import should_use_plan


CHART_TRANSLATION = {
    "bar_chart": "bar",
    "horizontal_bar_chart": "bar",
    "line_chart": "line",
    "scatter_plot": "scatter",
    "histogram": "histogram",
    "box_plot": "box",
    "heatmap": "heatmap",
    "correlation_heatmap": "heatmap",
    "kpi_card": "kpi",
    "multi_chart_dashboard": "dashboard",
    "table": "table",
    "none": "table",
}


OPERATION_TRANSLATION = {
    "mean": {
        "main_intent": "aggregation",
        "main_analysis_type": "aggregation",
        "main_aggregation": "mean",
        "operation_family": "aggregation",
    },
    "sum": {
        "main_intent": "aggregation",
        "main_analysis_type": "aggregation",
        "main_aggregation": "sum",
        "operation_family": "aggregation",
    },
    "min": {
        "main_intent": "aggregation",
        "main_analysis_type": "aggregation",
        "main_aggregation": "min",
        "operation_family": "aggregation",
    },
    "max": {
        "main_intent": "aggregation",
        "main_analysis_type": "aggregation",
        "main_aggregation": "max",
        "operation_family": "aggregation",
    },
    "count": {
        "main_intent": "aggregation",
        "main_analysis_type": "aggregation",
        "main_aggregation": "count",
        "operation_family": "aggregation",
    },
    "groupby_mean": {
        "main_intent": "comparison",
        "main_analysis_type": "comparison",
        "main_aggregation": "mean",
        "operation_family": "comparison",
    },
    "groupby_sum": {
        "main_intent": "comparison",
        "main_analysis_type": "comparison",
        "main_aggregation": "sum",
        "operation_family": "comparison",
    },
    "groupby_mean_sort_desc": {
        "main_intent": "ranking",
        "main_analysis_type": "ranking",
        "main_aggregation": "mean",
        "sort": "desc",
        "operation_family": "ranking",
    },
    "groupby_sum_sort_desc": {
        "main_intent": "ranking",
        "main_analysis_type": "ranking",
        "main_aggregation": "sum",
        "sort": "desc",
        "operation_family": "ranking",
    },
    "groupby_target_rate": {
        "main_intent": "target_rate",
        "main_analysis_type": "target_rate",
        "main_aggregation": "rate",
        "operation_family": "target_rate",
    },
    "groupby_target_rate_sort_desc": {
        "main_intent": "target_rate_ranking",
        "main_analysis_type": "target_rate_ranking",
        "main_aggregation": "rate",
        "sort": "desc",
        "operation_family": "target_rate_ranking",
    },
    "time_groupby_sum": {
        "main_intent": "trend_analysis",
        "main_analysis_type": "trend_analysis",
        "main_aggregation": "sum",
        "operation_family": "trend_analysis",
    },
    "time_groupby_mean": {
        "main_intent": "trend_analysis",
        "main_analysis_type": "trend_analysis",
        "main_aggregation": "mean",
        "operation_family": "trend_analysis",
    },
    "correlation": {
        "main_intent": "correlation",
        "main_analysis_type": "correlation",
        "main_aggregation": None,
        "operation_family": "correlation",
    },
    "correlation_heatmap": {
        "main_intent": "correlation_heatmap",
        "main_analysis_type": "correlation_heatmap",
        "main_aggregation": None,
        "operation_family": "correlation_heatmap",
    },
    "distribution": {
        "main_intent": "distribution",
        "main_analysis_type": "distribution",
        "main_aggregation": None,
        "operation_family": "distribution",
    },
    "outlier_check": {
        "main_intent": "outlier_check",
        "main_analysis_type": "outlier_check",
        "main_aggregation": None,
        "operation_family": "outlier_check",
    },
    "null_check": {
        "main_intent": "data_quality",
        "main_analysis_type": "data_quality",
        "main_aggregation": None,
        "operation_family": "data_quality",
    },
    "duplicate_check": {
        "main_intent": "data_quality",
        "main_analysis_type": "data_quality",
        "main_aggregation": None,
        "operation_family": "data_quality",
    },
    "data_quality_summary": {
        "main_intent": "data_quality",
        "main_analysis_type": "data_quality",
        "main_aggregation": None,
        "operation_family": "data_quality",
    },
    "full_dataset_analysis": {
        "main_intent": "summary_analysis",
        "main_analysis_type": "summary_analysis",
        "main_aggregation": None,
        "operation_family": "summary_analysis",
    },
    "diagnostic_analysis": {
        "main_intent": "diagnostic_analysis",
        "main_analysis_type": "diagnostic_analysis",
        "main_aggregation": None,
        "operation_family": "diagnostic_analysis",
    },
    "forecast": {
        "main_intent": "forecasting",
        "main_analysis_type": "forecasting",
        "main_aggregation": None,
        "operation_family": "forecasting",
    },
}


def _get_selected_columns(mapped_plan: Dict[str, Any]) -> Dict[str, Any]:
    selected_columns = mapped_plan.get("selected_columns")

    if isinstance(selected_columns, dict):
        return selected_columns

    return {}


def _translate_chart(chart_type: Any) -> Any:
    return CHART_TRANSLATION.get(chart_type, chart_type)


def _translate_operation(operation: Any) -> Dict[str, Any]:
    defaults = {
        "main_intent": operation,
        "main_analysis_type": operation,
        "main_aggregation": None,
        "sort": None,
        "limit": None,
        "operation_family": operation,
    }
    translated = OPERATION_TRANSLATION.get(operation, {})
    defaults.update(translated)
    return defaults


def _main_target(selected: Dict[str, Any]) -> Any:
    return (
        selected.get("measure_column")
        or selected.get("target_column")
        or selected.get("text_column")
    )


def _main_drivers(selected: Dict[str, Any]) -> list:
    drivers = [
        selected.get("dimension_column"),
        selected.get("secondary_measure_column"),
    ]
    return [driver for driver in drivers if driver]


def _empty_contract(validation_errors=None) -> Dict[str, Any]:
    validation_errors = validation_errors or []
    return {
        "analysis_intent": None,
        "operation": None,
        "chart_type": None,
        "columns": {
            "measure": None,
            "secondary_measure": None,
            "dimension": None,
            "target": None,
            "time": None,
            "text": None,
        },
        "safe_to_execute": False,
        "needs_fallback": True,
        "confidence_status": None,
        "planner_source": None,
        "validation_errors": validation_errors,
        "validation_warnings": [],
        "main_intent": None,
        "main_analysis_type": None,
        "main_aggregation": None,
        "main_chart": None,
        "main_target": None,
        "main_drivers": [],
        "main_time_column": None,
        "sort": None,
        "limit": None,
        "operation_family": None,
        "raw_universal_operation": None,
        "raw_universal_chart_type": None,
    }


def adapt_mapped_plan_for_platform(mapped_plan: Dict[str, Any]) -> Dict[str, Any]:
    """
    Convert an internal mapped planner output into the platform contract.
    """

    if not isinstance(mapped_plan, dict):
        return _empty_contract(["Mapped plan must be a dictionary."])

    selected = _get_selected_columns(mapped_plan)
    validation_errors = mapped_plan.get("schema_errors") or []
    validation_warnings = mapped_plan.get("schema_warnings") or []
    safe_to_execute = should_use_plan(mapped_plan)
    operation = mapped_plan.get("operation")
    chart_type = mapped_plan.get("best_chart")
    translated_operation = _translate_operation(operation)
    main_chart = _translate_chart(chart_type)

    return {
        "analysis_intent": mapped_plan.get("intent"),
        "operation": operation,
        "chart_type": chart_type,
        "columns": {
            "measure": selected.get("measure_column"),
            "secondary_measure": selected.get("secondary_measure_column"),
            "dimension": selected.get("dimension_column"),
            "target": selected.get("target_column"),
            "time": selected.get("time_column"),
            "text": selected.get("text_column"),
        },
        "safe_to_execute": safe_to_execute,
        "needs_fallback": not safe_to_execute,
        "confidence_status": mapped_plan.get("confidence_status"),
        "planner_source": mapped_plan.get("planner_source"),
        "validation_errors": validation_errors,
        "validation_warnings": validation_warnings,
        "main_intent": translated_operation.get("main_intent"),
        "main_analysis_type": translated_operation.get("main_analysis_type"),
        "main_aggregation": translated_operation.get("main_aggregation"),
        "main_chart": main_chart,
        "main_target": _main_target(selected),
        "main_drivers": _main_drivers(selected),
        "main_time_column": selected.get("time_column"),
        "sort": translated_operation.get("sort"),
        "limit": translated_operation.get("limit"),
        "operation_family": translated_operation.get("operation_family"),
        "raw_universal_operation": operation,
        "raw_universal_chart_type": chart_type,
    }
