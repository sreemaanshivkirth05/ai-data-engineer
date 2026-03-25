import json
from llm.openai_client import OpenAIClient


class PlannerAgent:
    def __init__(self):
        self.llm = OpenAIClient()

    def run(self, question, columns):
        columns = [str(col).strip() for col in columns]
        normalized_map = {str(col).strip().lower(): col for col in columns}

        prompt = f"""
You are a senior data analysis planner.

User question:
"{question}"

Dataset columns:
{columns}

Task:
1. Select the single best target column to analyze.
2. Select the best driver columns that either explain, segment, or group the target.
3. Prefer a numeric business metric as the target when possible.
4. Prefer date, category, region, segment, product, channel, or customer-like fields as drivers.
5. Do not return the target inside drivers.
6. Return only valid column names from the provided list.

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

        if not target:
            target = self._fallback_target(columns, question)

        if not drivers:
            drivers = self._fallback_drivers(columns, target, question)

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
            col_lower = col.lower()
            if lower_candidate == col_lower:
                return col
            if lower_candidate in col_lower or col_lower in lower_candidate:
                return col

        return None

    def _fallback_target(self, columns, question):
        q = (question or "").lower()

        business_metric_priority = [
            "revenue", "sales", "profit", "amount", "price", "cost",
            "income", "margin", "value", "quantity", "units", "count"
        ]

        for keyword in business_metric_priority:
            for col in columns:
                if keyword in col.lower():
                    return col

        for col in columns:
            col_lower = col.lower()
            if any(word in q for word in ["trend", "over time", "growth", "performance", "summary"]):
                if any(metric in col_lower for metric in business_metric_priority):
                    return col

        return columns[-1] if columns else None

    def _fallback_drivers(self, columns, target, question):
        q = (question or "").lower()
        driver_priority = [
            "date", "time", "region", "country", "state", "city",
            "category", "segment", "product", "channel", "customer",
            "department", "type", "group"
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

            if col_lower in q:
                score += 5

            scored.append((col, score))

        scored.sort(key=lambda x: x[1], reverse=True)

        ranked = [col for col, score in scored if score > 0]
        if ranked:
            return ranked[:5]

        return [col for col in columns if col != target][:5]