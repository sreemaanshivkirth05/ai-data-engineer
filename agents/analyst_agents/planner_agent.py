import json
import re
from difflib import SequenceMatcher
from llm.openai_client import OpenAIClient


class PlannerAgent:
    def __init__(self):
        self.llm = OpenAIClient()

    def run(self, question, columns):
        """
        Accepts either:
        1. columns = ["Sales", "Profit", "Order Date", ...]
        or
        2. columns = [
            {
                "name": "Sales",
                "dtype": "float64",
                "semantic_type": "metric",
                "non_null_pct": 1.0,
                "unique_count": 500,
                "unique_ratio": 0.45,
                "sample_values": [100.5, 220.0, 99.9],
                "is_probable_id": False,
                "is_probable_metric": True,
                "is_probable_datetime": False
            },
            ...
        ]
        """

        question = (question or "").strip()
        question_lower = question.lower()

        column_profiles = self._prepare_column_profiles(columns)
        if not column_profiles:
            return {
                "target": None,
                "drivers": [],
                "time_column": None,
                "analysis_type": "comparison",
                "aggregation": "none",
                "chart": "table",
                "reasoning": {
                    "target_why": "No columns were provided.",
                    "drivers_why": [],
                    "warnings": ["No dataset columns available."]
                }
            }

        prompt = self._build_planner_prompt(question, column_profiles)

        raw_plan = {}
        try:
            response = self.llm.generate(prompt)
            response = response.replace("```json", "").replace("```", "").strip()
            raw_plan = json.loads(response)
        except Exception as e:
            print("PlannerAgent LLM error:", e)
            raw_plan = {}

        plan = self._validate_plan(raw_plan, column_profiles, question_lower)

        # Strong deterministic fallback for target
        explicit_target = self._explicit_metric_target(column_profiles, question_lower)
        if explicit_target:
            plan["target"] = explicit_target

        if not plan["target"]:
            plan["target"] = self._fallback_target(column_profiles, question_lower)

        # Strong deterministic fallback for drivers
        if not plan["drivers"]:
            plan["drivers"] = self._fallback_drivers(column_profiles, plan["target"], question_lower)

        # Repair time column if missing and question suggests time/trend
        if not plan["time_column"] and self._question_is_trend_like(question_lower):
            dt_cols = [c["name"] for c in column_profiles if c.get("semantic_type") == "datetime"]
            if dt_cols:
                plan["time_column"] = dt_cols[0]
                if plan["chart"] == "bar":
                    plan["chart"] = "line"
                if plan["analysis_type"] == "comparison":
                    plan["analysis_type"] = "trend"
                if plan["aggregation"] == "none":
                    plan["aggregation"] = "sum"

        # Final cleanup
        plan["drivers"] = self._dedupe_keep_order(
            [d for d in plan["drivers"] if d and d != plan["target"]]
        )[:5]

        if plan["target"] and plan["target"] in plan["drivers"]:
            plan["drivers"] = [d for d in plan["drivers"] if d != plan["target"]]

        return plan

    # ---------------------------
    # Profile preparation
    # ---------------------------

    def _prepare_column_profiles(self, columns):
        """
        Converts either list[str] or list[dict] into a uniform profile format.
        """
        if not columns:
            return []

        profiles = []

        for item in columns:
            if isinstance(item, dict):
                name = str(item.get("name", "")).strip()
                if not name:
                    continue

                profile = {
                    "name": name,
                    "dtype": item.get("dtype", "unknown"),
                    "semantic_type": item.get("semantic_type") or self._infer_semantic_type_from_name(name),
                    "non_null_pct": self._safe_float(item.get("non_null_pct"), 1.0),
                    "unique_count": self._safe_int(item.get("unique_count"), 0),
                    "unique_ratio": self._safe_float(item.get("unique_ratio"), 0.0),
                    "sample_values": item.get("sample_values", []),
                    "is_probable_id": bool(item.get("is_probable_id", self._looks_like_id(name))),
                    "is_probable_metric": bool(item.get("is_probable_metric", self._looks_like_metric(name))),
                    "is_probable_datetime": bool(item.get("is_probable_datetime", self._looks_like_datetime(name))),
                }
                profiles.append(profile)
            else:
                name = str(item).strip()
                if not name:
                    continue

                semantic_type = self._infer_semantic_type_from_name(name)

                profiles.append({
                    "name": name,
                    "dtype": "unknown",
                    "semantic_type": semantic_type,
                    "non_null_pct": 1.0,
                    "unique_count": 0,
                    "unique_ratio": 0.0,
                    "sample_values": [],
                    "is_probable_id": self._looks_like_id(name),
                    "is_probable_metric": self._looks_like_metric(name),
                    "is_probable_datetime": self._looks_like_datetime(name),
                })

        return profiles

    def _infer_semantic_type_from_name(self, name):
        norm = self._normalize_name(name)

        if self._looks_like_id(name):
            return "id"
        if self._looks_like_datetime(name):
            return "datetime"
        if self._looks_like_metric(name):
            return "metric"
        if self._looks_like_text(name):
            return "text"
        if self._looks_like_boolean(name):
            return "boolean"

        categorical_keywords = [
            "region", "country", "state", "city", "category", "segment",
            "product", "sub category", "channel", "customer", "ship mode",
            "department", "type", "group", "class", "market", "brand", "status"
        ]
        if any(k in norm for k in categorical_keywords):
            return "categorical"

        return "unknown"

    # ---------------------------
    # Prompt
    # ---------------------------

    def _build_planner_prompt(self, question, column_profiles):
        schema_json = json.dumps(column_profiles, indent=2)

        return f"""
You are a senior analytics planning agent for a production AI Data Analysis system.

Your job is to convert a business question into a VALID analysis plan using ONLY the provided dataset schema.

USER QUESTION:
{question}

DATASET SCHEMA:
{schema_json}

STRICT RULES:
1. Use ONLY exact column names from the provided schema.
2. Never invent columns, aliases, or derived fields that are not listed.
3. Choose ONE best target column, unless the question is impossible to answer from this schema.
4. Choose up to 5 driver columns that help explain, segment, group, or trend the target.
5. Do NOT include the target inside drivers.
6. Prefer business metrics as targets:
   - numeric continuous metrics such as sales, revenue, profit, cost, quantity, amount, price, margin
   - count-based targets only when no stronger metric exists or the question asks for counts
7. Prefer temporal columns for trend questions.
8. Prefer low-to-medium cardinality categorical columns for grouping/comparison.
9. Avoid IDs, UUIDs, row numbers, postal codes, zip codes, free-text notes, and nearly unique columns as drivers unless the user explicitly asks for them.
10. If the user asks about a metric that does not exist, choose the closest valid metric only if strongly supported by the schema; otherwise set target to null and explain why in warnings.
11. Respect data types:
   - line chart requires a temporal or ordered x-axis
   - scatter requires 2 numeric variables
   - histogram/box plot require numeric target
   - bar chart is preferred for categorical comparisons
12. If a date/time column exists and the question implies trend, include it as time_column.
13. If multiple date columns exist, choose the most semantically relevant one.
14. Prefer columns with lower missingness and meaningful business semantics.
15. Return valid JSON only. No markdown, no comments, no prose outside JSON.

SENIOR ANALYST DECISION RULES:
- For "trend over time" questions: choose a numeric target + a temporal column + aggregation usually sum/avg/count.
- For "top/bottom" questions: choose ranking/comparison with bar chart.
- For "distribution" questions: numeric target with histogram or box plot.
- For "relationship/correlation" questions: two numeric fields with scatter, or one numeric target and several candidate numeric drivers.
- For "breakdown by segment/region/category/channel" questions: use categorical grouping columns with bar or stacked bar.
- If a categorical column is extremely high cardinality or nearly unique, do not use it as a default driver.
- If the target appears to be an identifier, reject it unless the question explicitly asks for counts by ID.
- If the target has heavy nulls, mention that in warnings.
- If no good metric exists, prefer count-based analysis over a bad metric.

Return JSON in this exact structure:
{{
  "target": "exact column name or null",
  "drivers": ["exact column name"],
  "time_column": "exact column name or null",
  "analysis_type": "trend | comparison | distribution | ranking | relationship | composition | diagnostic",
  "aggregation": "sum | avg | median | count | count_distinct | none",
  "chart": "line | bar | scatter | histogram | box | area | heatmap | table",
  "reasoning": {{
    "target_why": "short reason",
    "drivers_why": ["short reason"],
    "warnings": ["warning"]
  }}
}}
""".strip()

    # ---------------------------
    # Validation
    # ---------------------------

    def _validate_plan(self, plan, column_profiles, question_lower):
        target = self._match_column(
            plan.get("target"),
            column_profiles,
            expected_types={"metric", "categorical", "datetime", "unknown"}
        )

        raw_drivers = plan.get("drivers", []) or []
        drivers = []
        for driver in raw_drivers:
            matched = self._match_column(
                driver,
                column_profiles,
                expected_types={"categorical", "datetime", "metric", "unknown"}
            )
            if matched and matched != target and matched not in drivers:
                profile = self._get_profile(matched, column_profiles)
                if profile and not profile.get("is_probable_id", False):
                    drivers.append(matched)

        time_column = self._match_column(
            plan.get("time_column"),
            column_profiles,
            expected_types={"datetime"}
        )

        analysis_type = plan.get("analysis_type", "comparison")
        if analysis_type not in {
            "trend", "comparison", "distribution",
            "ranking", "relationship", "composition", "diagnostic"
        }:
            analysis_type = "comparison"

        aggregation = plan.get("aggregation", "none")
        if aggregation not in {"sum", "avg", "median", "count", "count_distinct", "none"}:
            aggregation = "none"

        chart = plan.get("chart", "table")
        if chart not in {"line", "bar", "scatter", "histogram", "box", "area", "heatmap", "table"}:
            chart = "table"

        reasoning = plan.get("reasoning", {})
        if not isinstance(reasoning, dict):
            reasoning = {}

        validated = {
            "target": target,
            "drivers": drivers[:5],
            "time_column": time_column,
            "analysis_type": analysis_type,
            "aggregation": aggregation,
            "chart": chart,
            "reasoning": {
                "target_why": str(reasoning.get("target_why", "")).strip(),
                "drivers_why": reasoning.get("drivers_why", []) if isinstance(reasoning.get("drivers_why", []), list) else [],
                "warnings": reasoning.get("warnings", []) if isinstance(reasoning.get("warnings", []), list) else [],
            }
        }

        # Deterministic repairs
        if validated["target"]:
            target_profile = self._get_profile(validated["target"], column_profiles)
            if target_profile and target_profile.get("is_probable_id", False):
                validated["reasoning"]["warnings"].append("Target looked like an ID column and was rejected.")
                validated["target"] = None

        if validated["analysis_type"] == "trend" and not validated["time_column"]:
            dt_cols = [c["name"] for c in column_profiles if c.get("semantic_type") == "datetime"]
            if dt_cols:
                validated["time_column"] = dt_cols[0]
            else:
                validated["chart"] = "bar"

        if validated["chart"] == "line" and not validated["time_column"]:
            validated["chart"] = "bar"

        if validated["chart"] in {"histogram", "box"} and validated["target"]:
            target_profile = self._get_profile(validated["target"], column_profiles)
            if target_profile and target_profile.get("semantic_type") not in {"metric", "unknown"}:
                validated["chart"] = "bar"

        if validated["chart"] == "scatter":
            numeric_candidates = [
                c["name"] for c in column_profiles
                if c.get("semantic_type") in {"metric", "unknown"} and not c.get("is_probable_id", False)
            ]
            if len(numeric_candidates) < 2:
                validated["chart"] = "bar"

        if not validated["target"] and self._question_is_count_like(question_lower):
            validated["aggregation"] = "count"
            if validated["analysis_type"] == "comparison":
                validated["chart"] = "bar"

        return validated

    # ---------------------------
    # Matching
    # ---------------------------

    def _match_column(self, candidate, column_profiles, min_score=0.84, expected_types=None):
        if not candidate:
            return None

        candidate_norm = self._normalize_name(candidate)
        scored = []

        for col in column_profiles:
            col_name = col["name"]
            col_norm = self._normalize_name(col_name)
            score = SequenceMatcher(None, candidate_norm, col_norm).ratio()

            if candidate_norm == col_norm:
                score += 0.20
            if candidate_norm.replace(" ", "") == col_norm.replace(" ", ""):
                score += 0.15
            if candidate_norm in col_norm or col_norm in candidate_norm:
                score += 0.05
            if expected_types and col.get("semantic_type") in expected_types:
                score += 0.04

            scored.append((col_name, score))

        scored.sort(key=lambda x: x[1], reverse=True)

        if scored and scored[0][1] >= min_score:
            best = scored[0][0]
            if self._type_ok(best, column_profiles, expected_types):
                return best

        return None

    def _type_ok(self, column_name, column_profiles, expected_types=None):
        if not expected_types:
            return True

        profile = self._get_profile(column_name, column_profiles)
        if not profile:
            return False

        return profile.get("semantic_type") in expected_types

    def _get_profile(self, column_name, column_profiles):
        for col in column_profiles:
            if col["name"] == column_name:
                return col
        return None

    # ---------------------------
    # Explicit target logic
    # ---------------------------

    def _explicit_metric_target(self, column_profiles, question_lower):
        metric_aliases = {
            "profit": ["profit", "profits", "margin"],
            "sales": ["sales", "sale"],
            "revenue": ["revenue", "revenues"],
            "cost": ["cost", "costs", "expense", "expenses"],
            "quantity": ["quantity", "qty", "units", "unit", "volume"],
            "discount": ["discount", "discounts"],
            "price": ["price", "prices"],
            "amount": ["amount", "amounts", "value", "values"],
            "count": ["count", "counts", "number of", "how many"]
        }

        best = None
        best_score = -999

        for canonical_metric, aliases in metric_aliases.items():
            if not any(alias in question_lower for alias in aliases):
                continue

            for col in column_profiles:
                name = col["name"]
                norm = self._normalize_name(name)
                score = 0

                if col.get("is_probable_id", False):
                    score -= 10

                if col.get("semantic_type") == "metric":
                    score += 5

                if canonical_metric in norm:
                    score += 4

                if any(alias in norm for alias in aliases):
                    score += 2

                if score > best_score:
                    best = name
                    best_score = score

        return best if best_score > 0 else None

    # ---------------------------
    # Fallback target logic
    # ---------------------------

    def _fallback_target(self, column_profiles, question_lower):
        ranked = self._score_target_candidates(column_profiles, question_lower)
        return ranked[0][0] if ranked else None

    def _score_target_candidates(self, column_profiles, question_lower):
        metric_keywords = {
            "revenue", "sales", "profit", "cost", "amount", "price",
            "quantity", "margin", "income", "value", "discount", "count"
        }

        scored = []

        for col in column_profiles:
            name = col["name"]
            norm = self._normalize_name(name)
            semantic_type = col.get("semantic_type", "unknown")
            non_null_pct = col.get("non_null_pct", 1.0)
            unique_ratio = col.get("unique_ratio", 0.0)

            score = 0.0

            if semantic_type == "metric":
                score += 5.0
            elif semantic_type == "categorical":
                score += 1.0
            elif semantic_type == "datetime":
                score -= 2.0
            elif semantic_type == "id":
                score -= 10.0
            elif semantic_type == "text":
                score -= 4.0

            if col.get("is_probable_id", False):
                score -= 10.0

            for kw in metric_keywords:
                if kw in norm:
                    score += 2.5
                if kw in question_lower and kw in norm:
                    score += 3.0

            if self._question_is_count_like(question_lower) and semantic_type not in {"id", "text"}:
                score += 1.0

            score += non_null_pct * 1.5

            if unique_ratio > 0.98 and semantic_type not in {"metric"}:
                score -= 3.0

            scored.append((name, score))

        scored.sort(key=lambda x: x[1], reverse=True)
        return scored

    # ---------------------------
    # Fallback driver logic
    # ---------------------------

    def _fallback_drivers(self, column_profiles, target, question_lower, max_drivers=5):
        preferred_group_keywords = [
            "date", "time", "year", "month", "quarter",
            "region", "country", "state", "city",
            "category", "segment", "product", "sub category",
            "channel", "department", "type", "group", "market", "brand", "status"
        ]

        scored = []

        for col in column_profiles:
            name = col["name"]
            if name == target:
                continue

            norm = self._normalize_name(name)
            semantic_type = col.get("semantic_type", "unknown")
            unique_ratio = col.get("unique_ratio", 0.0)
            non_null_pct = col.get("non_null_pct", 1.0)
            is_probable_id = col.get("is_probable_id", False)

            score = 0.0

            if semantic_type == "categorical":
                score += 3.5
            elif semantic_type == "datetime":
                score += 3.0
            elif semantic_type == "metric":
                score += 1.0
            elif semantic_type == "text":
                score -= 3.0

            for kw in preferred_group_keywords:
                if kw in norm:
                    score += 2.0
                if kw in question_lower and kw in norm:
                    score += 2.0

            if is_probable_id:
                score -= 8.0

            if unique_ratio > 0.95 and semantic_type == "categorical":
                score -= 4.0

            if non_null_pct < 0.50:
                score -= 1.5

            scored.append((name, score))

        scored.sort(key=lambda x: x[1], reverse=True)

        ranked = [name for name, score in scored if score > 0]
        if ranked:
            return ranked[:max_drivers]

        return [c["name"] for c in column_profiles if c["name"] != target][:max_drivers]

    # ---------------------------
    # Utilities
    # ---------------------------

    def _normalize_name(self, text):
        text = str(text or "").strip().lower()
        text = re.sub(r"[_\-/]+", " ", text)
        text = re.sub(r"\s+", " ", text)
        return text

    def _looks_like_id(self, name):
        norm = self._normalize_name(name)
        id_keywords = [
            "id", "uuid", "key", "row number", "rownum",
            "transaction id", "order id", "customer id", "product id",
            "postal", "zip", "zipcode"
        ]
        return any(k in norm for k in id_keywords)

    def _looks_like_metric(self, name):
        norm = self._normalize_name(name)
        metric_keywords = [
            "sales", "revenue", "profit", "amount", "price", "cost",
            "income", "margin", "quantity", "qty", "units", "discount",
            "value", "score", "rate", "count", "total"
        ]
        return any(k in norm for k in metric_keywords)

    def _looks_like_datetime(self, name):
        norm = self._normalize_name(name)
        dt_keywords = [
            "date", "time", "timestamp", "year",
            "month", "quarter", "week", "day"
        ]
        return any(k in norm for k in dt_keywords)

    def _looks_like_text(self, name):
        norm = self._normalize_name(name)
        text_keywords = [
            "comment", "comments", "note", "notes", "description",
            "message", "text", "address", "summary", "remark", "remarks"
        ]
        return any(k in norm for k in text_keywords)

    def _looks_like_boolean(self, name):
        norm = self._normalize_name(name)
        bool_keywords = ["is ", "has ", "flag", "active", "enabled", "deleted"]
        return any(k in norm for k in bool_keywords)

    def _question_is_trend_like(self, question_lower):
        trend_words = [
            "trend", "over time", "by month", "by year", "by quarter",
            "timeline", "growth", "decline", "change over time", "time series"
        ]
        return any(word in question_lower for word in trend_words)

    def _question_is_count_like(self, question_lower):
        count_words = [
            "count", "counts", "how many", "number of", "total number"
        ]
        return any(word in question_lower for word in count_words)

    def _dedupe_keep_order(self, items):
        seen = set()
        result = []
        for item in items:
            if item and item not in seen:
                result.append(item)
                seen.add(item)
        return result

    def _safe_float(self, value, default=0.0):
        try:
            return float(value)
        except Exception:
            return default

    def _safe_int(self, value, default=0):
        try:
            return int(value)
        except Exception:
            return default