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

        # ---------------------------
        # NEW: explicit metric/group disentangling
        # ---------------------------
        metric_candidate, grouping_candidate, metric_group_warnings = self._resolve_metric_and_grouping(
            question_lower=question_lower,
            column_profiles=column_profiles
        )
        plan["reasoning"]["warnings"].extend(metric_group_warnings)

        # Explicit metric from question wins over weak LLM target
        if metric_candidate:
            current_target_profile = self._get_profile(plan.get("target"), column_profiles) if plan.get("target") else None
            if (
                not plan.get("target")
                or (current_target_profile and current_target_profile.get("semantic_type") in {"categorical", "text", "id", "boolean"})
            ):
                plan["target"] = metric_candidate
                plan["reasoning"]["target_why"] = (
                    f"Selected {metric_candidate} because it best matches the measurable business metric named in the question."
                )

        # If LLM accidentally chose grouping column as target while we have a metric, repair it
        if grouping_candidate and metric_candidate:
            if plan.get("target") == grouping_candidate:
                plan["target"] = metric_candidate
                if grouping_candidate not in plan["drivers"]:
                    plan["drivers"] = [grouping_candidate] + plan["drivers"]
                plan["reasoning"]["warnings"].append(
                    f"Grouping column {grouping_candidate} was moved from target to drivers because the question asks to measure {metric_candidate} by group."
                )

        explicit_target = self._explicit_metric_target(column_profiles, question_lower)
        if explicit_target:
            plan["target"] = explicit_target
            if not plan["reasoning"]["target_why"]:
                plan["reasoning"]["target_why"] = (
                    f"Selected {explicit_target} because it strongly matches the business metric named in the question."
                )

        if not plan["target"]:
            fallback_target, fallback_reason = self._fallback_target(column_profiles, question_lower)
            plan["target"] = fallback_target
            if fallback_reason:
                plan["reasoning"]["warnings"].append(fallback_reason)

        # If fallback still lands on grouping while we know the intended grouping separately, fix it
        if grouping_candidate and metric_candidate and plan.get("target") == grouping_candidate:
            plan["target"] = metric_candidate
            if grouping_candidate not in plan["drivers"]:
                plan["drivers"] = [grouping_candidate] + plan["drivers"]
            plan["reasoning"]["warnings"].append(
                f"Fallback target was corrected from grouping column {grouping_candidate} to metric {metric_candidate}."
            )

        if not plan["drivers"]:
            plan["drivers"] = self._fallback_drivers(
                column_profiles,
                plan["target"],
                question_lower,
                analysis_type=plan.get("analysis_type")
            )

        # Ensure detected grouping stays in drivers when relevant
        if grouping_candidate and grouping_candidate != plan.get("target") and grouping_candidate not in plan["drivers"]:
            plan["drivers"] = [grouping_candidate] + plan["drivers"]

        if plan.get("target") in plan["drivers"]:
            plan["drivers"] = [d for d in plan["drivers"] if d != plan["target"]]

        if plan["time_column"] and plan["time_column"] not in [c["name"] for c in column_profiles]:
            plan["time_column"] = None

        if not plan["time_column"] and self._question_is_trend_like(question_lower):
            best_time = self._best_time_column(column_profiles)
            if best_time:
                plan["time_column"] = best_time
                if plan["chart"] == "bar":
                    plan["chart"] = "line"
                if plan["analysis_type"] == "comparison":
                    plan["analysis_type"] = "trend"
                if plan["aggregation"] == "none":
                    plan["aggregation"] = "sum"
                plan["reasoning"]["warnings"].append(
                    f"Time column was repaired automatically to {best_time} for trend-style analysis."
                )

        plan = self._repair_plan_for_analysis_type(plan, column_profiles, question_lower)

        plan["drivers"] = self._dedupe_keep_order(
            [d for d in plan["drivers"] if d and d != plan["target"]]
        )[:5]

        if plan["target"] and plan["target"] in plan["drivers"]:
            plan["drivers"] = [d for d in plan["drivers"] if d != plan["target"]]

        plan["reasoning"]["warnings"] = self._dedupe_keep_order(
            [w for w in plan["reasoning"].get("warnings", []) if str(w).strip()]
        )[:6]

        return plan

    # ---------------------------
    # Profile preparation
    # ---------------------------

    def _prepare_column_profiles(self, columns):
        if not columns:
            return []

        profiles = []

        for item in columns:
            if isinstance(item, dict):
                name = str(item.get("name", "")).strip()
                if not name:
                    continue

                dtype = str(item.get("dtype", "unknown"))
                non_null_pct = self._safe_float(item.get("non_null_pct"), 1.0)
                unique_count = self._safe_int(item.get("unique_count"), 0)
                unique_ratio = self._safe_float(item.get("unique_ratio"), 0.0)
                sample_values = item.get("sample_values", [])

                semantic_type = item.get("semantic_type")
                if not semantic_type:
                    semantic_type = self._infer_semantic_type_from_profile_dict(
                        name=name,
                        dtype=dtype,
                        unique_ratio=unique_ratio,
                        sample_values=sample_values
                    )

                profile = {
                    "name": name,
                    "dtype": dtype,
                    "semantic_type": semantic_type,
                    "non_null_pct": non_null_pct,
                    "unique_count": unique_count,
                    "unique_ratio": unique_ratio,
                    "sample_values": sample_values,
                    "is_probable_id": bool(
                        item.get("is_probable_id", self._looks_like_id(name) or unique_ratio >= 0.98)
                    ),
                    "is_probable_metric": bool(
                        item.get("is_probable_metric", self._looks_like_metric(name) or self._dtype_is_numeric(dtype))
                    ),
                    "is_probable_datetime": bool(
                        item.get("is_probable_datetime", self._looks_like_datetime(name) or self._dtype_is_datetime(dtype))
                    ),
                }

                profile["semantic_type"] = self._refine_semantic_type(profile)
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

    def _infer_semantic_type_from_profile_dict(self, name, dtype, unique_ratio, sample_values):
        if self._looks_like_id(name) or unique_ratio >= 0.99:
            return "id"
        if self._dtype_is_datetime(dtype) or self._looks_like_datetime(name):
            return "datetime"
        if self._dtype_is_bool(dtype) or self._looks_like_boolean(name):
            return "boolean"
        if self._dtype_is_numeric(dtype):
            return "metric"
        if self._looks_like_text(name):
            return "text"
        if unique_ratio >= 0.95:
            return "text"
        if self._looks_like_category(name):
            return "categorical"
        return "categorical"

    def _refine_semantic_type(self, profile):
        name = profile["name"]
        dtype = str(profile.get("dtype", "unknown"))
        unique_ratio = self._safe_float(profile.get("unique_ratio"), 0.0)

        if profile.get("is_probable_id", False):
            return "id"
        if self._dtype_is_datetime(dtype) or profile.get("is_probable_datetime", False):
            return "datetime"
        if self._dtype_is_bool(dtype) or self._looks_like_boolean(name):
            return "boolean"
        if self._dtype_is_numeric(dtype):
            return "metric"
        if self._looks_like_text(name):
            return "text"
        if unique_ratio >= 0.95:
            return "text"
        if self._looks_like_category(name):
            return "categorical"
        return profile.get("semantic_type", "unknown") or "unknown"

    def _infer_semantic_type_from_name(self, name):
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
        if self._looks_like_category(name):
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
3. Choose ONE best numeric or aggregatable target column, unless the question is impossible to answer from this schema.
4. Separately identify grouping dimensions inside drivers. Do not confuse the grouping entity with the measured target.
5. Choose up to 5 driver columns that help explain, segment, group, or trend the target.
6. Do NOT include the target inside drivers.
7. Prefer business metrics as targets:
   - numeric continuous metrics such as sales, revenue, profit, cost, quantity, amount, price, margin
   - count-based targets only when no stronger metric exists or the question asks for counts
