import os
import json
import warnings
from typing import Dict, Any, List

import pandas as pd


# -----------------------------
# Dataset Loading
# -----------------------------

def load_dataset(file_path: str) -> pd.DataFrame:
    """
    Load a dataset from CSV, Excel, JSON, or Parquet into a pandas DataFrame.
    """

    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Dataset file not found: {file_path}")

    ext = os.path.splitext(file_path)[1].lower()

    if ext == ".csv":
        return pd.read_csv(file_path)

    if ext in [".xlsx", ".xls"]:
        return pd.read_excel(file_path)

    if ext == ".json":
        return pd.read_json(file_path)

    if ext == ".parquet":
        return pd.read_parquet(file_path)

    raise ValueError(
        f"Unsupported file type: {ext}. "
        "Supported formats: .csv, .xlsx, .xls, .json, .parquet"
    )


def get_source_type(file_path: str) -> str:
    """
    Convert file extension into a source type label.
    """

    ext = os.path.splitext(file_path)[1].lower()

    source_map = {
        ".csv": "csv",
        ".xlsx": "excel",
        ".xls": "excel",
        ".json": "json",
        ".parquet": "parquet",
    }

    return source_map.get(ext, "unknown")


# -----------------------------
# Basic Helpers
# -----------------------------

def normalize_name(name: str) -> str:
    """
    Normalize a column name for keyword matching.
    """

    return (
        str(name)
        .lower()
        .replace("_", " ")
        .replace("-", " ")
        .strip()
    )


def compact_name(name: str) -> str:
    """
    Compact column name for safer matching.
    Example:
    - MonthlyIncome -> monthlyincome
    - Order Date -> orderdate
    """

    return (
        str(name)
        .lower()
        .replace("_", "")
        .replace("-", "")
        .replace(" ", "")
        .strip()
    )


def get_name_tokens(name: str) -> List[str]:
    """
    Split normalized column name into tokens.
    """

    return normalize_name(name).split()


def get_sample_values(series: pd.Series, limit: int = 5) -> List[str]:
    """
    Return clean sample values from a column.
    """

    return series.dropna().astype(str).head(limit).tolist()


def safe_unique_count(series: pd.Series) -> int:
    """
    Safely count unique values.
    """

    try:
        return int(series.nunique(dropna=True))
    except Exception:
        return 0


def get_cardinality_type(series: pd.Series, row_count: int, semantic_type: str) -> str:
    """
    Classify column cardinality.

    Useful for avoiding bad chart dimensions like:
    - customer_id
    - order_id
    - transaction_id
    """

    unique_count = safe_unique_count(series)

    if row_count == 0:
        return "unknown"

    unique_ratio = unique_count / row_count

    if semantic_type == "numeric":
        if unique_count <= 2:
            return "binary_numeric"
        if unique_ratio >= 0.9:
            return "high_unique_numeric"
        return "continuous_or_measure"

    if semantic_type == "datetime":
        return "time"

    if semantic_type == "text":
        return "free_text"

    if semantic_type == "boolean":
        return "boolean"

    # category
    if unique_count <= 2:
        return "binary_category"
    if unique_count <= 20:
        return "low_cardinality_category"
    if unique_ratio >= 0.8:
        return "high_cardinality_category"

    return "medium_cardinality_category"


# -----------------------------
# Name-Based Guards
# -----------------------------

