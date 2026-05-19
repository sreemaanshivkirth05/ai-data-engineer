import os
import pickle
import logging
import re
from typing import Dict, Any, Optional


logger = logging.getLogger("rule_correction")

CONFIDENCE_THRESHOLD = 0.65

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_MODEL_FILE = os.path.join(BASE_DIR, "models", "planner_model.pkl")
MODEL_FILE = os.environ.get("UNIVERSAL_PLANNER_MODEL_PATH") or DEFAULT_MODEL_FILE
_MODEL_CACHE = None


# ============================================================
# Strong Rule Confidence Settings
# ============================================================

STRONG_RULE_NAMES = {
    # scalar / aggregation
    "hard_scalar_aggregation_guard",
    "pre_temporal_aggregation_override",
    "groupby_mean_override",

    # income/groupby/ranking
    "income_groupby_mean_ranking_override",
    "income_groupby_mean_comparison_override",

    # target-rate / HR attrition
    "target_rate_ranking_override",
    "target_rate_causal_override",
    "target_rate_comparison_override",
    "employee_leaving_diagnostic_override",

    # correlation
    "correlation_heatmap_override",
    "two_measure_comparison_override",
    "correlation_pair_override",
    "two_measure_relation_override",
    "general_correlation_summary_override",

    # distribution / outliers
    "distribution_override",
    "outlier_override",

    # data quality
    "incomplete_data_override",
    "data_quality_override",

    # text
    "word_frequency_override",
    "word_frequency_general_override",
    "sentiment_override",
    "text_summary_override",

    # temporal
    "log_temporal_override",
    "metric_temporal_override",
    "numeric_rate_temporal_override",
    "numeric_rate_correlation_override",
    "numeric_rate_groupby_sum_ranking_override",
    "numeric_rate_groupby_sum_comparison_override",
    "unit_price_groupby_mean_override",
}


MEDIUM_RULE_NAMES = {
    "summary_override",
    "diagnostic_override",
    "ranking_override",
    "comparison_override",
    "correlation_affect_override",
    "general_correlation_override",
    "forecasting_override",
}


# ============================================================
# Model Loading + Prediction Confidence
# ============================================================

def resolve_model_file() -> str:
    """
    Resolve the planner model path for local and packaged execution.
    """

    env_path = os.environ.get("UNIVERSAL_PLANNER_MODEL_PATH")
    model_path = env_path or DEFAULT_MODEL_FILE

    if os.path.exists(model_path):
        return model_path

    source = (
        "UNIVERSAL_PLANNER_MODEL_PATH"
        if env_path
        else "default relative path ../models/planner_model.pkl"
    )
    raise FileNotFoundError(
        "Universal Planner model file not found.\n"
        f"Resolved path: {model_path}\n"
        f"Source: {source}\n"
        "Set UNIVERSAL_PLANNER_MODEL_PATH to the trained planner_model.pkl "
        "or place planner_model.pkl in the repository models/ directory."
    )


def load_model():
    """
    Load and cache the trained planner model.
    """

    global _MODEL_CACHE

    if _MODEL_CACHE is not None:
        return _MODEL_CACHE

    model_path = resolve_model_file()

    with open(model_path, "rb") as file:
        artifact = pickle.load(file)

    _MODEL_CACHE = artifact["model"], artifact["target_columns"]
    return _MODEL_CACHE


def predict_with_confidence(model, target_columns, X):
    """
    Predict labels and confidence scores.

    Supports:
    1. A direct MultiOutputClassifier
    2. A scikit-learn Pipeline where the final step is MultiOutputClassifier
    """

    predictions = {}
    confidence = {}

    # Case 1: sklearn Pipeline
    if hasattr(model, "steps"):
        transformer = model[:-1]
        final_estimator = model.steps[-1][1]

        X_transformed = transformer.transform(X)

        if hasattr(final_estimator, "estimators_"):
            for i, estimator in enumerate(final_estimator.estimators_):
                label = target_columns[i]

                if hasattr(estimator, "predict_proba"):
                    proba = estimator.predict_proba(X_transformed)[0]
                    max_conf = proba.max()
                    predicted_class = estimator.classes_[proba.argmax()]
                else:
                    predicted_class = estimator.predict(X_transformed)[0]
                    max_conf = 1.0

                predictions[label] = predicted_class
                confidence[label] = round(float(max_conf), 3)

            return predictions, confidence

        raw_prediction = model.predict(X)[0]

        for i, label in enumerate(target_columns):
            predictions[label] = raw_prediction[i]
            confidence[label] = 1.0

        return predictions, confidence

    # Case 2: direct MultiOutputClassifier
    if hasattr(model, "estimators_"):
        for i, estimator in enumerate(model.estimators_):
            label = target_columns[i]

            if hasattr(estimator, "predict_proba"):
                proba = estimator.predict_proba(X)[0]
                max_conf = proba.max()
                predicted_class = estimator.classes_[proba.argmax()]
            else:
                predicted_class = estimator.predict(X)[0]
                max_conf = 1.0

            predictions[label] = predicted_class
            confidence[label] = round(float(max_conf), 3)

        return predictions, confidence

    # Final fallback
    raw_prediction = model.predict(X)[0]

    for i, label in enumerate(target_columns):
        predictions[label] = raw_prediction[i]
        confidence[label] = 1.0

    return predictions, confidence


# ============================================================
# General Helpers
# ============================================================

def bool_from_string(value: str) -> bool:
    return str(value).lower().strip() == "true"


def normalize_text(text: str) -> str:
    """
    Normalize user question text.
    """

    return str(text).lower().replace("_", " ").replace("-", " ").strip()


def tokenize(text: str):
    """
    Tokenize safely so short words like 'min' do not match inside words like 'upcoming'.
    """

    return re.findall(r"[a-zA-Z0-9]+", normalize_text(text))


def has_token(question: str, token: str) -> bool:
    return normalize_text(token) in tokenize(question)


def has_any_keyword(question: str, keywords) -> bool:
    """
    Phrase/substring matcher.

    Use this for multi-word phrases and normal keywords.
    Do NOT use this for tiny tokens like min/max because it can match substrings.
    """

    q = normalize_text(question)
    return any(normalize_text(keyword) in q for keyword in keywords)


def build_model_input(question: str, metadata: Optional[Dict[str, Any]] = None) -> str:
    """
    Build the text input used by the ML model.
    Metadata is added so the planner learns dataset-aware behavior.
    """

    if not metadata:
        return question

    metadata_text = (
        f" source_type:{metadata.get('source_type', 'unknown')}"
        f" has_numeric:{metadata.get('has_numeric', 'unknown')}"
        f" has_category:{metadata.get('has_category', 'unknown')}"
        f" has_datetime:{metadata.get('has_datetime', 'unknown')}"
        f" has_text:{metadata.get('has_text', 'unknown')}"
    )

    return question + metadata_text


def get_recommended_charts(best_chart: str):
    chart_map = {
        "none": [],
        "kpi_card": ["kpi_card", "table"],
        "table": ["table", "kpi_card"],
        "bar_chart": ["bar_chart", "horizontal_bar_chart", "table"],
        "horizontal_bar_chart": ["horizontal_bar_chart", "bar_chart", "table"],
        "line_chart": ["line_chart", "area_chart", "bar_chart", "table"],
        "area_chart": ["area_chart", "line_chart", "bar_chart"],
        "histogram": ["histogram", "box_plot", "table"],
        "box_plot": ["box_plot", "histogram", "table"],
        "scatter_plot": ["scatter_plot", "correlation_heatmap", "table"],
        "heatmap": ["heatmap", "table"],
        "correlation_heatmap": ["correlation_heatmap", "scatter_plot", "table"],
        "multi_chart_dashboard": [
            "kpi_cards",
            "bar_chart",
            "line_chart",
            "histogram",
            "correlation_heatmap",
            "table",
        ],
    }

    return chart_map.get(best_chart, ["table"])