8. Prefer temporal columns for trend questions.
9. Prefer low-to-medium cardinality categorical columns for grouping/comparison.
10. Avoid IDs, UUIDs, row numbers, postal codes, zip codes, free-text notes, and nearly unique columns as drivers unless the user explicitly asks for them.
11. If the user asks about a metric that does not exist, choose the closest valid metric only if strongly supported by the schema; otherwise set target to null and explain why in warnings.
12. Respect data types:
   - line chart requires a temporal or ordered x-axis
   - scatter requires 2 numeric variables
   - histogram/box plot require numeric target
   - bar chart is preferred for categorical comparisons
13. If a date/time column exists and the question implies trend, include it as time_column.
14. If multiple date columns exist, choose the most semantically relevant one.
15. Prefer columns with lower missingness and meaningful business semantics.
16. Return valid JSON only. No markdown, no comments, no prose outside JSON.

SENIOR ANALYST DECISION RULES:
- For questions like "Which countries are ordering the highest quantities?" the target should be the measurable metric (Quantity) and the grouping dimension (Country) should go into drivers.
- For questions like "Which products contribute the most revenue?" the target should be a revenue-like metric if present; otherwise choose a clearly labeled proxy metric only if justified.
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
                    if not (profile.get("semantic_type") == "text" and profile.get("unique_ratio", 0.0) > 0.50):
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

        if validated["target"]:
            target_profile = self._get_profile(validated["target"], column_profiles)
            if target_profile and target_profile.get("is_probable_id", False):
                validated["reasoning"]["warnings"].append("Target looked like an ID column and was rejected.")
                validated["target"] = None

            if target_profile and target_profile.get("non_null_pct", 1.0) < 0.60:
                validated["reasoning"]["warnings"].append(
                    f"Target {validated['target']} has relatively high missingness."
                )

        if validated["analysis_type"] == "trend" and not validated["time_column"]:
            best_time = self._best_time_column(column_profiles)
            if best_time:
                validated["time_column"] = best_time
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
                if c.get("semantic_type") == "metric" and not c.get("is_probable_id", False)
            ]
            if len(numeric_candidates) < 2:
                validated["chart"] = "bar"

        if not validated["target"] and self._question_is_count_like(question_lower):
            validated["aggregation"] = "count"
            if validated["analysis_type"] == "comparison":
                validated["chart"] = "bar"

        return validated

    def _repair_plan_for_analysis_type(self, plan, column_profiles, question_lower):
        analysis_type = plan.get("analysis_type", "comparison")
        target = plan.get("target")
        drivers = plan.get("drivers", []) or []

        if analysis_type == "trend":
            if not plan.get("time_column"):
                best_time = self._best_time_column(column_profiles)
                if best_time:
                    plan["time_column"] = best_time

            if plan.get("aggregation") == "none":
                plan["aggregation"] = "sum"

            if plan.get("chart") in {"table", "bar"} and plan.get("time_column"):
                plan["chart"] = "line"

        elif analysis_type in {"comparison", "ranking", "composition"}:
            if plan.get("chart") == "table":
                plan["chart"] = "bar"

        elif analysis_type == "distribution":
            target_profile = self._get_profile(target, column_profiles)
            if target_profile and target_profile.get("semantic_type") == "metric":
                if plan.get("chart") == "table":
                    plan["chart"] = "histogram"
            else:
                plan["chart"] = "bar"

        elif analysis_type == "relationship":
            numeric_fields = [
                c["name"] for c in column_profiles
                if c.get("semantic_type") == "metric" and not c.get("is_probable_id", False)
            ]
            if len(numeric_fields) >= 2 and plan.get("chart") == "table":
                plan["chart"] = "scatter"
            elif len(numeric_fields) < 2:
                plan["chart"] = "bar"

            if target and self._get_profile(target, column_profiles):
                target_profile = self._get_profile(target, column_profiles)
                if target_profile.get("semantic_type") != "metric":
                    metric_candidates = [c for c in numeric_fields if c != target]
                    if metric_candidates:
                        plan["target"] = metric_candidates[0]
                        plan["reasoning"]["warnings"].append(
                            f"Relationship analysis target was adjusted to numeric field {metric_candidates[0]}."
                        )

        if not drivers and target:
            plan["drivers"] = self._fallback_drivers(
                column_profiles,
                target,
                question_lower,
                analysis_type=analysis_type
            )

        return plan

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
    # NEW: metric/group separation
    # ---------------------------

    def _resolve_metric_and_grouping(self, question_lower, column_profiles):
        warnings = []

        metric_candidate = self._explicit_metric_target(column_profiles, question_lower)
        grouping_candidate = self._explicit_grouping_dimension(column_profiles, question_lower)

        if metric_candidate and grouping_candidate and metric_candidate == grouping_candidate:
            grouping_candidate = None
            warnings.append(
                "The same column appeared to match both metric and grouping roles, so grouping was cleared."
            )

        # If user asks for a metric that does not exist, prefer safe proxy metric if reasonable
        requested_metric = self._extract_requested_metric_phrase(question_lower)
        if requested_metric and not metric_candidate:
            proxy = self._best_proxy_metric_for_requested_metric(requested_metric, column_profiles)
            if proxy:
                metric_candidate = proxy
                warnings.append(
                    f"No exact {requested_metric} field was found, so {proxy} was chosen as the closest valid proxy metric."
                )
            else:
                warnings.append(
                    f"No exact {requested_metric} field was found in the schema."
                )

        return metric_candidate, grouping_candidate, warnings

    def _explicit_grouping_dimension(self, column_profiles, question_lower):
        grouping_aliases = {
            "country": ["country", "countries", "market", "markets", "geography"],
            "region": ["region", "regions", "territory", "territories"],
            "state": ["state", "states", "province", "provinces"],
            "city": ["city", "cities", "town", "towns"],
            "category": ["category", "categories", "segment", "segments", "group", "groups", "class", "classes"],
            "product": ["product", "products", "item", "items", "sku", "stockcode", "stock code", "description"],
            "customer": ["customer", "customers", "client", "clients"],
            "store": ["store", "stores", "location", "locations", "branch", "branches"],
            "department": ["department", "departments"],
            "channel": ["channel", "channels", "source", "sources"],
            "brand": ["brand", "brands"],
            "invoice": ["invoice", "invoices", "order", "orders", "transaction", "transactions"]
        }

        best = None
        best_score = -999

        for canonical_group, aliases in grouping_aliases.items():
            if not any(alias in question_lower for alias in aliases):
                continue

            for col in column_profiles:
                name = col["name"]
                norm = self._normalize_name(name)
                semantic_type = col.get("semantic_type", "unknown")
                unique_ratio = self._safe_float(col.get("unique_ratio"), 0.0)

                score = 0.0

                if semantic_type == "categorical":
                    score += 6.0
                elif semantic_type == "datetime":
                    score += 1.0
                elif semantic_type == "metric":
                    score -= 4.0
                elif semantic_type == "text":
                    score -= 3.0
                elif semantic_type == "id":
                    score -= 10.0

                if col.get("is_probable_id", False):
                    score -= 10.0

                if canonical_group in norm:
                    score += 5.0

                if any(alias in norm for alias in aliases):
                    score += 3.0

                if unique_ratio > 0.98 and semantic_type in {"categorical", "text"}:
                    score -= 4.0

                if score > best_score:
                    best = name
                    best_score = score

        return best if best_score > 0 else None

    def _extract_requested_metric_phrase(self, question_lower):
        metric_aliases = {
            "profit": ["profit", "profits", "margin"],
            "sales": ["sales", "sale"],
            "revenue": ["revenue", "revenues"],
            "cost": ["cost", "costs", "expense", "expenses"],
            "quantity": ["quantity", "quantities", "qty", "units", "unit", "volume"],
            "discount": ["discount", "discounts"],
            "price": ["price", "prices", "unit price", "unitprice"],
            "amount": ["amount", "amounts", "value", "values"],
            "count": ["count", "counts", "number of", "how many"]
        }

        for canonical_metric, aliases in metric_aliases.items():
            if any(alias in question_lower for alias in aliases):
                return canonical_metric
        return None

    def _best_proxy_metric_for_requested_metric(self, requested_metric, column_profiles):
        proxy_preferences = {
            "revenue": ["sales", "amount", "price", "unit price", "unitprice", "profit", "quantity"],
            "sales": ["revenue", "amount", "price", "quantity"],
            "profit": ["margin", "revenue", "sales", "amount"],
            "quantity": ["units", "volume", "count"],
            "count": ["quantity", "units", "volume"]
        }

        preferred_terms = proxy_preferences.get(requested_metric, [])

        best = None
        best_score = -999

        for col in column_profiles:
            name = col["name"]
            norm = self._normalize_name(name)
            semantic_type = col.get("semantic_type", "unknown")

            if semantic_type != "metric":
                continue
            if col.get("is_probable_id", False):
                continue

            score = 0.0
            for term in preferred_terms:
                if term in norm:
                    score += 4.0

            if col.get("is_probable_metric", False):
                score += 2.0

            score += self._safe_float(col.get("non_null_pct"), 1.0)

            if score > best_score:
                best = name
                best_score = score

        return best if best_score > 0 else None

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
            "price": ["price", "prices", "unit price", "unitprice"],
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
                semantic_type = col.get("semantic_type", "unknown")
                score = 0.0

                if col.get("is_probable_id", False):
                    score -= 20

                # Metric-like targets should strongly prefer numeric/aggregatable fields
                if semantic_type == "metric":
                    score += 8
                elif semantic_type == "categorical":
                    score -= 5
                elif semantic_type == "datetime":
                    score -= 6
                elif semantic_type == "text":
                    score -= 8

                if col.get("is_probable_metric", False):
                    score += 4

                if canonical_metric in norm:
                    score += 5

                if any(alias in norm for alias in aliases):
                    score += 3

                if col.get("non_null_pct", 1.0) < 0.60:
                    score -= 2

                if score > best_score:
                    best = name
                    best_score = score

        return best if best_score > 0 else None

    # ---------------------------
    # Fallback target logic
    # ---------------------------

    def _fallback_target(self, column_profiles, question_lower):
        ranked = self._score_target_candidates(column_profiles, question_lower)
        if not ranked:
            return None, "No reasonable target candidate could be identified from the schema."

        best_name, best_score = ranked[0]
        if best_score <= 0:
            return best_name, (
                f"Target {best_name} was selected as a weak fallback because no strong business metric match was found."
            )

        return best_name, (
            f"Target {best_name} was selected by deterministic scoring using dtype, semantic meaning, completeness, and question alignment."
        )

    def _score_target_candidates(self, column_profiles, question_lower):
        metric_keywords = {
            "revenue", "sales", "profit", "cost", "amount", "price",
            "quantity", "margin", "income", "value", "discount", "count",
            "total", "score", "rate", "volume"
        }

        ranked = []

        for col in column_profiles:
            name = col["name"]
            norm = self._normalize_name(name)
            semantic_type = col.get("semantic_type", "unknown")
            non_null_pct = self._safe_float(col.get("non_null_pct"), 1.0)
            unique_ratio = self._safe_float(col.get("unique_ratio"), 0.0)
            is_probable_id = bool(col.get("is_probable_id", False))
            is_probable_metric = bool(col.get("is_probable_metric", False))

            score = 0.0

            if is_probable_id:
                score -= 100.0

            # Stronger separation: targets should prefer measurable fields
            if semantic_type == "metric":
                score += 9.0
            elif semantic_type == "categorical":
                score -= 2.0
            elif semantic_type == "unknown":
                score += 0.5
            elif semantic_type == "datetime":
                score -= 5.0
            elif semantic_type == "text":
                score -= 6.0
            elif semantic_type == "boolean":
                score -= 3.0

            if is_probable_metric:
                score += 4.0

            for kw in metric_keywords:
                if kw in norm:
                    score += 2.5
                if kw in question_lower and kw in norm:
                    score += 3.5

            question_tokens = set(self._normalize_name(question_lower).split())
            column_tokens = set(norm.split())
            score += 0.75 * len(question_tokens.intersection(column_tokens))

            score += non_null_pct * 2.5

            if non_null_pct < 0.60:
                score -= 3.0
            if non_null_pct < 0.40:
                score -= 3.0

            if unique_ratio > 0.98 and semantic_type != "metric":
                score -= 8.0
            elif unique_ratio > 0.90 and semantic_type == "categorical":
                score -= 5.0

            ranked.append((name, score))

        ranked.sort(key=lambda x: x[1], reverse=True)
        return ranked

    # ---------------------------
    # Fallback driver logic
    # ---------------------------

    def _fallback_drivers(self, column_profiles, target, question_lower, analysis_type=None, max_drivers=5):
        scored = []

        for col in column_profiles:
            name = col["name"]
            if name == target:
                continue

            norm = self._normalize_name(name)
            semantic_type = col.get("semantic_type", "unknown")
            unique_ratio = self._safe_float(col.get("unique_ratio"), 0.0)
            non_null_pct = self._safe_float(col.get("non_null_pct"), 1.0)
            is_probable_id = bool(col.get("is_probable_id", False))

            score = 0.0

            if is_probable_id:
                score -= 100.0

            if semantic_type == "categorical":
                score += 5.0
            elif semantic_type == "datetime":
                score += 4.5
            elif semantic_type == "metric":
                score += 2.0
            elif semantic_type == "text":
                score -= 5.0
            elif semantic_type == "boolean":
                score += 1.0

            if self._looks_like_category(name):
                score += 2.0

            if analysis_type == "trend":
                if semantic_type == "datetime":
                    score += 4.0
                if any(k in norm for k in ["month", "quarter", "year", "week", "date", "time"]):
                    score += 3.0
                if semantic_type == "categorical":
                    score += 1.5

            elif analysis_type in {"comparison", "ranking", "composition"}:
                if semantic_type == "categorical":
                    score += 3.0
                if any(k in norm for k in ["region", "segment", "category", "channel", "market", "brand", "status", "product", "country"]):
                    score += 2.5

            elif analysis_type == "relationship":
                if semantic_type == "metric":
                    score += 3.5
                if semantic_type == "categorical":
                    score += 1.0

            question_tokens = set(self._normalize_name(question_lower).split())
            column_tokens = set(norm.split())
            score += 0.75 * len(question_tokens.intersection(column_tokens))

            if unique_ratio > 0.95 and semantic_type == "categorical":
                score -= 5.0
            elif unique_ratio > 0.75 and semantic_type == "categorical":
                score -= 2.0

            if semantic_type == "text" and unique_ratio > 0.50:
                score -= 4.0

            if non_null_pct < 0.50:
                score -= 2.0

            scored.append((name, score))

        scored.sort(key=lambda x: x[1], reverse=True)

        ranked = [name for name, score in scored if score > 0]
        if ranked:
            return ranked[:max_drivers]

        return [c["name"] for c in column_profiles if c["name"] != target][:max_drivers]

    def _best_time_column(self, column_profiles):
        scored = []

        for col in column_profiles:
            name = col["name"]
            norm = self._normalize_name(name)
            semantic_type = col.get("semantic_type", "unknown")
            is_probable_datetime = bool(col.get("is_probable_datetime", False))
            non_null_pct = self._safe_float(col.get("non_null_pct"), 1.0)

            score = 0.0

            if semantic_type == "datetime":
                score += 8.0
            if is_probable_datetime:
                score += 6.0
            if any(k in norm for k in ["order date", "sale date", "transaction date", "date", "time", "timestamp"]):
                score += 3.0
            if any(k in norm for k in ["year", "month", "quarter", "week", "day"]):
                score += 2.0

            score += non_null_pct

            scored.append((name, score))

        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[0][0] if scored and scored[0][1] > 0 else None

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
            "postal", "zip", "zipcode", "invoice no", "invoice number"
        ]
        return any(k in norm for k in id_keywords)

    def _looks_like_metric(self, name):
        norm = self._normalize_name(name)
        metric_keywords = [
            "sales", "revenue", "profit", "amount", "price", "cost",
            "income", "margin", "quantity", "qty", "units", "discount",
            "value", "score", "rate", "count", "total", "volume"
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

    def _looks_like_category(self, name):
        norm = self._normalize_name(name)
        categorical_keywords = [
            "region", "country", "state", "city", "category", "segment",
            "product", "sub category", "channel", "customer", "ship mode",
            "department", "type", "group", "class", "market", "brand", "status",
            "store", "branch", "location"
        ]
        return any(k in norm for k in categorical_keywords)

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

    def _dtype_is_numeric(self, dtype):
        dtype = str(dtype).lower()
        numeric_markers = ["int", "float", "double", "decimal", "number"]
        return any(marker in dtype for marker in numeric_markers)

    def _dtype_is_datetime(self, dtype):
        dtype = str(dtype).lower()
        return "datetime" in dtype or "timestamp" in dtype or dtype.startswith("date")

    def _dtype_is_bool(self, dtype):
        dtype = str(dtype).lower()
        return "bool" in dtype

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