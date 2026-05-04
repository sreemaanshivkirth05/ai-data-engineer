import json
from llm.openai_client import OpenAIClient


class ColumnSelectorAgent:
    """
    Uses an LLM to select which columns are relevant to answer a given question.
    Runs BEFORE PlannerAgent so the planner only sees relevant columns.

    Now accepts dataset_context from DatasetUnderstandingAgent — this gives the
    LLM pre-computed knowledge about what the dataset is about (domain, primary
    metric, column semantics) so it can make smarter selections without having
    to figure everything out from scratch on every question.

    Key benefit: handles domain-specific column names that don't match standard
    business keywords. Column names vary widely by domain — a revenue column might
    be named 'adr', 'ltv', 'net_sales', 'unit_price', or 'revenue_usd'. The LLM
    uses dtype, sample_values, and dataset context to infer the right mapping.
    """

    def __init__(self):
        self.llm = OpenAIClient()

    def run(self, question, column_profiles, dataset_context=None):
        """
        Returns a filtered list of column_profiles relevant to the question.
        Falls back to all profiles if LLM fails or returns unusable output.
        """
        if not column_profiles or not question:
            return column_profiles

        dataset_context = dataset_context or {}

        # Build compact schema — exclude ID columns upfront
        id_profiles = [c for c in column_profiles if c.get("is_probable_id", False)]
        compact_schema = [
            {
                "name": c["name"],
                "dtype": c.get("dtype", "unknown"),
                "semantic_type": c.get("semantic_type", "unknown"),
                "sample_values": c.get("sample_values", [])[:3],
                "is_probable_metric": c.get("is_probable_metric", False)
            }
            for c in column_profiles
            if not c.get("is_probable_id", False)
        ]

        if not compact_schema:
            return column_profiles

        prompt = self._build_prompt(question, compact_schema, dataset_context)

        try:
            response = self.llm.generate(prompt)
            response = response.replace("```json", "").replace("```", "").strip()
            result = json.loads(response)

            selected_names = result.get("selected_columns", [])
            target_hint = result.get("target_hint")
            semantic_mappings = result.get("semantic_mappings", {})

            if not selected_names or not isinstance(selected_names, list):
                return column_profiles

            selected_set = set(selected_names)

            filtered = []
            for c in column_profiles:
                if c["name"] in selected_set:
                    enriched = dict(c)
                    if c["name"] in semantic_mappings:
                        enriched["llm_semantic_hint"] = semantic_mappings[c["name"]]
                    filtered.append(enriched)

            # Mark the target hint
            if filtered and target_hint:
                for c in filtered:
                    if c["name"] == target_hint:
                        c["llm_target_hint"] = True
                        break

            # Safety: if LLM returned too few columns, fall back
            if len(filtered) < 2:
                print(f"⚠️ ColumnSelectorAgent returned too few columns ({len(filtered)}), using all profiles")
                return column_profiles

            print(f"🎯 ColumnSelectorAgent selected {len(filtered)} of {len(column_profiles)} columns")
            if target_hint:
                print(f"   LLM target hint: {target_hint}")

            return filtered

        except Exception as e:
            print(f"⚠️ ColumnSelectorAgent failed ({e}), using all column profiles")
            return column_profiles

    def _build_prompt(self, question, compact_schema, dataset_context):
        schema_json = json.dumps(compact_schema, indent=2)

        # Build dataset context block if available
        context_block = ""
        if dataset_context:
            domain = dataset_context.get("domain", "")
            description = dataset_context.get("description", "")
            primary_metric = dataset_context.get("primary_metric", "")
            primary_metric_reasoning = dataset_context.get("primary_metric_reasoning", "")
            column_semantics = dataset_context.get("column_semantics", {})

            if domain or description or primary_metric:
                context_block = f"""
DATASET CONTEXT (pre-computed by dataset understanding agent):
- Domain: {domain}
- Dataset description: {description}
- Suggested primary metric: {primary_metric}
- Why: {primary_metric_reasoning}
"""
                if column_semantics:
                    semantics_sample = dict(list(column_semantics.items())[:15])
                    context_block += f"- Column meanings: {json.dumps(semantics_sample, indent=2)}\n"

        return f"""You are a senior data analyst helping select the right columns to answer a business question.

QUESTION: "{question}"
{context_block}
AVAILABLE COLUMNS:
{schema_json}

Your job:
1. Select ONLY the columns needed to answer this question well.
2. Identify the single best TARGET column (the metric being measured or counted).
3. Map any business terms in the question to actual column names.

SELECTION RULES:
- Include: the target metric, grouping dimensions relevant to the question, and time columns if the question is about trends
- Include: columns that help explain or segment the target (up to 10 total)
- Exclude: ID columns, unrelated metrics, free-text fields, columns with no bearing on the question
- Use the DATASET CONTEXT above if available — it tells you what each column means in business terms
- If the dataset context provides a primary_metric suggestion, prefer it over generic fallbacks
- If the question uses a business term (revenue, profit, churn, volume) and no exact column exists,
  use the semantic_hint from the dataset context to find the closest proxy column
- If no exact match exists, use sample_values and dtype to infer what each column represents
- Always include at least 3-5 categorical columns for grouping/segmentation even if the question doesn't explicitly ask for them

IMPORTANT — column names often don't match standard business terms. Use dtype and
sample_values to infer meaning. Generic patterns:
- Float columns with values in a bounded range (e.g. 50–300) are likely rate/price metrics
- Integer columns with 0/1 values are boolean flags (cancellation, churn, approval)
- Integer columns with values 1900–2100 are year dimensions, NOT metrics
- Integer columns with values 1–12 are month dimensions
- Integer columns with values 0–31 are day dimensions
- High-cardinality string columns are segmentation dimensions
- Low-cardinality string columns (2–10 unique values) are categorical grouping dimensions
- Columns ending in "_id", "_key", "_uuid" are identifiers — exclude from analysis

Return JSON in this exact structure:
{{
  "selected_columns": ["exact column name", ...],
  "target_hint": "exact column name of the best target metric, or null",
  "semantic_mappings": {{
    "column_name": "what business concept this column represents"
  }},
  "reasoning": "one sentence explaining the selection"
}}

Return ONLY valid JSON. No markdown, no prose outside the JSON.""".strip()