def get_fallback_chart(plan: Dict[str, Any]) -> str:
    if not plan["chart_required"]:
        return "table"

    if plan["best_chart"] in ["line_chart", "area_chart"]:
        return "bar_chart"

    if plan["best_chart"] in ["scatter_plot", "heatmap", "correlation_heatmap"]:
        return "table"

    if plan["best_chart"] == "none":
        return "none"

    return "table"


def force_plan(
    plan: Dict[str, Any],
    intent: str,
    answer_depth: str,
    operation: str,
    best_chart: str,
    chart_required: bool,
    needs_numeric: bool,
    needs_category: bool,
    needs_datetime: bool,
    needs_text: bool,
) -> Dict[str, Any]:
    plan["intent"] = intent
    plan["answer_depth"] = answer_depth
    plan["operation"] = operation
    plan["best_chart"] = best_chart
    plan["chart_required"] = chart_required
    plan["required_data_roles"]["needs_numeric"] = needs_numeric
    plan["required_data_roles"]["needs_category"] = needs_category
    plan["required_data_roles"]["needs_datetime"] = needs_datetime
    plan["required_data_roles"]["needs_text"] = needs_text

    return plan


def looks_like_two_measure_comparison(question: str) -> bool:
    """
    Detect questions like:
    - Compare sales and profit
    - Compare treatment cost and patient count
    - Compare humidity and pressure

    These should be correlation/scatter-style, not group-by category comparison.
    """

    q = normalize_text(question)

    if "compare" not in q:
        return False

    if " and " not in q:
        return False

    grouping_signals = [
        " by ",
        " across ",
        " grouped by ",
        " break down ",
        " breakdown ",
    ]

    if any(signal in q for signal in grouping_signals):
        return False

    return True


def get_rule_strength(rules_fired) -> str:
    """
    Determine how much we should trust the rule correction.

    strong:
        Deterministic question pattern with clear expected operation/chart.

    medium:
        Useful rule, but may still need main project LLM review later.

    none:
        No rule correction.
    """

    if not rules_fired:
        return "none"

    fired = set(rules_fired)

    if fired.intersection(STRONG_RULE_NAMES):
        return "strong"

    if fired.intersection(MEDIUM_RULE_NAMES):
        return "medium"

    return "medium"


# ============================================================
# Rule Correction Layer
# ============================================================