def is_measure_name(column_name: str) -> bool:
    """
    Detect strong business-measure names.

    This prevents columns like MonthlyIncome, MonthlyRate, Revenue, Sales,
    Salary, Amount, Profit, Cost, Price, Spend, Quantity, Score, Rating, etc.
    from being incorrectly classified as time/date columns.
    """

    name = normalize_name(column_name)
    compact = compact_name(column_name)
    tokens = get_name_tokens(column_name)

    strong_measure_compacts = {
        "monthlyincome",
        "monthlyrate",
        "dailyincome",
        "dailyrate",
        "hourlyincome",
        "hourlyrate",
        "annualincome",
        "yearlyincome",
        "salary",
        "monthlysalary",
        "annualsalary",
        "wage",
        "income",
        "revenue",
        "sales",
        "amount",
        "profit",
        "price",
        "cost",
        "expense",
        "balance",
        "margin",
        "spend",
        "budget",
        "payment",
        "invoiceamount",
        "orderamount",
        "totalamount",
        "unitprice",
        "quantity",
        "qty",
        "count",
        "orders",
        "units",
        "items",
        "volume",
        "rating",
        "score",
        "grade",
        "rank",
        "satisfaction",
        "nps",
        "percent",
        "percentage",
        "ratio",
        "conversion",
        "ctr",
        "cvr",
    }

    measure_keywords = [
        "income",
        "salary",
        "wage",
        "revenue",
        "sales",
        "amount",
        "profit",
        "price",
        "cost",
        "expense",
        "balance",
        "margin",
        "spend",
        "budget",
        "payment",
        "quantity",
        "qty",
        "count",
        "orders",
        "units",
        "items",
        "volume",
        "rating",
        "score",
        "satisfaction",
        "nps",
        "percent",
        "percentage",
        "ratio",
        "rate",
    ]

    if compact in strong_measure_compacts:
        return True

    if any(keyword in compact for keyword in strong_measure_compacts):
        return True

    if any(keyword in tokens for keyword in measure_keywords):
        return True

    # CamelCase compact examples:
    # MonthlyIncome, DailyRate, HourlyRate, PercentSalaryHike
    compact_measure_fragments = [
        "income",
        "salary",
        "revenue",
        "sales",
        "amount",
        "profit",
        "price",
        "cost",
        "spend",
        "rate",
        "score",
        "rating",
        "satisfaction",
        "quantity",
        "count",
    ]

    if any(fragment in compact for fragment in compact_measure_fragments):
        return True

    return False


def is_identifier_name(column_name: str) -> bool:
    """
    Detect identifier-like columns.
    Uses token/phrase matching to avoid marking every column containing
    the letters 'id' as an identifier.
    """

    name = normalize_name(column_name)
    compact = compact_name(column_name)
    tokens = get_name_tokens(column_name)

    exact_identifier_names = {
        "id",
        "uuid",
        "key",
        "identifier",
        "order id",
        "customer id",
        "user id",
        "transaction id",
        "invoice id",
        "product id",
        "employee id",
        "employee number",
        "account id",
        "record id",
        "row id",
    }

    compact_identifier_names = {
        "id",
        "uuid",
        "userid",
        "useruuid",
        "customerid",
        "orderid",
        "transactionid",
        "invoiceid",
        "productid",
        "employeeid",
        "employeenumber",
        "accountid",
        "recordid",
        "rowid",
    }

    if name in exact_identifier_names:
        return True

    if compact in compact_identifier_names:
        return True

    if tokens and tokens[-1] in {"id", "uuid", "key"}:
        return True

    return False


