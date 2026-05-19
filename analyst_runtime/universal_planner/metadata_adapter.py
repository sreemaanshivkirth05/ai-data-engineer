from typing import Any, Dict, List

import pandas as pd


def _as_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _as_int(value: Any, default: int = 0) -> int:
    try:
        if value is None:
            return default
        return int(value)
    except (TypeError, ValueError):
        return default


def _normalize_text(value: Any) -> str:
    return str(value or "").strip().lower().replace("_", " ").replace("-", " ")


def _infer_semantic_type_from_dtype(name: str, dtype: Any, unique_ratio: float = 0.0) -> str:
    dtype_text = str(dtype or "").lower()
    name_text = _normalize_text(name)

    if any(token in name_text for token in ["date", "time", "timestamp", "year", "month"]):
        return "datetime"

    if "datetime" in dtype_text or "date" in dtype_text:
        return "datetime"

    if "bool" in dtype_text:
        return "boolean"

    if any(token in dtype_text for token in ["int", "float", "double", "decimal", "number"]):
        return "numeric"

    if unique_ratio >= 0.95:
        return "text"

    return "category"


def _infer_role(name: str, semantic_type: str, unique_ratio: float = 0.0) -> str:
    name_text = _normalize_text(name)

    if any(token in name_text for token in ["id", "uuid", "key", "postal", "zip"]):
        return "id"

    if semantic_type == "numeric":
        if unique_ratio >= 0.98:
            return "identifier_or_measure"
        return "measure"

    if semantic_type == "datetime":
        return "time"

    if semantic_type == "text":
        return "text"

    if semantic_type in {"category", "categorical", "boolean"}:
        return "dimension"

    return "unknown"


def _infer_business_type(name: str, semantic_type: str) -> str:
    name_text = _normalize_text(name)

    keyword_groups = [
        ("money", ["sales", "revenue", "income", "price", "cost", "profit", "amount", "spend"]),
        ("quantity", ["quantity", "qty", "units", "volume", "count"]),
        ("rate", ["rate", "ratio", "percent", "percentage"]),
        ("time", ["date", "time", "year", "month", "timestamp"]),
        ("geography", ["country", "region", "state", "city", "location"]),
        ("segment", ["segment", "category", "department", "type", "group", "market"]),
        ("text", ["description", "comment", "review", "message", "note", "text"]),
    ]

    for business_type, keywords in keyword_groups:
        if any(keyword in name_text for keyword in keywords):
            return business_type

    if semantic_type == "numeric":
        return "numeric_measure"
    if semantic_type == "datetime":
        return "time"
    if semantic_type in {"category", "categorical", "boolean"}:
        return "categorical_dimension"
    if semantic_type == "text":
        return "text"

    return "unknown"


def _cardinality_type(unique_ratio: float, unique_count: int = 0) -> str:
    if unique_count <= 0:
        return "unknown"
    if unique_count <= 2:
        return "binary"
    if unique_count <= 20:
        return "low"
    if unique_ratio >= 0.8:
        return "high"
    return "medium"


def _normalize_semantic_type(value: Any) -> str:
    semantic_type = str(value or "unknown").strip().lower()

    mapping = {
        "metric": "numeric",
        "number": "numeric",
        "measure": "numeric",
        "categorical": "category",
        "string": "category",
        "object": "category",
        "date": "datetime",
        "time": "datetime",
    }

    return mapping.get(semantic_type, semantic_type)