def apply_chart_corrections(question: str, plan: Dict[str, Any]) -> Dict[str, Any]:
    """
    Correct common mistakes made by the ML model.

    Important ordering:
    1. Group-by mean override before hard scalar aggregation.
    2. Hard scalar aggregation guard before temporal.
    3. Text-analysis rules before summary-analysis.
    4. Forecasting before scalar min/max.
    5. Numeric rate measure guards before binary target-rate rules.
    6. Binary target/outcome-rate rules before generic correlation.
    7. Correlation rules before temporal rules.
    8. Distribution/outlier before temporal trend rules.
    9. Grouped income/rate guard before temporal trend detection.
    10. Trend rules before comparison/ranking.
    11. Scalar min/max before ranking.
    """

    q = normalize_text(question)

    original = {
        "intent": plan.get("intent"),
        "operation": plan.get("operation"),
        "best_chart": plan.get("best_chart"),
    }

    def _fire(rule_name: str, forced: Dict[str, Any]) -> Dict[str, Any]:
        forced["rules_fired"] = [rule_name]

        logger.info(
            {
                "question": question,
                "rules_fired": [rule_name],
                "original_intent": original["intent"],
                "corrected_intent": forced.get("intent"),
                "original_operation": original["operation"],
                "corrected_operation": forced.get("operation"),
                "original_best_chart": original["best_chart"],
                "corrected_best_chart": forced.get("best_chart"),
            }
        )

        return forced

    # ========================================================
    # 0. Cleaned question for typo-tolerant rules
    # ========================================================

    q_clean = (
        q.replace("inocme", "income")
        .replace("incmoe", "income")
        .replace("incoem", "income")
        .replace("montly", "monthly")
    )

    # ========================================================
    # Keyword groups
    # ========================================================

    metric_keywords = [
        "sales",
        "revenue",
        "profit",
        "quantity",
        "discount",
        "salary",
        "bonus",
        "performance score",
        "attrition rate",
        "spend",
        "clicks",
        "impressions",
        "conversion rate",
        "treatment cost",
        "patient count",
        "length of stay",
        "error count",
        "request count",
        "latency",
        "rating",
        "resolution time",
        "temperature",
        "humidity",
        "pressure",
        "score",
        "attendance",
        "expense",
        "income",
        "monthly income",
        "monthly rate",
        "daily rate",
        "hourly rate",
        "budget",
        "orders",
        "amount",
        "price",
        "cost",
        "age",
    ]

    scalar_aggregation_metrics = [
        "monthly income",
        "monthly rate",
        "daily rate",
        "hourly rate",
        "income",
        "salary",
        "bonus",
        "age",
        "revenue",
        "sales",
        "profit",
        "quantity",
        "amount",
        "expense",
        "cost",
        "price",
        "budget",
        "score",
        "rating",
        "latency",
        "resolution time",
        "treatment cost",
        "patient count",
        "temperature",
        "humidity",
        "pressure",
    ]

    scalar_aggregation_starts = [
        "what is the average",
        "what is average",
        "what's the average",
        "show average",
        "average",
        "mean",
        "what is the mean",
        "show mean",
        "what is the total",
        "show total",
        "total",
        "sum",
        "overall",
        "give me overall",
    ]

    text_context_keywords = [
        "review",
        "reviews",
        "comment",
        "comments",
        "feedback",
        "customer feedback",
        "message",
        "messages",
        "log message",
        "log messages",
        "ticket",
        "tickets",
        "support",
        "support ticket",
        "support tickets",
        "ticket description",
        "ticket descriptions",
        "description",
        "descriptions",
        "open response",
        "open responses",
        "open ended",
        "open-ended",
        "responses",
        "complaint",
        "complaints",
        "theme",
        "themes",
        "topic",
        "topics",
    ]

    word_frequency_keywords = [
        "common words",
        "word frequency",
        "frequent words",
        "frequent terms",
        "top keywords",
        "keywords",
        "repeated words",
        "phrases appear",
        "most mentioned topics",
        "mentioned topics",
        "topics mentioned most",
        "topics are mentioned most",
        "what topics are mentioned",
        "support ticket topics",
        "topics in support tickets",
        "most common topics",
        "common topics",
        "complaint words",
        "words appear",
        "words appear most",
        "words appear most often",
        "most often in reviews",
        "what words appear",
        "what words appear in",
        "frequent words in ticket descriptions",
        "common support ticket topics",
        "common review keywords",
        "common words in customer reviews",
        "show topics",
        "show word frequency",
        "find frequent terms",
        "find repeated words",
    ]

    sentiment_keywords = [
        "sentiment",
        "sentiment breakdown",
        "positive or negative",
        "positive",
        "negative",
        "happy",
        "satisfaction",
        "satisfied",
        "dissatisfied",
        "sound negative",
        "customer happiness",
        "customers happy",
        "user satisfaction",
        "mostly positive",
        "mostly negative",
        "classify sentiment",
    ]

    text_summary_keywords = [
        "summary of reviews",
        "summary of review",
        "summary of comments",
        "summary of feedback",
        "summary of customer feedback",
        "summary of complaints",
        "summary of complaint",
        "summary of log messages",
        "summary of log message",
        "summary of ticket descriptions",
        "summary of tickets",
        "give me a summary of reviews",
        "give me a summary of complaints",
        "give me a summary of log messages",
        "give me a summary of ticket descriptions",
        "review text",
        "comments say",
        "customer complaints",
        "feedback messages",
        "users saying",
        "support ticket descriptions",
        "read the comments",
        "main theme",
        "main themes",
        "open ended responses",
        "open-ended responses",
        "summarize open ended",
        "summarize open-ended",
        "summarize customer",
        "summarize support",
        "summarize the review",
        "summarize the reviews",
        "summarize the comments",
        "summarize log messages",
        "summarize ticket descriptions",
        "what are users saying",
        "what do the reviews say",
        "what do the comments say",
        "what do the complaints say",
        "what do the log messages say",
    ]

    forecasting_keywords = [
        "forecast",
        "predict",
        "future",
        "next month",
        "next year",
        "upcoming",
        "what will",
        "look like in the future",
    ]

    temporal_signals = [
        "over time",
        "trend",
        "movement",
        "by day",
        "by date",
        "by week",
        "by month",
        "by year",
        "by hour",
        "per day",
        "per hour",
        "per week",
        "monthly",
        "daily",
        "weekly",
        "yearly",
        "hourly",
        "timestamp",
        "timeline",
        "time series",
        "changed over time",
        "change over time",
        "track",
        "plot",
    ]

    strong_temporal_signals = [
        "over time",
        "trend",
        "movement",
        "changed over time",
        "change over time",
        "by day",
        "by date",
        "by week",
        "by month",
        "by year",
        "by hour",
        "per day",
        "per hour",
        "per week",
        "daily",
        "weekly",
        "monthly trend",
        "plot",
        "track",
    ]

    log_temporal_keywords = [
        "errors over time",
        "error over time",
        "error count over time",
        "error trend",
        "errors trend",
        "errors by hour",
        "error by hour",
        "errors per hour",
        "error per hour",
        "failures over time",
        "failure trend",
        "failures by day",
        "exceptions over time",
        "exception trend",
        "exceptions per hour",
        "exceptions by hour",
        "request count over time",
        "request count by day",
        "latency over time",
        "latency trend",
        "latency by hour",
        "latency per hour",
        "plot latency by hour",
        "plot latency",
        "response time over time",
        "status codes over time",
        "traffic over time",
        "plot exceptions per hour",
        "track request count by day",
    ]

    aggregation_keywords = [
        "total sales",
        "total revenue",
        "total profit",
        "total amount",
        "total cost",
        "total price",
        "total expense",
        "total income",
        "total monthly income",
        "total monthly rate",
        "total daily rate",
        "total hourly rate",
        "total orders",
        "total clicks",
        "overall sales",
        "overall revenue",
        "overall profit",
        "overall amount",
        "overall impressions",
        "overall resolution time",
        "overall temperature",
        "overall bonus",
        "overall latency",
        "overall spend",
        "overall budget",
        "overall income",
        "overall expense",
        "company sales",
        "company revenue",
        "company wide sales",
        "company-wide sales",
        "company wide revenue",
        "company-wide revenue",
        "amount sold",
        "total sold",
        "overall sold",
        "sales of the company",
        "revenue of the company",
        "profit of the company",
        "what are the sales",
        "what is the sales",
        "what is the sale",
        "what are sales",
        "what are total sales",
        "what is total sales",
        "how much revenue",
        "how much sales",
        "how much did we make",
        "how much money did we make",
        "revenue did we make",
        "sales did we make",
        "sum of sales",
        "sum of revenue",
        "sum of profit",
        "sum of amount",
        "average sales",
        "average revenue",
        "average profit",
        "average amount",
        "average salary",
        "average score",
        "average temperature",
        "average response time",
        "average monthly income",
        "average monthly rate",
        "average daily rate",
        "average hourly rate",
        "show average",
        "mean ",
    ]

    summary_keywords = [
        "analyze this dataset",
        "analyze this file",
        "summary of this dataset",
        "business insights",
        "full analysis",
        "complete analysis",
        "analysis report",
        "key insights",
        "main insights",
        "main insights in this data",
        "what are the main insights",
        "what are the main insights in this data",
        "insights from this data",
        "analyze the dataset",
        "analyze this data",
        "do analysis",
        "perform analysis",
        "business overview",
        "executive summary",
        "dashboard-style analysis",
        "dataset is showing",
        "quick but complete analysis",
    ]

    correlation_heatmap_keywords = [
        "correlation heatmap",
        "correlation matrix",
        "numeric correlations",
        "all numeric correlations",
        "numeric feature correlation",
        "all numeric columns",
        "all numeric columns together",
        "relationships among all metrics",
        "relationship among all metrics",
        "numeric relationships",
        "heatmap of numeric relationships",
        "heatmap for sales profit and discount",
        "financial metrics",
        "compare all numeric columns",
        "show all numeric correlations",
        "build a correlation matrix",
        "create a heatmap",
        "create a heatmap of numeric relationships",
        "build heatmap for all measures",
        "heatmap for all measures",
        "all metrics heatmap",
        "measure correlation heatmap",
    ]

    general_correlation_keywords = [
        "correlation with",
        "correlation of",
        "correlation for",
        "correlate with",
        "correlated with",
        "relationship with",
        "relationship between",
    ]

    correlation_pair_keywords = [
        "clicks and conversions",
        "clicks vs conversions",
        "clicks versus conversions",
        "temperature and pressure",
        "temperature vs pressure",
        "temperature versus pressure",
        "temperature and humidity",
        "humidity and pressure",
        "sales and profit",
        "sales vs profit",
        "sales versus profit",
        "revenue and profit",
        "revenue vs profit",
        "price and quantity",
        "price vs quantity",
        "discount and profit",
        "discount vs profit",
        "expenses and income",
        "expenses vs income",
        "income and expenses",
        "monthly income and age",
        "monthly income vs age",
        "monthly income versus age",
        "age and monthly income",
        "age vs monthly income",
        "age versus monthly income",
        "response time related to error count",
        "response time and error count",
        "attendance and score",
        "attendance vs score",
        "spend affect revenue",
        "spend affects revenue",
        "does spend affect revenue",
        "spend impact revenue",
        "spend influence revenue",
        "conversion rate relate to revenue",
        "conversion rate related to revenue",
        "does conversion rate relate to revenue",
        "discount affect profit",
        "discount affects profit",
        "does discount affect profit",
        "does discount impact profit",
        "does discount influence profit",
        "price affect quantity",
        "price affects quantity",
        "does price affect quantity",
        "marketing spend affect revenue",
        "marketing spend affects revenue",
        "does marketing spend affect revenue",
    ]

    correlation_affect_words = [
        "affect",
        "affects",
        "impact",
        "impacts",
        "influence",
        "influences",
        "relate",
        "relates",
        "related",
        "relationship",
    ]

    numeric_rate_measure_phrases = [
        # True numeric rate measures only.
        # Do NOT include attrition/churn/cancellation here for HR datasets,
        # because those should route to binary target-rate operations.
        "conversion rate",
        "pass rate",
        "failure rate",
        "approval rate",
        "rejection rate",
        "click through rate",
        "click-through rate",
        "ctr",
    ]

    numeric_driver_phrases = [
        "salary",
        "bonus",
        "performance score",
        "spend",
        "revenue",
        "sales",
        "profit",
        "discount",
        "price",
        "quantity",
        "age",
        "income",
        "monthly income",
        "treatment cost",
        "patient count",
        "length of stay",
        "clicks",
        "impressions",
        "temperature",
        "humidity",
        "pressure",
        "score",
        "attendance",
        "latency",
        "response time",
        "resolution time",
    ]

    incomplete_data_keywords = [
        "incomplete records",
        "columns are incomplete",
        "incomplete data",
        "missing entries",
        "missing data",
        "missing values",
        "null values",
        "nulls",
        "blank values",
        "blanks",
        "empty values",
        "empty fields",
        "fields missing data",
        "missing fields",
        "which columns have missing",
        "which columns are missing",
        "show null value counts",
        "check missing entries",
    ]

    data_quality_keywords = [
        "duplicate",
        "duplicates",
        "data quality",
        "quality",
        "invalid",
        "clean",
        "cleaning",
        "errors in the data",
        "data errors",
        "bad records",
        "wrong values",
        "incorrect values",
    ]

    diagnostic_keywords = [
        "why",
        "reason",
        "cause",
        "caused",
        "drop",
        "decline",
        "spike",
        "increase",
        "decrease",
        "anomaly",
        "anomalies",
        "unusual",
        "abnormal",
        "investigate",
        "traffic logs",
    ]

    ranking_keywords = [
        "highest",
        "top",
        "best",
        "most",
        "largest",
        "rank",
        "ranking",
        "lowest",
        "least",
        "bottom",
        "maximum",
        "minimum",
        "biggest",
        "smallest",
        "leading",
        "worst",
        "who sold the most",
    ]

    ranking_entity_words = [
        "product",
        "country",
        "region",
        "department",
        "employee",
        "employee name",
        "job role",
        "customer",
        "customer name",
        "channel",
        "campaign",
        "service",
        "endpoint",
        "hospital",
        "diagnosis",
        "doctor",
        "device",
        "device type",
        "location",
        "category",
        "class",
        "subject",
        "student",
        "student name",
        "account",
        "account name",
        "expense category",
        "priority",
        "status code",
    ]

    distribution_keywords = [
        "distribution",
        "show distribution",
        "show me the distribution",
        "histogram",
        "spread",
        "range of",
        "range",
        "variance",
        "skew",
        "skewness",
    ]

    outlier_keywords = [
        "outlier",
        "outliers",
        "anomaly",
        "anomalies",
        "unusual values",
        "extreme values",
    ]

    comparison_keywords = [
        "by country",
        "by product",
        "by region",
        "by category",
        "by segment",
        "by customer",
        "by department",
        "by city",
        "by state",
        "by hospital",
        "by class",
        "by channel",
        "by service",
        "by endpoint",
        "by location",
        "by device type",
        "by priority",
        "by doctor",
        "by job role",
        "by status code",
        "across",
        "comparison",
        "breakdown",
        "grouped by",
        "group by",
        "break down",
        "compare",
    ]

    # ========================================================
    # 0. Group-by signal detection
    # ========================================================

    has_groupby_signal = has_any_keyword(
        q_clean,
        [
            " by ",
            " across ",
            " grouped by ",
            " group by ",
            "break down",
            "breakdown",
            "compare",
        ],
    )

    # ========================================================
    # 0.1 Grouped mean override before hard scalar aggregation
    # ========================================================

    if (
        has_any_keyword(q_clean, ["average", "mean"])
        and has_any_keyword(q_clean, scalar_aggregation_metrics)
        and has_groupby_signal
    ):
        return _fire(
            "groupby_mean_override",
            force_plan(
                plan,
                "comparison",
                "visual_answer",
                "groupby_mean",
                "bar_chart",
                True,
                True,
                True,
                False,
                False,
            ),
        )

    # ========================================================
    # 0.2 Hard scalar aggregation guard
    # ========================================================

    is_hard_scalar_aggregation = (
        any(q_clean.startswith(prefix) for prefix in scalar_aggregation_starts)
        and has_any_keyword(q_clean, scalar_aggregation_metrics)
        and not has_groupby_signal
    )

    if is_hard_scalar_aggregation:
        if (
            q_clean.startswith("what is the average")
            or q_clean.startswith("what is average")
            or q_clean.startswith("what's the average")
            or q_clean.startswith("show average")
            or q_clean.startswith("average")
            or q_clean.startswith("mean")
            or q_clean.startswith("what is the mean")
            or q_clean.startswith("show mean")
            or "average" in q_clean
            or has_token(q_clean, "mean")
        ):
            operation = "mean"
        else:
            operation = "sum"

        return _fire(
            "hard_scalar_aggregation_guard",
            force_plan(
                plan,
                "aggregation",
                "direct_answer",
                operation,
                "kpi_card",
                False,
                True,
                False,
                False,
                False,
            ),
        )

    # ========================================================
    # 1. Text rules first
    # ========================================================

    if has_any_keyword(q_clean, word_frequency_keywords) and has_any_keyword(q_clean, text_context_keywords):
        return _fire(
            "word_frequency_override",
            force_plan(
                plan,
                "text_analysis",
                "visual_answer",
                "word_frequency",
                "bar_chart",
                True,
                False,
                False,
                False,
                True,
            ),
        )

    if (
        ("words" in q_clean or "keywords" in q_clean or "topics" in q_clean or "frequent" in q_clean)
        and has_any_keyword(q_clean, text_context_keywords)
    ):
        return _fire(
            "word_frequency_general_override",
            force_plan(
                plan,
                "text_analysis",
                "visual_answer",
                "word_frequency",
                "bar_chart",
                True,
                False,
                False,
                False,
                True,
            ),
        )

    if has_any_keyword(q_clean, sentiment_keywords) and has_any_keyword(q_clean, text_context_keywords):
        return _fire(
            "sentiment_override",
            force_plan(
                plan,
                "text_analysis",
                "visual_answer",
                "sentiment_summary",
                "bar_chart",
                True,
                False,
                False,
                False,
                True,
            ),
        )

    if has_any_keyword(q_clean, text_summary_keywords) or (
        has_any_keyword(q_clean, ["summarize", "what do", "what are users saying", "main theme", "summary of"])
        and has_any_keyword(q_clean, text_context_keywords)
    ):
        return _fire(
            "text_summary_override",
            force_plan(
                plan,
                "text_analysis",
                "small_summary",
                "text_summary",
                "bar_chart",
                True,
                False,
                False,
                False,
                True,
            ),
        )

    # ========================================================
    # 2. Forecasting before scalar min/max
    # ========================================================

    if has_any_keyword(q_clean, forecasting_keywords):
        return _fire(
            "forecasting_override",
            force_plan(
                plan,
                "forecasting",
                "deep_analysis",
                "forecast",
                "line_chart",
                True,
                True,
                False,
                True,
                False,
            ),
        )

    # ========================================================
    # 2.3 Numeric rate measure guards
    # ========================================================

    has_numeric_rate_measure = has_any_keyword(q_clean, numeric_rate_measure_phrases)
    has_strong_temporal_signal = has_any_keyword(q_clean, strong_temporal_signals)
    has_correlation_signal = has_any_keyword(q_clean, correlation_affect_words)
    has_numeric_driver = has_any_keyword(q_clean, numeric_driver_phrases)

    if has_numeric_rate_measure and has_strong_temporal_signal:
        return _fire(
            "numeric_rate_temporal_override",
            force_plan(
                plan,
                "trend_analysis",
                "visual_answer",
                "time_groupby_sum",
                "line_chart",
                True,
                True,
                False,
                True,
                False,
            ),
        )

    if has_numeric_rate_measure and has_correlation_signal and has_numeric_driver:
        return _fire(
            "numeric_rate_correlation_override",
            force_plan(
                plan,
                "correlation",
                "visual_answer",
                "correlation",
                "scatter_plot",
                True,
                True,
                False,
                False,
                False,
            ),
        )

    if has_numeric_rate_measure and has_any_keyword(q_clean, comparison_keywords + ["by ", "across"]):
        if has_any_keyword(q_clean, ranking_keywords):
            return _fire(
                "numeric_rate_groupby_sum_ranking_override",
                force_plan(
                    plan,
                    "ranking",
                    "small_summary",
                    "groupby_sum_sort_desc",
                    "horizontal_bar_chart",
                    True,
                    True,
                    True,
                    False,
                    False,
                ),
            )

        return _fire(
            "numeric_rate_groupby_sum_comparison_override",
            force_plan(
                plan,
                "comparison",
                "visual_answer",
                "groupby_sum",
                "bar_chart",
                True,
                True,
                True,
                False,
                False,
            ),
        )

    # ========================================================
    # 2.5 Binary target / outcome-rate rules
    # ========================================================

    target_outcome_keywords = [
        "attrition",
        "attrition rate",
        "churn rate",
        "cancellation rate",
        "churn",
        "cancellation",
        "cancelled",
        "canceled",
        "is canceled",
        "is cancelled",
        "default",
        "defaulted",
        "fraud",
        "failure",
        "failed",
        "approval",
        "approved",
        "rejection",
        "rejected",
        "conversion",
        "converted",
        "leave",
        "leaves",
        "leaving",
        "left",
        "quit",
        "quits",
        "quitting",
        "resign",
        "resigned",
        "resignation",
        "turnover",
        "employee leaving",
        "employees leaving",
    ]

    target_dimension_phrases = [
        "by job role",
        "by department",
        "by overtime",
        "by over time",
        "by gender",
        "by education field",
        "by marital status",
        "by business travel",
        "by age group",
        "by job level",
        "by environment satisfaction",
        "by job satisfaction",
        "by work life balance",
        "by country",
        "by region",
        "by product",
        "by category",
        "by segment",
        "by plan",
        "by contract",
        "by hotel",
        "by market segment",
        "across job role",
        "across department",
        "across overtime",
        "across over time",
        "across gender",
        "across education field",
        "across marital status",
        "across business travel",
        "across country",
        "across region",
        "across product",
        "across category",
        "across segment",
        "across plan",
        "across contract",
        "across hotel",
        "across market segment",
    ]

    target_dimension_words = [
        "job role",
        "department",
        "overtime",
        "over time",
        "gender",
        "education field",
        "marital status",
        "business travel",
        "age group",
        "job level",
        "environment satisfaction",
        "job satisfaction",
        "work life balance",
        "country",
        "region",
        "product",
        "category",
        "segment",
        "plan",
        "contract",
        "hotel",
        "market segment",
    ]

    target_rate_question_signals = [
        "compare",
        "show",
        "break down",
        "breakdown",
        "group",
        "grouped",
        "across",
        "by ",
        "rate",
        "percentage",
        "percent",
    ]

    target_rate_causal_signals = [
        "affect",
        "affects",
        "impact",
        "impacts",
        "influence",
        "influences",
        "related to",
        "relationship",
        "does",
        "why",
    ]

    target_rate_ranking_signals = [
        "highest",
        "top",
        "most",
        "largest",
        "rank",
        "ranking",
        "lowest",
        "least",
        "smallest",
    ]

    has_target_outcome = has_any_keyword(q_clean, target_outcome_keywords)
    has_target_dimension_phrase = has_any_keyword(q_clean, target_dimension_phrases)
    has_target_dimension_word = has_any_keyword(q_clean, target_dimension_words)
    has_target_rate_signal = has_any_keyword(q_clean, target_rate_question_signals)
    has_target_causal_signal = has_any_keyword(q_clean, target_rate_causal_signals)
    has_target_ranking_signal = has_any_keyword(q_clean, target_rate_ranking_signals)

    is_binary_target_phrase = has_target_outcome and not has_numeric_rate_measure

    is_target_rate_question = (
        is_binary_target_phrase
        and (
            has_target_dimension_phrase
            or has_target_causal_signal
            or (has_target_dimension_word and has_target_rate_signal)
            or (has_target_dimension_word and has_target_ranking_signal)
            or "attrition rate" in q_clean
            or "churn rate" in q_clean
            or "cancellation rate" in q_clean
        )
    )

    if is_target_rate_question:
        if has_target_ranking_signal:
            return _fire(
                "target_rate_ranking_override",
                force_plan(
                    plan,
                    "ranking",
                    "small_summary",
                    "groupby_target_rate_sort_desc",
                    "horizontal_bar_chart",
                    True,
                    False,
                    True,
                    False,
                    False,
                ),
            )

        if has_target_causal_signal:
            return _fire(
                "target_rate_causal_override",
                force_plan(
                    plan,
                    "diagnostic_analysis",
                    "visual_answer",
                    "groupby_target_rate",
                    "bar_chart",
                    True,
                    False,
                    True,
                    False,
                    False,
                ),
            )

        return _fire(
            "target_rate_comparison_override",
            force_plan(
                plan,
                "comparison",
                "visual_answer",
                "groupby_target_rate",
                "bar_chart",
                True,
                False,
                True,
                False,
                False,
            ),
        )

    # ========================================================
    # 3. Correlation / two-measure comparison
    # ========================================================

    if has_any_keyword(q_clean, correlation_heatmap_keywords):
        return _fire(
            "correlation_heatmap_override",
            force_plan(
                plan,
                "correlation",
                "visual_answer",
                "correlation_heatmap",
                "heatmap",
                True,
                True,
                False,
                False,
                False,
            ),
        )

    two_measure_relation_signals = [
        "relationship between",
        "correlation between",
        "relation between",
        "related to",
        "relate to",
        "relates to",
        "vs",
        "versus",
        "against",
    ]

    broad_correlation_signals = [
        "correlation with",
        "correlation of",
        "correlation for",
        "correlate with",
        "correlated with",
        "what is the correlation with",
        "show correlation with",
        "show correlations with",
        "which columns correlate with",
        "which variables correlate with",
        "what variables correlate with",
    ]

    has_two_measure_relation_signal = has_any_keyword(q_clean, two_measure_relation_signals)
    has_broad_correlation_signal = has_any_keyword(q_clean, broad_correlation_signals)

    if looks_like_two_measure_comparison(q_clean):
        return _fire(
            "two_measure_comparison_override",
            force_plan(
                plan,
                "correlation",
                "visual_answer",
                "correlation",
                "scatter_plot",
                True,
                True,
                False,
                False,
                False,
            ),
        )

    if has_any_keyword(q_clean, correlation_pair_keywords):
        return _fire(
            "correlation_pair_override",
            force_plan(
                plan,
                "correlation",
                "visual_answer",
                "correlation",
                "scatter_plot",
                True,
                True,
                False,
                False,
                False,
            ),
        )

    if has_two_measure_relation_signal:
        return _fire(
            "two_measure_relation_override",
            force_plan(
                plan,
                "correlation",
                "visual_answer",
                "correlation",
                "scatter_plot",
                True,
                True,
                False,
                False,
                False,
            ),
        )

    if (
        has_any_keyword(q_clean, correlation_affect_words)
        and not has_any_keyword(q_clean, text_context_keywords)
        and not has_broad_correlation_signal
    ):
        return _fire(
            "correlation_affect_override",
            force_plan(
                plan,
                "correlation",
                "visual_answer",
                "correlation",
                "scatter_plot",
                True,
                True,
                False,
                False,
                False,
            ),
        )

    if has_broad_correlation_signal or has_any_keyword(q_clean, general_correlation_keywords):
        return _fire(
            "general_correlation_summary_override",
            force_plan(
                plan,
                "correlation",
                "small_summary",
                "correlation",
                "table",
                True,
                True,
                False,
                False,
                False,
            ),
        )

    # ========================================================
    # 3.5 General aggregation override before temporal rules
    # ========================================================

    aggregation_question_starts = [
        "what is the average",
        "what is average",
        "show average",
        "average",
        "mean",
        "what is the mean",
        "show mean",
        "what is the total",
        "show total",
        "total",
        "overall",
        "give me overall",
    ]

    is_aggregation_question = (
        any(q_clean.startswith(prefix) for prefix in aggregation_question_starts)
        and has_any_keyword(q_clean, metric_keywords)
        and not has_groupby_signal
    )

    if is_aggregation_question or (has_any_keyword(q_clean, aggregation_keywords) and not has_groupby_signal):
        if (
            q_clean.startswith("what is the average")
            or q_clean.startswith("what is average")
            or q_clean.startswith("show average")
            or q_clean.startswith("average")
            or q_clean.startswith("mean")
            or q_clean.startswith("what is the mean")
            or q_clean.startswith("show mean")
            or "average" in q_clean
            or has_token(q_clean, "mean")
        ):
            operation = "mean"
        else:
            operation = "sum"

        return _fire(
            "pre_temporal_aggregation_override",
            force_plan(
                plan,
                "aggregation",
                "direct_answer",
                operation,
                "kpi_card",
                False,
                True,
                False,
                False,
                False,
            ),
        )

    # ========================================================
    # 3.6 Distribution / outlier guard BEFORE temporal rules
    # ========================================================

    if has_any_keyword(q_clean, outlier_keywords):
        return _fire(
            "outlier_override",
            force_plan(
                plan,
                "distribution",
                "visual_answer",
                "outlier_check",
                "box_plot",
                True,
                True,
                False,
                False,
                False,
            ),
        )

    if has_any_keyword(q_clean, distribution_keywords):
        return _fire(
            "distribution_override",
            force_plan(
                plan,
                "distribution",
                "visual_answer",
                "distribution",
                "histogram",
                True,
                True,
                False,
                False,
                False,
            ),
        )

    # ========================================================
    # 3.7 Income/rate group-by guard before temporal rules
    # ========================================================

    income_measure_phrases = [
        "monthly income",
        "monthly rate",
        "daily rate",
        "hourly rate",
    ]

    group_dimension_phrases = [
        "by department",
        "by job role",
        "by gender",
        "by education field",
        "by marital status",
        "by business travel",
        "by overtime",
        "by over time",
        "by attrition",
        "across department",
        "across job role",
        "across gender",
        "across education field",
        "across marital status",
        "across business travel",
        "across overtime",
        "across over time",
        "across attrition",
    ]

    group_dimension_words = [
        "department",
        "job role",
        "gender",
        "education field",
        "marital status",
        "business travel",
        "overtime",
        "over time",
        "attrition",
    ]

    ranking_group_signals = [
        "highest",
        "top",
        "most",
        "largest",
        "rank",
        "ranking",
        "best",
    ]

    comparison_group_signals = [
        "compare",
        "show",
        "break down",
        "breakdown",
        "group",
        "grouped",
        "across",
        "by ",
    ]

    has_income_measure = has_any_keyword(q_clean, income_measure_phrases)
    has_group_phrase = has_any_keyword(q_clean, group_dimension_phrases)
    has_group_word = has_any_keyword(q_clean, group_dimension_words)
    has_ranking_signal = has_any_keyword(q_clean, ranking_group_signals)
    has_comparison_signal = has_any_keyword(q_clean, comparison_group_signals)

    is_grouped_income_question = (
        has_income_measure
        and not has_strong_temporal_signal
        and (
            has_group_phrase
            or (has_group_word and (has_ranking_signal or has_comparison_signal))
        )
    )

    if is_grouped_income_question:
        if has_ranking_signal:
            return _fire(
                "income_groupby_mean_ranking_override",
                force_plan(
                    plan,
                    "ranking",
                    "small_summary",
                    "groupby_mean_sort_desc",
                    "horizontal_bar_chart",
                    True,
                    True,
                    True,
                    False,
                    False,
                ),
            )

        return _fire(
            "income_groupby_mean_comparison_override",
            force_plan(
                plan,
                "comparison",
                "visual_answer",
                "groupby_mean",
                "bar_chart",
                True,
                True,
                True,
                False,
                False,
            ),
        )

    # ========================================================
    # 4. Temporal/trend rules before comparison/ranking
    # ========================================================

    if has_any_keyword(q_clean, log_temporal_keywords):
        return _fire(
            "log_temporal_override",
            force_plan(
                plan,
                "trend_analysis",
                "visual_answer",
                "time_groupby_sum",
                "line_chart",
                True,
                True,
                False,
                True,
                False,
            ),
        )

    if (
        has_any_keyword(q_clean, temporal_signals)
        and has_any_keyword(q_clean, metric_keywords)
        and not is_hard_scalar_aggregation
        and not is_aggregation_question
        and not is_grouped_income_question
    ):
        return _fire(
            "metric_temporal_override",
            force_plan(
                plan,
                "trend_analysis",
                "visual_answer",
                "time_groupby_sum",
                "line_chart",
                True,
                True,
                False,
                True,
                False,
            ),
        )

    # ========================================================
    # 5. Missing/null data quality
    # ========================================================

    if has_any_keyword(q_clean, incomplete_data_keywords):
        return _fire(
            "incomplete_data_override",
            force_plan(
                plan,
                "data_quality",
                "data_quality_answer",
                "null_check",
                "table",
                False,
                False,
                False,
                False,
                False,
            ),
        )

    # ========================================================
    # 6. Scalar min/max before ranking
    # ========================================================

    has_min_signal = (
        has_token(q_clean, "min")
        or has_token(q_clean, "minimum")
        or has_token(q_clean, "lowest")
        or has_token(q_clean, "smallest")
        or has_token(q_clean, "least")
    )

    has_max_signal = (
        has_token(q_clean, "max")
        or has_token(q_clean, "maximum")
        or has_token(q_clean, "highest")
        or has_token(q_clean, "largest")
        or has_token(q_clean, "biggest")
    )

    has_metric_signal = has_any_keyword(q_clean, metric_keywords)
    has_ranking_entity = has_any_keyword(q_clean, ranking_entity_words)

    if (has_min_signal or has_max_signal) and has_metric_signal and not has_ranking_entity:
        operation = "min" if has_min_signal else "max"

        return _fire(
            "single_value_minmax_override",
            force_plan(
                plan,
                "aggregation",
                "direct_answer",
                operation,
                "kpi_card",
                False,
                True,
                False,
                False,
                False,
            ),
        )

    # ========================================================
    # 7. Data quality
    # ========================================================

    if has_any_keyword(q_clean, data_quality_keywords) and not has_any_keyword(q_clean, temporal_signals):
        operation = "duplicate_check" if ("duplicate" in q_clean or "duplicates" in q_clean) else "data_quality_summary"

        return _fire(
            "data_quality_override",
            force_plan(
                plan,
                "data_quality",
                "data_quality_answer",
                operation,
                "table",
                False,
                False,
                False,
                False,
                False,
            ),
        )

    # ========================================================
    # 7.5 HR attrition / employee-leaving diagnostic
    # ========================================================

    employee_leaving_keywords = [
        "employees leaving",
        "employee leaving",
        "why are employees leaving",
        "why employees leave",
        "why do employees leave",
        "people leaving",
        "staff leaving",
        "workers leaving",
        "employee turnover",
        "turnover",
        "attrition reason",
        "attrition reasons",
        "why attrition",
        "why is attrition",
        "cause of attrition",
        "causes of attrition",
    ]

    if has_any_keyword(q_clean, employee_leaving_keywords):
        return _fire(
            "employee_leaving_diagnostic_override",
            force_plan(
                plan,
                "diagnostic_analysis",
                "deep_analysis",
                "groupby_target_rate",
                "bar_chart",
                True,
                False,
                True,
                False,
                False,
            ),
        )

    # ========================================================
    # 8. Summary / diagnostic
    # ========================================================

    if has_any_keyword(q_clean, summary_keywords):
        return _fire(
            "summary_override",
            force_plan(
                plan,
                "summary_analysis",
                "deep_analysis",
                "full_dataset_analysis",
                "multi_chart_dashboard",
                True,
                True,
                True,
                True,
                False,
            ),
        )

    if has_any_keyword(q_clean, diagnostic_keywords):
        return _fire(
            "diagnostic_override",
            force_plan(
                plan,
                "diagnostic_analysis",
                "deep_analysis",
                "diagnostic_analysis",
                "multi_chart_dashboard",
                True,
                True,
                True,
                True,
                False,
            ),
        )

    # ========================================================
    # 9. Ranking / distribution / comparison
    # ========================================================

    if has_any_keyword(q_clean, ranking_keywords):
        return _fire(
            "ranking_override",
            force_plan(
                plan,
                "ranking",
                "small_summary",
                "groupby_sum_sort_desc",
                "horizontal_bar_chart",
                True,
                True,
                True,
                False,
                False,
            ),
        )

    if has_any_keyword(q_clean, outlier_keywords):
        return _fire(
            "outlier_override",
            force_plan(
                plan,
                "distribution",
                "visual_answer",
                "outlier_check",
                "box_plot",
                True,
                True,
                False,
                False,
                False,
            ),
        )

    if has_any_keyword(q_clean, distribution_keywords):
        return _fire(
            "distribution_override",
            force_plan(
                plan,
                "distribution",
                "visual_answer",
                "distribution",
                "histogram",
                True,
                True,
                False,
                False,
                False,
            ),
        )

    # ========================================================
    # 9.1 Unit price comparison guard
    #
    # Unit price is an average-style metric. Summing unit prices by country,
    # product, category, or any dimension is usually not meaningful.
    # Example: "Compare unit price by country" -> groupby_mean.
    # ========================================================

    unit_price_phrases = [
        "unit price",
        "unitprice",
        "price per unit",
        "item price",
        "product price",
    ]

    if has_any_keyword(q_clean, unit_price_phrases) and has_any_keyword(q_clean, comparison_keywords):
        return _fire(
            "unit_price_groupby_mean_override",
            force_plan(
                plan,
                "comparison",
                "visual_answer",
                "groupby_mean",
                "bar_chart",
                True,
                True,
                True,
                False,
                False,
            ),
        )

    if has_any_keyword(q_clean, comparison_keywords):
        return _fire(
            "comparison_override",
            force_plan(
                plan,
                "comparison",
                "visual_answer",
                "groupby_sum",
                "bar_chart",
                True,
                True,
                True,
                False,
                False,
            ),
        )

    plan["rules_fired"] = []
    return plan