def is_true_time_name(column_name: str) -> bool:
    """
    Detect real date/time columns while avoiding false positives:

    Good time columns:
    - OrderDate
    - CreatedAt
    - UpdatedAt
    - Timestamp
    - Year
    - Month
    - Quarter

    Not time columns:
    - MonthlyIncome
    - MonthlyRate
    - OverTime
    - TotalWorkingYears
    - YearsAtCompany
    """

    name = normalize_name(column_name)
    compact = compact_name(column_name)
    tokens = get_name_tokens(column_name)

    # Strong measure names should not become time columns.
    if is_measure_name(column_name):
        return False

    # HR/business duration columns are numeric measures, not datetime columns.
    duration_compacts = {
        "totalworkingyears",
        "yearsatcompany",
        "yearsincurrentrole",
        "yearssincelastpromotion",
        "yearswithcurrmanager",
        "trainingtimeslastyear",
    }

    if compact in duration_compacts:
        return False

    # Boolean/categorical columns that contain "time" should not become datetime.
    non_time_compacts = {
        "overtime",
        "over18",
        "fulltime",
        "parttime",
    }

    if compact in non_time_compacts:
        return False

    exact_time_names = {
        "date",
        "time",
        "datetime",
        "timestamp",
        "created",
        "updated",
        "created at",
        "updated at",
        "created on",
        "updated on",
        "order date",
        "ship date",
        "start date",
        "end date",
        "month",
        "year",
        "quarter",
        "day",
    }

    compact_time_names = {
        "date",
        "time",
        "datetime",
        "timestamp",
        "created",
        "updated",
        "createdat",
        "updatedat",
        "createdon",
        "updatedon",
        "orderdate",
        "shipdate",
        "startdate",
        "enddate",
        "eventdate",
        "transactiondate",
        "purchasedate",
        "month",
        "year",
        "quarter",
        "day",
    }

    if name in exact_time_names:
        return True

    if compact in compact_time_names:
        return True

    # Token-level safe detection.
    # Avoid substring errors like "monthlyincome" containing "month".
    if any(token in tokens for token in ["date", "datetime", "timestamp"]):
        return True

    if any(token in tokens for token in ["created", "updated"]) and any(
        token in tokens for token in ["at", "on", "date", "time"]
    ):
        return True

    return False


# -----------------------------
# Semantic Type Detection
# -----------------------------

def looks_like_boolean(series: pd.Series) -> bool:
    """
    Detect boolean-like columns.
    """

    sample = series.dropna().astype(str).str.lower().str.strip()

    if len(sample) == 0:
        return False

    unique_values = set(sample.unique())

    boolean_sets = [
        {"true", "false"},
        {"yes", "no"},
        {"y", "n"},
        {"0", "1"},
        {"active", "inactive"},
        {"passed", "failed"},
        {"success", "failure"},
    ]

    return any(unique_values.issubset(valid_set) for valid_set in boolean_sets)


def looks_like_datetime(series: pd.Series, column_name: str = "") -> bool:
    """
    Detect date-like columns while reducing pandas warning noise.

    Strategy:
    1. Use safe name detection, not loose substring detection.
    2. Try strict/common date formats first.
    3. Use fallback parser silently only if the name strongly suggests date.
    """

    name_suggests_date = is_true_time_name(column_name)

    sample = series.dropna().astype(str).head(50)

    if len(sample) == 0:
        return False

    # Avoid treating numeric measure columns as dates.
    if pd.api.types.is_numeric_dtype(series) and not name_suggests_date:
        return False

    common_formats = [
        "%Y-%m-%d",
        "%m/%d/%Y",
        "%d/%m/%Y",
        "%Y/%m/%d",
        "%m-%d-%Y",
        "%d-%m-%Y",
        "%Y-%m-%d %H:%M:%S",
        "%m/%d/%Y %H:%M:%S",
        "%d/%m/%Y %H:%M:%S",
    ]

    for fmt in common_formats:
        parsed = pd.to_datetime(sample, format=fmt, errors="coerce")
        if parsed.notna().mean() >= 0.7:
            return True

    # Fallback parser only when name strongly suggests date/time.
    if name_suggests_date:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            parsed = pd.to_datetime(sample, errors="coerce")

        return parsed.notna().mean() >= 0.7

    return False


def looks_like_text(series: pd.Series) -> bool:
    """
    Detect free-text columns such as reviews, comments, messages, feedback.
    """

    sample = series.dropna().astype(str).head(50)

    if len(sample) == 0:
        return False

    avg_length = sample.str.len().mean()
    avg_words = sample.str.split().str.len().mean()

    return avg_length >= 50 or avg_words >= 8