def _normalize_column(column: Dict[str, Any], row_count: int = 0) -> Dict[str, Any]:
    name = str(column.get("name") or column.get("column") or "").strip()
    unique_count = _as_int(column.get("unique_count"), 0)
    unique_ratio = _as_float(column.get("unique_ratio"), 0.0)

    if not unique_ratio and row_count and unique_count:
        unique_ratio = unique_count / row_count

    semantic_type = _normalize_semantic_type(column.get("semantic_type"))
    if semantic_type in {"unknown", ""}:
        semantic_type = _infer_semantic_type_from_dtype(
            name,
            column.get("dtype"),
            unique_ratio,
        )

    role = str(column.get("role") or "").strip().lower()
    if not role:
        role = _infer_role(name, semantic_type, unique_ratio)

    business_type = str(column.get("business_type") or "").strip().lower()
    if not business_type:
        business_type = _infer_business_type(name, semantic_type)

    cardinality_type = str(column.get("cardinality_type") or "").strip().lower()
    if not cardinality_type:
        cardinality_type = _cardinality_type(unique_ratio, unique_count)

    return {
        "name": name,
        "semantic_type": semantic_type,
        "role": role,
        "business_type": business_type,
        "cardinality_type": cardinality_type,
        "unique_ratio": round(float(unique_ratio), 4),
    }


def normalize_planner_metadata(metadata: Any) -> Dict[str, Any]:
    """
    Normalize external metadata into the Universal Planner metadata shape.
    """

    if not isinstance(metadata, dict):
        metadata = {}

    raw_columns = metadata.get("columns") or metadata.get("column_profiles") or []
    if isinstance(raw_columns, dict):
        raw_columns = [
            {"name": name, **(value if isinstance(value, dict) else {})}
            for name, value in raw_columns.items()
        ]

    row_count = _as_int(metadata.get("row_count"), 0)
    columns = [
        _normalize_column(column, row_count=row_count)
        for column in raw_columns
        if isinstance(column, dict) and (column.get("name") or column.get("column"))
    ]

    column_count = _as_int(metadata.get("column_count"), len(columns))
    semantic_types = {column.get("semantic_type") for column in columns}
    roles = {column.get("role") for column in columns}

    return {
        "source_type": metadata.get("source_type") or metadata.get("dataset_format") or "unknown",
        "row_count": row_count,
        "column_count": column_count,
        "columns": columns,
        "has_numeric": bool(metadata.get("has_numeric")) or "numeric" in semantic_types or "measure" in roles,
        "has_category": bool(metadata.get("has_category")) or "category" in semantic_types or "dimension" in roles,
        "has_datetime": bool(metadata.get("has_datetime")) or "datetime" in semantic_types or "time" in roles,
        "has_text": bool(metadata.get("has_text")) or "text" in semantic_types or "text" in roles,
    }


def metadata_from_dataframe(df: Any) -> Dict[str, Any]:
    """
    Build Universal Planner metadata from a pandas DataFrame.
    """

    if not isinstance(df, pd.DataFrame):
        return normalize_planner_metadata({})

    row_count = int(len(df))
    columns: List[Dict[str, Any]] = []

    for name in df.columns:
        series = df[name]
        unique_count = int(series.nunique(dropna=True))
        unique_ratio = unique_count / row_count if row_count else 0.0
        semantic_type = _infer_semantic_type_from_dtype(name, series.dtype, unique_ratio)
        columns.append(
            {
                "name": str(name),
                "dtype": str(series.dtype),
                "semantic_type": semantic_type,
                "role": _infer_role(str(name), semantic_type, unique_ratio),
                "business_type": _infer_business_type(str(name), semantic_type),
                "cardinality_type": _cardinality_type(unique_ratio, unique_count),
                "unique_count": unique_count,
                "unique_ratio": round(float(unique_ratio), 4),
            }
        )

    return normalize_planner_metadata(
        {
            "source_type": "dataframe",
            "row_count": row_count,
            "column_count": int(len(df.columns)),
            "columns": columns,
        }
    )


def metadata_from_column_profiles(column_profiles: Any) -> Dict[str, Any]:
    """
    Build Universal Planner metadata from main-project style column profiles.
    """

    if not isinstance(column_profiles, list):
        column_profiles = []

    return normalize_planner_metadata(
        {
            "source_type": "column_profiles",
            "row_count": 0,
            "column_count": len(column_profiles),
            "columns": column_profiles,
        }
    )