# ============================================================
# Public Prediction Functions
# ============================================================

def predict_plan_raw(question: str, metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Raw ML prediction without rule correction.
    Use this for ML-only evaluation.
    """

    model, target_columns = load_model()

    model_input = build_model_input(question, metadata)
    predictions, confidence = predict_with_confidence(model, target_columns, [model_input])

    plan = {
        "intent": predictions["intent"],
        "answer_depth": predictions["answer_depth"],
        "operation": predictions["operation"],
        "best_chart": predictions["best_chart"],
        "chart_required": bool_from_string(predictions["chart_required"]),
        "required_data_roles": {
            "needs_numeric": bool_from_string(predictions["needs_numeric"]),
            "needs_category": bool_from_string(predictions["needs_category"]),
            "needs_datetime": bool_from_string(predictions["needs_datetime"]),
            "needs_text": bool_from_string(predictions["needs_text"]),
        },
    }

    low_confidence_fields = [
        field for field, score in confidence.items()
        if score < CONFIDENCE_THRESHOLD
    ]

    min_confidence = min(confidence.values()) if confidence else 1.0

    plan["confidence_scores"] = confidence
    plan["min_confidence"] = round(float(min_confidence), 3)

    if low_confidence_fields:
        plan["low_confidence"] = low_confidence_fields
        plan["route_to"] = "llm_router"
        plan["ml_flag"] = "low_confidence_fallback"
        plan["confidence_status"] = "low_confidence"
        plan["requires_llm_fallback"] = True
        plan["planner_source"] = "raw_ml_low_confidence"
    else:
        plan["low_confidence"] = []
        plan["route_to"] = "ml_planner"
        plan["ml_flag"] = "high_confidence"
        plan["confidence_status"] = "high_confidence"
        plan["requires_llm_fallback"] = False
        plan["planner_source"] = "raw_ml"

    plan["recommended_charts"] = get_recommended_charts(plan["best_chart"])
    plan["fallback_chart"] = get_fallback_chart(plan)

    return plan


def predict_plan(question: str, metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Final planner prediction.

    Includes:
    1. Raw ML prediction
    2. Rule correction layer
    3. Recommended/fallback charts
    4. Confidence/fallback metadata

    Important Phase 1 hardening:
    - If a strong deterministic rule fires, trust the rule as rule_high_confidence,
      even if the raw ML model had low confidence.
    - This prevents correct rule-fixed plans from being unnecessarily routed to
      fallback during the future main-project merge.
    """

    plan = predict_plan_raw(question, metadata)

    raw_plan_snapshot = {
        "intent": plan["intent"],
        "operation": plan["operation"],
        "best_chart": plan["best_chart"],
    }

    raw_low_confidence_fields = list(plan.get("low_confidence", []))
    raw_min_confidence = plan.get("min_confidence", 1.0)
    raw_confidence_status = plan.get("confidence_status", "unknown")

    plan = apply_chart_corrections(question, plan)

    corrected_plan_snapshot = {
        "intent": plan["intent"],
        "operation": plan["operation"],
        "best_chart": plan["best_chart"],
    }

    rule_override_applied = raw_plan_snapshot != corrected_plan_snapshot
    rules_fired = plan.get("rules_fired", [])
    rule_strength = get_rule_strength(rules_fired)

    plan["rule_override_applied"] = rule_override_applied
    plan["raw_ml_prediction"] = raw_plan_snapshot
    plan["raw_low_confidence"] = raw_low_confidence_fields
    plan["raw_min_confidence"] = raw_min_confidence
    plan["raw_confidence_status"] = raw_confidence_status
    plan["rule_strength"] = rule_strength

    # ========================================================
    # Phase 1 hardened confidence logic
    # ========================================================

    if rules_fired and rule_strength == "strong":
        plan["requires_llm_fallback"] = False
        plan["confidence_status"] = "rule_high_confidence"
        plan["planner_source"] = "ml_plus_strong_rules"
        plan["route_to"] = "ml_planner"
        plan["ml_flag"] = "rule_high_confidence"

        # Keep raw low confidence for debugging, but do not let it control routing.
        plan["low_confidence"] = []
        plan["fallback_reason"] = None

    elif rules_fired and rule_strength == "medium":
        # Medium rules are useful, but should still be reviewable by the main project later.
        plan["requires_llm_fallback"] = False
        plan["confidence_status"] = "medium_confidence"
        plan["planner_source"] = "ml_plus_medium_rules"
        plan["route_to"] = "ml_planner"
        plan["ml_flag"] = "medium_confidence_rule_assisted"
        plan["low_confidence"] = raw_low_confidence_fields
        plan["fallback_reason"] = "Rule corrected the ML plan, but rule strength is medium."

    elif raw_low_confidence_fields:
        plan["requires_llm_fallback"] = True
        plan["confidence_status"] = "low_confidence"
        plan["planner_source"] = "raw_ml_low_confidence_recommend_llm_fallback"
        plan["route_to"] = "llm_router"
        plan["ml_flag"] = "low_confidence_fallback"
        plan["low_confidence"] = raw_low_confidence_fields
        plan["fallback_reason"] = "Raw ML confidence is below threshold and no strong rule corrected it."

    else:
        plan["requires_llm_fallback"] = False
        plan["confidence_status"] = "high_confidence"
        plan["planner_source"] = "raw_ml"
        plan["route_to"] = "ml_planner"
        plan["ml_flag"] = "high_confidence"
        plan["low_confidence"] = []
        plan["fallback_reason"] = None

    plan["min_confidence"] = raw_min_confidence
    plan["recommended_charts"] = get_recommended_charts(plan["best_chart"])
    plan["fallback_chart"] = get_fallback_chart(plan)

    return plan


# ============================================================
# Manual Test
# ============================================================

if __name__ == "__main__":
    test_metadata = {
        "source_type": "csv",
        "has_numeric": True,
        "has_category": True,
        "has_datetime": True,
        "has_text": False,
    }

    questions = [
        "What is the average monthly income?",
        "What is the average monthly income by department?",
        "Which department has the highest monthly income?",
        "Which job role has the highest monthly income?",
        "Compare monthly income by job role",
        "Show distribution of monthly income",
        "Show me the distribution of monthly income",
        "Show age distribution",
        "Show outliers in monthly income",
        "Compare attrition by job role",
        "Does overtime affect attrition?",
        "Why are employees leaving the company?",
        "Which department has the highest attrition?",
        "What is the correlation with monthly income?",
        "Does monthly income relate to age?",
        "Relationship between age and monthly income",
        "Build heatmap for all measures",
        "Show attrition rate trend over time",
        "How has attrition rate changed over time?",
        "Attrition Rate over time",
        "Compare attrition rate by department",
        "Which department has the highest attrition rate?",
        "Does salary affect attrition rate?",
        "Does bonus relate to attrition rate?",
        "Relationship between performance score and attrition rate",
        "Show conversion rate trend over time",
        "How has conversion rate changed over time?",
        "Compare conversion rate by region",
        "Forecast upcoming revenue",
    ]

    for question in questions:
        print("\nQuestion:", question)
        print(predict_plan(question, test_metadata))

# ============================================================
# Phase 2 Hotel Booking Cross-Dataset Overrides
# ============================================================

# Keep a reference to the previous rule layer. predict_plan() resolves the global
# apply_chart_corrections name at runtime, so this override is used automatically.
_LEGACY_APPLY_CHART_CORRECTIONS = apply_chart_corrections


def _hotel_has_any_keyword(question: str, keywords) -> bool:
    q = normalize_text(question)
    return any(normalize_text(keyword) in q for keyword in keywords)


def _hotel_is_average_daily_rate_question(question: str) -> bool:
    q = normalize_text(question)
    return _hotel_has_any_keyword(
        q,
        [
            "average daily rate",
            "daily rate",
            "adr",
            "room rate",
            "nightly rate",
            "rate per night",
        ],
    )


def apply_chart_corrections(question: str, plan: Dict[str, Any]) -> Dict[str, Any]:
    """
    Phase 2 hotel-booking hardened rule layer.

    These rules run before the legacy rules because the legacy aggregation logic
    can incorrectly collapse questions like:
    - "Which market segment has the highest average daily rate?"
    - "Show outliers in average daily rate"
    - "Show average daily rate trend by month"
    into scalar mean KPI plans.
    """

    q_clean = normalize_text(question)

    def _fire_hotel(rule_name: str, forced: Dict[str, Any]) -> Dict[str, Any]:
        forced["rules_fired"] = [rule_name]
        return forced

    average_daily_rate = _hotel_is_average_daily_rate_question(q_clean)

    ranking_signals = [
        "highest",
        "top",
        "largest",
        "most",
        "rank",
        "ranking",
        "best",
        "lowest",
        "least",
        "smallest",
        "bottom",
    ]

    hotel_dimension_signals = [
        "hotel type",
        "hotel",
        "market segment",
        "customer type",
        "deposit type",
        "room type",
        "reserved room type",
        "assigned room type",
        "country",
        "segment",
        "channel",
    ]

    # IMPORTANT:
    # Do NOT include plain "daily" here because "average daily rate" contains
    # the word daily, but it is a metric name (ADR), not a time intent.
    # This rule should only fire when the user explicitly asks for a trend/time view.
    temporal_signals = [
        "trend",
        "over time",
        "by month",
        "by year",
        "by week",
        "by day",
        "per month",
        "per year",
        "per week",
        "per day",
        "monthly trend",
        "weekly trend",
        "daily trend",
        "timeline",
        "time series",
    ]

    outlier_signals = [
        "outlier",
        "outliers",
        "anomaly",
        "anomalies",
        "unusual values",
        "extreme values",
    ]

    # 1) Outlier questions must win over scalar average aggregation.
    if average_daily_rate and _hotel_has_any_keyword(q_clean, outlier_signals):
        return _fire_hotel(
            "hotel_adr_outlier_override",
            force_plan(
                plan,
                "distribution",
                "visual_answer",
                "outlier_check",
                "box_plot",
                True,
                True,
                False,
                False,
                False,
            ),
        )

    # 2) Trend questions must win over groupby-mean/aggregation rules.
    if average_daily_rate and _hotel_has_any_keyword(q_clean, temporal_signals):
        return _fire_hotel(
            "hotel_adr_temporal_override",
            force_plan(
                plan,
                "trend_analysis",
                "visual_answer",
                "time_groupby_sum",
                "line_chart",
                True,
                True,
                False,
                True,
                False,
            ),
        )

    # 3) Ranking by a dimension should be groupby mean sort desc, not scalar mean.
    if (
        average_daily_rate
        and _hotel_has_any_keyword(q_clean, ranking_signals)
        and _hotel_has_any_keyword(q_clean, hotel_dimension_signals)
    ):
        return _fire_hotel(
            "hotel_adr_groupby_mean_ranking_override",
            force_plan(
                plan,
                "ranking",
                "small_summary",
                "groupby_mean_sort_desc",
                "horizontal_bar_chart",
                True,
                True,
                True,
                False,
                False,
            ),
        )

    return _LEGACY_APPLY_CHART_CORRECTIONS(question, plan)


# Mark the new deterministic hotel rules as strong so they do not get routed to
# fallback just because the raw ML confidence was low.
try:
    STRONG_RULE_NAMES.update(
        {
            "hotel_adr_outlier_override",
            "hotel_adr_temporal_override",
            "hotel_adr_groupby_mean_ranking_override",
        }
    )
except NameError:
    pass