def detect_semantic_type(series: pd.Series, column_name: str = "") -> str:
    """
    Detect the semantic type of a column.

    Returns:
    - numeric
    - datetime
    - text
    - category
    - boolean
    """

    if looks_like_boolean(series):
        return "boolean"

    if pd.api.types.is_datetime64_any_dtype(series):
        return "datetime"

    if looks_like_datetime(series, column_name):
        return "datetime"

    if pd.api.types.is_numeric_dtype(series):
        return "numeric"

    if looks_like_text(series):
        return "text"

    return "category"


# -----------------------------
# Business Type Detection
# -----------------------------

def detect_business_type(column_name: str, series: pd.Series, semantic_type: str) -> str:
    """
    Detect richer business meaning of a column.

    Examples:
    - currency_or_amount
    - percentage
    - identifier
    - geography
    - rating_or_score
    - quantity_or_count
    - date_or_time
    - free_text

    Important:
    Order matters. Rating/satisfaction/work-life columns must be checked
    before geography and currency to avoid false matches like:
    - RelationshipSatisfaction -> geography because of "lat"
    - WorkLifeBalance -> currency because of "balance"
    """

    name = normalize_name(column_name)
    compact = compact_name(column_name)
    tokens = get_name_tokens(column_name)

    # --------------------------------------------------------
    # Strong rating / score / HR survey fields
    # --------------------------------------------------------

    rating_compact_names = {
        "relationshipsatisfaction",
        "environmentsatisfaction",
        "jobsatisfaction",
        "worklifebalance",
        "performancerating",
        "jobinvolvement",
        "joblevel",
        "stockoptionlevel",
        "education",
    }

    rating_keywords = [
        "rating",
        "score",
        "stars",
        "grade",
        "rank",
        "satisfaction",
        "nps",
        "work life balance",
        "worklifebalance",
        "involvement",
        "level",
    ]

    if compact in rating_compact_names:
        return "rating_or_score"

    if any(keyword in name for keyword in rating_keywords):
        return "rating_or_score"

    if any(keyword in compact for keyword in ["satisfaction", "rating", "score", "worklifebalance"]):
        return "rating_or_score"

    # --------------------------------------------------------
    # True date/time fields
    # --------------------------------------------------------

    if semantic_type == "datetime" or is_true_time_name(column_name):
        return "date_or_time"

    # --------------------------------------------------------
    # Identifiers
    # --------------------------------------------------------

    if is_identifier_name(column_name):
        return "identifier"

    # --------------------------------------------------------
    # Geography
    # Use safer matching.
    # Do not use loose substring matching for short tokens like "lat" or "lon"
    # because they can appear inside unrelated words.
    # --------------------------------------------------------

    geography_phrase_keywords = [
        "country",
        "state",
        "city",
        "region",
        "location",
        "zipcode",
        "postal",
        "territory",
        "province",
        "latitude",
        "longitude",
    ]

    geography_token_keywords = {
        "country",
        "state",
        "city",
        "region",
        "location",
        "zip",
        "zipcode",
        "postal",
        "territory",
        "province",
        "latitude",
        "longitude",
        "lat",
        "lon",
    }

    if any(keyword in name for keyword in geography_phrase_keywords):
        return "geography"

    if any(token in geography_token_keywords for token in tokens):
        return "geography"

    # --------------------------------------------------------
    # Percentage / rate fields
    # --------------------------------------------------------

    percentage_keywords = [
        "percent",
        "percentage",
        "%",
        "ratio",
        "conversion",
        "ctr",
        "cvr",
        "attrition rate",
        "churn rate",
        "cancellation rate",
    ]

    # Do NOT classify all columns containing "rate" as percentage.
    # Examples like MonthlyRate, DailyRate, HourlyRate may be numeric measures.
    if any(keyword in name for keyword in percentage_keywords):
        return "percentage"

    if compact.startswith("percent") or compact.endswith("percent"):
        return "percentage"

    # --------------------------------------------------------
    # Currency / amount fields
    # Avoid classifying WorkLifeBalance as currency just because it contains balance.
    # --------------------------------------------------------

    currency_keywords = [
        "sales",
        "revenue",
        "amount",
        "profit",
        "price",
        "cost",
        "income",
        "expense",
        "margin",
        "spend",
        "budget",
        "salary",
        "wage",
        "payment",
        "invoice",
    ]

    currency_exact_or_compact = {
        "balance",
        "accountbalance",
        "endingbalance",
        "openingbalance",
        "closingbalance",
        "currentbalance",
    }

    if any(keyword in name for keyword in currency_keywords):
        return "currency_or_amount"

    if any(keyword in compact for keyword in currency_keywords):
        return "currency_or_amount"

    if compact in currency_exact_or_compact:
        return "currency_or_amount"

    # --------------------------------------------------------
    # Quantity / count fields
    # --------------------------------------------------------

    quantity_keywords = [
        "quantity",
        "qty",
        "count",
        "orders",
        "units",
        "items",
        "volume",
        "number of",
        "num",
    ]

    if any(keyword in name for keyword in quantity_keywords):
        return "quantity_or_count"

    if any(keyword in tokens for keyword in quantity_keywords):
        return "quantity_or_count"

    # --------------------------------------------------------
    # Free text fields
    # --------------------------------------------------------

    text_keywords = [
        "review",
        "comment",
        "feedback",
        "message",
        "description",
        "ticket",
        "notes",
        "summary",
        "text",
    ]

    if semantic_type == "text" or any(keyword in name for keyword in text_keywords):
        return "free_text"

    # --------------------------------------------------------
    # Boolean / numeric / category fallback
    # --------------------------------------------------------

    if semantic_type == "boolean":
        return "boolean_flag"

    if semantic_type == "numeric":
        return "numeric_measure"

    if semantic_type == "category":
        return "categorical_dimension"

    return "unknown"


