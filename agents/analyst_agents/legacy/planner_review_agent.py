import json
import os
from typing import Any, Dict, List, Optional


class PlannerReviewAgent:
    """
    OpenAI-powered planner reviewer.

    This agent does NOT execute analysis.
    It reviews the Universal Planner contract against the current pipeline plan
    and recommends whether to trust the Universal Planner, keep the current plan,
    ask for clarification, or fallback to general analysis.
    """

    def __init__(self, model: str = "gpt-4o-mini"):
        self.model = model

    def run(
        self,
        question: str,
        columns: List[str],
        current_plan: Dict[str, Any],
        universal_contract: Optional[Dict[str, Any]],
        dataset_context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        if not universal_contract:
            return self._fallback_response(
                decision="use_current_pipeline",
                reason="No Universal Planner contract was available.",
            )

        # If OpenAI is not configured, return a safe deterministic review.
        if not os.getenv("OPENAI_API_KEY"):
            return self._rule_based_review(
                question=question,
                columns=columns,
                current_plan=current_plan,
                universal_contract=universal_contract,
                dataset_context=dataset_context,
                note="OPENAI_API_KEY not found, used rule-based reviewer fallback.",
            )

        try:
            from openai import OpenAI
            client = OpenAI()

            prompt = self._build_prompt(
                question=question,
                columns=columns,
                current_plan=current_plan,
                universal_contract=universal_contract,
                dataset_context=dataset_context,
            )

            response = client.chat.completions.create(
                model=self.model,
                temperature=0.0,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are a careful data analysis planner reviewer. "
                            "You must return only valid JSON. "
                            "Do not invent columns. Use only the columns provided. "
                            "Prefer the Universal Planner when it is safe, specific, and schema-valid. "
                            "Prefer the current pipeline when the Universal Planner is unsafe, too broad, or incompatible. "
                            "Ask for clarification only when neither plan is reliable."
                        ),
                    },
                    {
                        "role": "user",
                        "content": prompt,
                    },
                ],
            )

            content = response.choices[0].message.content
            parsed = self._safe_json_loads(content)

            if parsed is None:
                return self._rule_based_review(
                    question=question,
                    columns=columns,
                    current_plan=current_plan,
                    universal_contract=universal_contract,
                    dataset_context=dataset_context,
                    note="LLM response was not valid JSON, used rule-based fallback.",
                )

            return self._validate_review(parsed, columns)

        except Exception as exc:
            fallback = self._rule_based_review(
                question=question,
                columns=columns,
                current_plan=current_plan,
                universal_contract=universal_contract,
                dataset_context=dataset_context,
                note=f"LLM reviewer failed: {exc}. Used rule-based fallback.",
            )
            return fallback

    def _build_prompt(
        self,
        question: str,
        columns: List[str],
        current_plan: Dict[str, Any],
        universal_contract: Dict[str, Any],
        dataset_context: Optional[Dict[str, Any]] = None,
    ) -> str:
        payload = {
            "task": "Review two planning outputs for a data analysis question.",
            "question": question,
            "available_columns": columns,
            "dataset_context": dataset_context or {},
            "current_pipeline_plan": current_plan,
            "universal_planner_contract": universal_contract,
            "instructions": {
                "choose_one_decision": [
                    "use_universal_planner",
                    "use_current_pipeline",
                    "ask_clarification",
                    "fallback_to_general_analysis",
                ],
                "rules": [
                    "Do not invent columns.",
                    "If Universal Planner is safe_to_execute=true and question-specific, prefer it.",
                    "If Universal Planner has needs_fallback=true or safe_to_execute=false, do not use it directly.",
                    "For rate questions like cancellation rate, churn rate, attrition rate, prefer target-rate logic.",
                    "For broad dataset-summary questions, do not force a single random dimension.",
                    "If both plans are weak, ask clarification.",
                ],
            },
            "required_output_json_schema": {
                "decision": "use_universal_planner | use_current_pipeline | ask_clarification | fallback_to_general_analysis",
                "final_target": "column name or null",
                "final_drivers": ["list of column names"],
                "final_time_column": "column name or null",
                "final_aggregation": "sum | avg | mean | count | none | null",
                "final_chart": "bar | line | scatter | box | histogram | heatmap | table | dashboard | null",
                "confidence": "high | medium | low",
                "reason": "short explanation",
                "warnings": ["list of warnings"],
            },
        }

        return json.dumps(payload, indent=2)

    def _safe_json_loads(self, text: str) -> Optional[Dict[str, Any]]:
        try:
            cleaned = text.strip()

            if cleaned.startswith("```"):
                cleaned = cleaned.strip("`")
                if cleaned.lower().startswith("json"):
                    cleaned = cleaned[4:].strip()

            return json.loads(cleaned)
        except Exception:
            return None

    def _validate_review(self, review: Dict[str, Any], columns: List[str]) -> Dict[str, Any]:
        valid_decisions = {
            "use_universal_planner",
            "use_current_pipeline",
            "ask_clarification",
            "fallback_to_general_analysis",
        }

        decision = review.get("decision")
        if decision not in valid_decisions:
            review["decision"] = "use_current_pipeline"
            review.setdefault("warnings", []).append(
                "Invalid reviewer decision; defaulted to use_current_pipeline."
            )

        final_target = review.get("final_target")
        if final_target and final_target not in columns:
            review["final_target"] = None
            review.setdefault("warnings", []).append(
                f"Reviewer selected invalid target column: {final_target}"
            )

        final_time_column = review.get("final_time_column")
        if final_time_column and final_time_column not in columns:
            review["final_time_column"] = None
            review.setdefault("warnings", []).append(
                f"Reviewer selected invalid time column: {final_time_column}"
            )

        final_drivers = review.get("final_drivers") or []
        valid_drivers = [col for col in final_drivers if col in columns]
        invalid_drivers = [col for col in final_drivers if col not in columns]

        if invalid_drivers:
            review.setdefault("warnings", []).append(
                f"Removed invalid driver columns: {invalid_drivers}"
            )

        review["final_drivers"] = valid_drivers

        if review.get("confidence") not in {"high", "medium", "low"}:
            review["confidence"] = "medium"

        review.setdefault("reason", "")
        review.setdefault("warnings", [])

        return review

    def _rule_based_review(
        self,
        question: str,
        columns: List[str],
        current_plan: Dict[str, Any],
        universal_contract: Optional[Dict[str, Any]],
        dataset_context: Optional[Dict[str, Any]] = None,
        note: str = "",
    ) -> Dict[str, Any]:
        if not universal_contract:
            return self._fallback_response(
                decision="use_current_pipeline",
                reason="No Universal Planner contract available.",
                warning=note,
            )

        safe = bool(universal_contract.get("safe_to_execute"))
        needs_fallback = bool(universal_contract.get("needs_fallback"))
        operation = universal_contract.get("operation")
        contract_columns = universal_contract.get("columns", {}) or {}

        if not safe or needs_fallback:
            return self._fallback_response(
                decision="use_current_pipeline",
                reason="Universal Planner contract was unsafe or required fallback.",
                warning=note,
            )

        if operation == "full_dataset_analysis":
            return {
                "decision": "use_current_pipeline",
                "final_target": current_plan.get("target"),
                "final_drivers": [],
                "final_time_column": current_plan.get("time_column"),
                "final_aggregation": current_plan.get("aggregation"),
                "final_chart": current_plan.get("chart"),
                "confidence": "medium",
                "reason": (
                    "Broad full-dataset analysis should preserve the current executable plan "
                    "while clearing noisy drivers."
                ),
                "warnings": [note] if note else [],
            }

        target = (
            universal_contract.get("main_target")
            or contract_columns.get("measure")
            or contract_columns.get("target")
            or current_plan.get("target")
        )

        drivers = universal_contract.get("main_drivers")
        if drivers is None:
            dimension = contract_columns.get("dimension")
            drivers = [dimension] if dimension else []

        aggregation = universal_contract.get("main_aggregation") or current_plan.get("aggregation")
        if aggregation == "rate":
            aggregation = "avg"

        return {
            "decision": "use_universal_planner",
            "final_target": target if target in columns else current_plan.get("target"),
            "final_drivers": [d for d in drivers if d in columns],
            "final_time_column": universal_contract.get("main_time_column")
            or contract_columns.get("time")
            or current_plan.get("time_column"),
            "final_aggregation": aggregation,
            "final_chart": universal_contract.get("main_chart") or current_plan.get("chart"),
            "confidence": "medium",
            "reason": "Universal Planner contract is safe and schema-valid.",
            "warnings": [note] if note else [],
        }

    def _fallback_response(
        self,
        decision: str,
        reason: str,
        warning: str = "",
    ) -> Dict[str, Any]:
        warnings = []
        if warning:
            warnings.append(warning)

        return {
            "decision": decision,
            "final_target": None,
            "final_drivers": [],
            "final_time_column": None,
            "final_aggregation": None,
            "final_chart": None,
            "confidence": "low",
            "reason": reason,
            "warnings": warnings,
        }