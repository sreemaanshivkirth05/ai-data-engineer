from difflib import SequenceMatcher
from typing import Dict, Any, List, Optional


class ColumnResolver:
    """
    Resolves target, group, and time columns using deterministic scoring.
    """

    METRIC_HINT_MAP = {
        "revenue": ["revenue", "sales", "amount", "total", "value", "income"],
        "sales": ["sales", "amount", "revenue", "value"],
        "amount": ["amount", "sales", "revenue", "value"],
        "profit": ["profit", "margin"],
        "cost": ["cost", "expense", "spend"],
        "price": ["price", "unit price"],
        "quantity": ["quantity", "qty", "units"],
        "value": ["value", "amount", "sales", "revenue"],
        "income": ["income", "revenue", "amount"],
        "spend": ["spend", "cost", "expense"],
    }

    GROUP_HINT_MAP = {
        "country": ["country", "nation"],
        "region": ["region", "zone", "area"],
        "state": ["state"],
        "city": ["city", "town"],
        "product": ["product", "item", "sku"],
        "sales person": ["sales person", "salesperson", "seller", "rep"],
        "salesperson": ["salesperson", "sales person", "seller", "rep"],
        "customer": ["customer", "client", "buyer"],
        "segment": ["segment", "group"],
        "category": ["category", "class"],
        "department": ["department", "dept"],
        "channel": ["channel", "source"],
    }

    TIME_HINT_MAP = {
        "date": ["date", "order date", "transaction date", "created date"],
        "time": ["time", "timestamp", "created at", "event time"],
        "month": ["date", "month", "order date"],
        "year": ["date", "year", "order date"],
        "quarter": ["date", "quarter", "order date"],
        "week": ["date", "week", "order date"],
        "day": ["date", "day", "order date"],
        "timestamp": ["timestamp", "event time", "created at"],
        "created": ["created", "created at", "created date"],
        "order date": ["order date", "date"],
    }

    def _similarity(self, a: str, b: str) -> float:
        return SequenceMatcher(None, a.lower(), b.lower()).ratio()

    def _score_name(self, column_name: str, aliases: List[str]) -> float:
        col = column_name.lower()
        score = 0.0
        for alias in aliases:
            alias_l = alias.lower()
            if alias_l == col:
                score = max(score, 1.0)
            elif alias_l in col:
                score = max(score, 0.85)
            else:
                score = max(score, self._similarity(col, alias_l) * 0.75)
        return score

    def _pick_best(self, candidates: List[str], aliases: List[str]) -> Optional[str]:
        best_col = None
        best_score = 0.0
        for col in candidates:
            score = self._score_name(col, aliases)
            if score > best_score:
                best_score = score
                best_col = col
        return best_col

    def resolve(
        self,
        plan: Dict[str, Any],
        dataset_profile: Dict[str, Any],
    ) -> Dict[str, Any]:
        numeric_columns = dataset_profile.get("numeric_columns", [])
        categorical_columns = dataset_profile.get("categorical_columns", [])
        datetime_columns = dataset_profile.get("datetime_columns", [])

        target_hint = plan.get("target_metric_hint")
        group_hints = plan.get("group_by_hint", [])
        time_hint = plan.get("time_column_hint")

        target_metric = None
        if target_hint and target_hint in self.METRIC_HINT_MAP:
            target_metric = self._pick_best(numeric_columns, self.METRIC_HINT_MAP[target_hint])

        if not target_metric:
            metric_candidates = dataset_profile.get("metric_candidates") or numeric_columns
            target_metric = metric_candidates[0] if metric_candidates else None

        group_by = []
        for hint in group_hints:
            if hint in self.GROUP_HINT_MAP:
                col = self._pick_best(categorical_columns, self.GROUP_HINT_MAP[hint])
                if col and col not in group_by:
                    group_by.append(col)

        if not group_by and categorical_columns and plan["question_type"] in {"ranking", "comparison", "contribution"}:
            group_by = [categorical_columns[0]]

        time_column = None
        if time_hint and time_hint in self.TIME_HINT_MAP:
            time_column = self._pick_best(datetime_columns, self.TIME_HINT_MAP[time_hint])

        if not time_column and datetime_columns and plan["question_type"] == "trend":
            time_column = datetime_columns[0]

        # choose time grain
        time_grain = "month" if plan["question_type"] == "trend" else None

        resolved = {
            "target_metric": target_metric,
            "group_by": group_by,
            "time_column": time_column,
            "time_grain": time_grain,
            "filters": plan.get("filters", []),
            "aggregation": plan.get("aggregation", "sum"),
            "sort": plan.get("sort", "desc"),
            "limit": plan.get("limit", 5),
            "question_type": plan.get("question_type"),
        }

        warnings = []
        if plan["question_type"] != "summary" and not target_metric:
            warnings.append("Could not resolve a numeric target metric.")
        if plan["question_type"] in {"ranking", "comparison", "contribution"} and not group_by:
            warnings.append("Could not resolve a grouping column.")
        if plan["question_type"] == "trend" and not time_column:
            warnings.append("Could not resolve a time column.")

        resolved["warnings"] = warnings
        return resolved