# -----------------------------
# Column Role Detection
# -----------------------------

def infer_column_role(
    column_name: str,
    semantic_type: str,
    business_type: str,
    cardinality_type: str,
    row_count: int,
    unique_count: int,
) -> str:
    """
    Infer the role of a column for analysis.

    Returns:
    - measure
    - dimension
    - time
    - text
    - id
    - boolean
    """

    name = normalize_name(column_name)

    if semantic_type == "datetime" or business_type == "date_or_time":
        return "time"

    if business_type == "identifier":
        return "id"

    # High-cardinality categories are often IDs/names.
    # But some names like Customer or Product can still be useful dimensions.
    if cardinality_type == "high_cardinality_category":
        if any(keyword in name for keyword in ["customer", "product", "employee", "vendor", "supplier"]):
            return "dimension"
        return "id"

    if semantic_type == "numeric":
        # Numeric IDs should not be treated as measures.
        if business_type == "identifier":
            return "id"

        return "measure"

    if semantic_type == "text":
        return "text"

    if semantic_type == "boolean":
        return "boolean"

    return "dimension"


# -----------------------------
# Dataset-Level Profiling
# -----------------------------

def profile_dataframe(df: pd.DataFrame, source_type: str = "unknown") -> Dict[str, Any]:
    """
    Create metadata for a pandas DataFrame.
    This metadata is passed into your ML planner and column mapper.
    """

    columns = []

    has_numeric = False
    has_category = False
    has_datetime = False
    has_text = False
    has_boolean = False
    has_geography = False
    has_identifier = False
    has_currency = False
    has_percentage = False

    row_count = int(len(df))

    for column in df.columns:
        series = df[column]

        semantic_type = detect_semantic_type(series, str(column))
        unique_count = safe_unique_count(series)
        cardinality_type = get_cardinality_type(series, row_count, semantic_type)
        business_type = detect_business_type(str(column), series, semantic_type)

        role = infer_column_role(
            column_name=str(column),
            semantic_type=semantic_type,
            business_type=business_type,
            cardinality_type=cardinality_type,
            row_count=row_count,
            unique_count=unique_count,
        )

        if semantic_type == "numeric":
            has_numeric = True
        elif semantic_type == "datetime":
            has_datetime = True
        elif semantic_type == "text":
            has_text = True
        elif semantic_type == "category":
            has_category = True
        elif semantic_type == "boolean":
            has_boolean = True

        if business_type == "geography":
            has_geography = True
        elif business_type == "identifier":
            has_identifier = True
        elif business_type == "currency_or_amount":
            has_currency = True
        elif business_type == "percentage":
            has_percentage = True

        column_metadata = {
            "name": str(column),
            "dtype": str(series.dtype),
            "semantic_type": semantic_type,
            "role": role,
            "business_type": business_type,
            "cardinality_type": cardinality_type,
            "null_count": int(series.isna().sum()),
            "null_percent": round(float(series.isna().mean() * 100), 2),
            "unique_count": unique_count,
            "unique_ratio": round(float(unique_count / row_count), 4) if row_count > 0 else 0.0,
            "sample_values": get_sample_values(series),
        }

        columns.append(column_metadata)

    metadata = {
        "source_type": source_type,
        "row_count": row_count,
        "column_count": int(len(df.columns)),
        "has_numeric": has_numeric,
        "has_category": has_category,
        "has_datetime": has_datetime,
        "has_text": has_text,
        "has_boolean": has_boolean,
        "has_geography": has_geography,
        "has_identifier": has_identifier,
        "has_currency": has_currency,
        "has_percentage": has_percentage,
        "columns": columns,
    }

    return metadata


