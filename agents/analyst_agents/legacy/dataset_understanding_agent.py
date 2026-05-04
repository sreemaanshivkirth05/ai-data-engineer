import json
import pandas as pd
from llm.openai_client import OpenAIClient


class DatasetUnderstandingAgent:
    """
    Runs ONCE after a dataset is uploaded, before any question is asked.
    Produces a rich semantic profile of the dataset so all downstream agents
    can make smarter decisions — especially when column names are domain-specific.

    Output is cached in session and passed to:
      - ColumnSelectorAgent (context for column selection)
      - PlannerAgent (context for target selection)
      - VisualizationAgent (context for chart relevance)
      - NarrativeAgent (context for business framing)
    """

    def __init__(self):
        self.llm = OpenAIClient()

    def run(self, df):
        """
        Returns a dataset_context dict with:
          - domain: what industry/domain this dataset appears to be from
          - description: one sentence describing what the dataset contains
          - primary_metric: the best single business KPI in this dataset
          - primary_metric_reasoning: why
          - time_columns: list of columns that represent time
          - segment_columns: list of columns useful for grouping/segmentation
          - metric_columns: list of numeric business metrics
          - column_semantics: {col_name: "what this column represents in business terms"}
          - warnings: any data quality notes
        """
        if df is None or len(df) == 0:
            return self._empty_context()

        # Build compact schema for LLM
        schema = self._build_compact_schema(df)
        prompt = self._build_prompt(schema)

        try:
            response = self.llm.generate(prompt)
            response = response.replace("```json", "").replace("```", "").strip()
            result = json.loads(response)
            result["schema"] = schema  # Attach raw schema for downstream use
            result["row_count"] = int(len(df))
            result["column_count"] = int(len(df.columns))
            print(f"✅ DatasetUnderstandingAgent: domain={result.get('domain')}, primary_metric={result.get('primary_metric')}")
            return result
        except Exception as e:
            print(f"⚠️ DatasetUnderstandingAgent failed ({e}), returning basic context")
            return self._basic_context(df, schema)

    def _build_compact_schema(self, df):
        """Build a compact but information-rich schema for the LLM."""
        schema = []
        total_rows = max(len(df), 1)

        for col in df.columns:
            series = df[col]
            dtype = str(series.dtype)
            non_null_pct = round(float(series.notna().mean() * 100), 1)
            unique_count = int(series.nunique(dropna=True))
            unique_ratio = round(float(unique_count / total_rows), 4)

            # Get representative sample values
            sample = []
            for v in series.dropna().head(5).tolist():
                try:
                    sample.append(str(v)[:40])
                except Exception:
                    pass

            entry = {
                "name": col,
                "dtype": dtype,
                "non_null_pct": non_null_pct,
                "unique_count": unique_count,
                "unique_ratio": unique_ratio,
                "sample_values": sample
            }

            # Add stats for numeric columns
            if pd.api.types.is_numeric_dtype(series) and not pd.api.types.is_bool_dtype(series):
                clean = pd.to_numeric(series, errors="coerce").dropna()
                if len(clean) > 0:
                    entry["min"] = round(float(clean.min()), 2)
                    entry["max"] = round(float(clean.max()), 2)
                    entry["mean"] = round(float(clean.mean()), 2)

            schema.append(entry)

        return schema

    def _build_prompt(self, schema):
        schema_json = json.dumps(schema, indent=2)

        return f"""You are a senior data analyst. You have been given a dataset schema.
Your job is to understand what this dataset is about and produce a semantic profile.

DATASET SCHEMA:
{schema_json}

Answer the following questions about this dataset by returning a JSON object:

1. What industry/domain does this dataset come from?
   Examples: "hotel bookings", "e-commerce sales", "healthcare admissions", "logistics",
   "finance", "retail", "manufacturing", "telecommunications", "insurance", "HR/payroll"
2. What does each row represent?
   Examples: "one transaction", "one patient visit", "one shipment", "one employee record",
   "one product sale", "one customer interaction"
3. What is the single best business metric to measure performance? (the most meaningful numeric KPI)
4. Why is that column the best metric?
5. For each column, what does it mean in plain business language?
6. Which columns represent time dimensions?
7. Which columns are best for segmentation/grouping?
8. Which columns are numeric business metrics (not IDs, not counts of things that aren't useful)?
9. Are there any data quality warnings?

IMPORTANT RULES:
- Column names may NOT match standard business terms. Use sample_values, dtype, and context clues to understand what each column represents.
- Use sample_values, dtype, and value ranges to understand each column's meaning
- Integer columns with values 0/1 are usually boolean flags (cancellation, churn, default)
- Float columns with values 0–1 are usually rates or proportions
- Integer columns with values 1900–2100 are year dimensions, NOT metrics
- Integer columns with values 1–12 are month dimensions
- Columns with a small number of unique string values are categorical dimensions
- High-cardinality integer columns could be IDs, quantities, or numeric metrics
- Example domain mappings: "adr" in hotel data = revenue proxy; "churn" in telecom = cancellation flag;
  "los" in healthcare = length of stay; "ltv" in finance = lifetime value
- Think carefully about what the data is trying to measure before selecting the primary metric

Return ONLY valid JSON in this exact structure:
{{
  "domain": "brief domain name",
  "row_description": "one sentence describing what each row represents",
  "description": "one sentence describing the entire dataset",
  "primary_metric": "exact column name",
  "primary_metric_reasoning": "why this is the best KPI",
  "time_columns": ["col_name"],
  "segment_columns": ["col_name"],
  "metric_columns": ["col_name"],
  "column_semantics": {{
    "col_name": "plain English description of what this column means in business context"
  }},
  "useful_question_starters": [
    "What is the total ...",
    "Which ... drives the highest ...",
    "How has ... changed over time?"
  ],
  "warnings": ["any data quality notes"]
}}""".strip()

    def _basic_context(self, df, schema):
        """Fallback when LLM fails — use heuristics."""
        numeric_cols = df.select_dtypes(include=["number"]).columns.tolist()
        categorical_cols = df.select_dtypes(include=["object"]).columns.tolist()
        datetime_cols = df.select_dtypes(include=["datetime64[ns]", "datetime64[ns, UTC]"]).columns.tolist()

        # Pick a primary metric heuristically
        metric_keywords = ["revenue", "sales", "profit", "amount", "price", "cost", "total", "value", "quantity", "margin", "rate", "score"]
        primary = None
        for col in numeric_cols:
            if any(k in col.lower() for k in metric_keywords):
                primary = col
                break
        if not primary and numeric_cols:
            primary = numeric_cols[0]

        return {
            "domain": "unknown",
            "row_description": f"Each row is one record in a {len(df):,}-row dataset",
            "description": f"A dataset with {len(df.columns)} columns and {len(df):,} rows",
            "primary_metric": primary,
            "primary_metric_reasoning": "Selected by keyword heuristic",
            "time_columns": datetime_cols,
            "segment_columns": categorical_cols[:5],
            "metric_columns": numeric_cols[:8],
            "column_semantics": {},
            "useful_question_starters": [],
            "warnings": [],
            "schema": schema,
            "row_count": int(len(df)),
            "column_count": int(len(df.columns))
        }

    def _empty_context(self):
        return {
            "domain": "unknown",
            "row_description": "",
            "description": "",
            "primary_metric": None,
            "primary_metric_reasoning": "",
            "time_columns": [],
            "segment_columns": [],
            "metric_columns": [],
            "column_semantics": {},
            "useful_question_starters": [],
            "warnings": [],
            "schema": [],
            "row_count": 0,
            "column_count": 0
        }