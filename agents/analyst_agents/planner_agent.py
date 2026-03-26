import json
from llm.openai_client import OpenAIClient


class PlannerAgent:
    def __init__(self):
        self.llm = OpenAIClient()

    def run(self, question, columns):
        columns = [str(col).strip() for col in columns]
        normalized_map = {str(col).strip().lower(): col for col in columns}
        question_lower = (question or "").lower().strip()

        prompt = f"""
You are a senior data analysis planner.

User question:
"{question}"

Dataset columns:
{columns}

Task:
1. Select the single best target column to analyze.
2. Select the best driver columns that either explain, segment, or group the target.
3. If the user explicitly mentions a metric like profit, sales, revenue, cost, quantity, discount, or margin, prefer the matching column as the target.
4. Prefer a numeric business metric as the target when possible.
5. Prefer date, category, region, segment, product, channel, or customer-like fields as drivers.
6. Do not return the target inside drivers.
7. Return only valid column names from the provided list.

Return ONLY JSON in this format:
{{"target": "string", "drivers": ["string", "string", "string"]}}
""".strip()

        target = None
        drivers = []

        try:
            response = self.llm.generate(prompt)
            response = response.replace("```json", "").replace("```", "").strip()
            plan = json.loads(response)

            raw_target = str(plan.get("target", "")).strip()
            raw_drivers = plan.get("drivers", [])

            target = self._match_column(raw_target, columns, normalized_map)
            drivers = [
                matched
                for matched in [
                    self._match_column(str(driver).strip(), columns, normalized_map)
                    for driver in raw_drivers
                ]
                if matched and matched != target
            ]

        except Exception as e:
            print("PlannerAgent LLM error:", e)

        # strongest fallback: explicit metric mention in question
        explicit_target = self._explicit_metric_target(columns, question_lower)
        if explicit_target:
            target = explicit_target

        if not target:
            target = self._fallback_target(columns, question_lower)

        if not drivers:
            drivers = self._fallback_drivers(columns, target, question_lower)

        drivers = self._dedupe_keep_order(drivers)

        return {
            "target": target,
            "drivers": drivers[:5]
        }

    def _match_column(self, candidate, columns, normalized_map):
        if not candidate:
            return None

        if candidate in columns:
            return candidate

        lower_candidate = candidate.lower().strip()

        if lower_candidate in normalized_map:
            return normalized_map[lower_candidate]

        for col in columns:
            col_lower = col.lower().strip()
            if lower_candidate == col_lower:
                return col
            if lower_candidate in col_lower or col_lower in lower_candidate:
                return col

        return None

    def _explicit_metric_target(self, columns, question_lower):
        metric_aliases = {
            "profit": ["profit", "profits", "margin"],
            "sales": ["sales", "sale"],
            "revenue": ["revenue", "revenues"],
            "cost": ["cost", "costs", "expense", "expenses"],
            "quantity": ["quantity", "qty", "units", "unit", "volume"],
            "discount": ["discount", "discounts"],
            "price": ["price", "prices"],
            "amount": ["amount", "amounts", "value", "values"]
        }

        matched_metric = None
        for canonical_metric, aliases in metric_aliases.items():
            if any(alias in question_lower for alias in aliases):
                matched_metric = canonical_metric
                break

        if not matched_metric:
            return None

        # exact/strong contains match in column names
        for col in columns:
            col_lower = col.lower()
            if matched_metric in col_lower:
                return col

        # alias-based match
        for alias in metric_aliases[matched_metric]:
            for col in columns:
                if alias in col.lower():
                    return col

        return None

    def _fallback_target(self, columns, question_lower):
        business_metric_priority = [
            "revenue", "profit", "sales", "amount", "price", "cost",
            "income", "margin", "value", "quantity", "units", "count", "discount"
        ]

        # if trend-like question, prefer a business metric, not a categorical field
        for keyword in business_metric_priority:
            for col in columns:
                if keyword in col.lower():
                    return col

        return columns[-1] if columns else None

    def _fallback_drivers(self, columns, target, question_lower):
        driver_priority = [
            "date", "time", "year", "month",
            "region", "country", "state", "city",
            "category", "segment", "product", "sub-category",
            "channel", "customer", "ship mode", "department", "type", "group"
        ]

        scored = []

        for col in columns:
            if col == target:
                continue

            score = 0
            col_lower = col.lower()

            for idx, keyword in enumerate(driver_priority):
                if keyword in col_lower:
                    score += (len(driver_priority) - idx)

            if col_lower in question_lower:
                score += 5

            # penalize IDs and weak grouping columns
            if "id" in col_lower or "postal" in col_lower or "zip" in col_lower:
                score -= 5

            scored.append((col, score))

        scored.sort(key=lambda x: x[1], reverse=True)

        ranked = [col for col, score in scored if score > 0]
        if ranked:
            return ranked[:5]

        return [col for col in columns if col != target][:5]

    def _dedupe_keep_order(self, items):
        seen = set()
        result = []
        for item in items:
            if item not in seen:
                result.append(item)
                seen.add(item)
        return result