def profile_file(file_path: str) -> Dict[str, Any]:
    """
    Load a file and return metadata.
    """

    df = load_dataset(file_path)
    source_type = get_source_type(file_path)
    metadata = profile_dataframe(df, source_type=source_type)

    return metadata


# -----------------------------
# Printing Helpers
# -----------------------------

def print_metadata_summary(metadata: Dict[str, Any]) -> None:
    """
    Print a readable summary of dataset metadata.
    """

    print("\n================ DATASET METADATA SUMMARY ================\n")

    print(f"Source Type: {metadata['source_type']}")
    print(f"Rows: {metadata['row_count']}")
    print(f"Columns: {metadata['column_count']}")
    print(f"Has Numeric: {metadata['has_numeric']}")
    print(f"Has Category: {metadata['has_category']}")
    print(f"Has Datetime: {metadata['has_datetime']}")
    print(f"Has Text: {metadata['has_text']}")
    print(f"Has Boolean: {metadata.get('has_boolean')}")
    print(f"Has Geography: {metadata.get('has_geography')}")
    print(f"Has Identifier: {metadata.get('has_identifier')}")
    print(f"Has Currency/Amount: {metadata.get('has_currency')}")
    print(f"Has Percentage: {metadata.get('has_percentage')}")

    print("\n---------------- COLUMN DETAILS ----------------\n")

    for col in metadata["columns"]:
        print(f"Column: {col['name']}")
        print(f"  dtype: {col['dtype']}")
        print(f"  semantic_type: {col['semantic_type']}")
        print(f"  role: {col['role']}")
        print(f"  business_type: {col['business_type']}")
        print(f"  cardinality_type: {col['cardinality_type']}")
        print(f"  null_percent: {col['null_percent']}%")
        print(f"  unique_count: {col['unique_count']}")
        print(f"  unique_ratio: {col['unique_ratio']}")
        print(f"  sample_values: {col['sample_values']}")
        print()


if __name__ == "__main__":
    file_path = input("Enter dataset path: ").strip()

    metadata = profile_file(file_path)

    print_metadata_summary(metadata)

    print("\n================ RAW METADATA JSON ================\n")
    print(json.dumps(metadata, indent=2))