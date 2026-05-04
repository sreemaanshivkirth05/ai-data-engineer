import json
from llm.huggingface_client import HuggingFaceClient


# Columns that should NEVER be cleaned — they are identifiers, not values.
# Text-standardising an Order ID destroys its format.
# Filling a Postal Code with a numeric median produces nonsense.
ID_COLUMN_KEYWORDS = [
    "id", "uuid", "key", "row number", "rownum",
    "transaction id", "order id", "customer id", "product id",
    "postal", "postal code", "zip", "zipcode", "row id",
]


def _is_protected_id_column(col_name: str, semantic_type: str, unique_ratio: float) -> bool:
    """Return True if this column should be excluded from cleaning actions."""
    if semantic_type == "id":
        return True
    norm = str(col_name).lower().replace("_", " ").strip()
    if any(kw in norm for kw in ID_COLUMN_KEYWORDS):
        return True
    # Near-unique string columns are almost certainly identifiers
    if unique_ratio >= 0.90:
        return True
    return False


class CleaningPlannerAgent:
    def __init__(self):
        self.llm = HuggingFaceClient()

    def run(self, dataset_profile, business_requirements=""):
        prompt = self._build_prompt(dataset_profile, business_requirements)
        response = self.llm.generate(prompt, max_tokens=1800)
        response = self._clean_response(response)

        try:
            plan = json.loads(response)
        except Exception as e:
            print(f"CleaningPlannerAgent JSON parse failed: {e}")
            print("RAW HF RESPONSE:", response)
            plan = self._fallback_plan(dataset_profile)

        return self._validate_plan(plan, dataset_profile)

    def _build_prompt(self, dataset_profile, business_requirements):
        return f"""
You are a senior data cleaning planner for a production AI Data Cleaner.

You do NOT clean data yourself.
You only produce a deterministic cleaning plan that Python will execute.

DATASET PROFILE:
{json.dumps(dataset_profile, indent=2)}

BUSINESS REQUIREMENTS:
{business_requirements}

STRICT RULES:
1. Use ONLY exact column names from the dataset profile.
2. Treat ERROR, UNKNOWN, N/A, NULL, ?, empty strings, and blank strings as invalid placeholder values.
3. Use median fill for numeric/metric columns ONLY (not for ID, postal code, or text columns).
4. Use mode fill for categorical columns.
5. Use datetime casting for date-like columns (semantic_type == datetime).
6. Use standardize_date for date format normalisation.
7. Use standardize_text ONLY for categorical columns (segment, region, product name, etc).
8. NEVER apply standardize_text, fill_missing, or cast_type to any column whose semantic_type is "id",
   or whose name contains "id", "postal", "zip", "zipcode", "row id", "order id", "customer id".
9. If duplicate_rows > 0, include remove_duplicates.
10. If a column has missing values AND is not an ID column, include fill_missing.
11. Return valid JSON only.

ALLOWED ACTIONS:
- replace_invalid_values
- fill_missing
- cast_type
- standardize_text
- standardize_date
- remove_duplicates
- clip_outliers

ALLOWED ISSUE TYPES:
- missing_values
- type_mismatch
- duplicates
- outliers
- inconsistent_format
- invalid_category
- invalid_placeholder_values

ALLOWED TARGET TYPES FOR cast_type:
- number
- datetime
- string

Return JSON in EXACTLY this structure:
{{
  "issues": [
    {{
      "column": "column_name_or_null",
      "issue_type": "missing_values | type_mismatch | duplicates | outliers | inconsistent_format | invalid_category | invalid_placeholder_values",
      "severity": "high | medium | low",
      "recommendation": "short recommendation"
    }}
  ],
  "cleaning_steps": [
    {{
      "action": "replace_invalid_values | fill_missing | cast_type | standardize_text | standardize_date | remove_duplicates | clip_outliers",
      "column": "column_name_or_null",
      "parameters": {{}},
      "reason": "short explanation"
    }}
  ],
  "validation_checks": [
    "short validation check"
  ]
}}
""".strip()

    def _clean_response(self, response):
        if not response:
            return "{}"
        cleaned = str(response).replace("```json", "").replace("```", "").strip()
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start != -1 and end != -1 and end > start:
            cleaned = cleaned[start:end + 1]
        return cleaned

    def _validate_plan(self, plan, dataset_profile):
        profile_map = {
            str(col.get("name")).strip(): col
            for col in dataset_profile.get("columns", [])
            if str(col.get("name", "")).strip()
        }
        valid_columns = set(profile_map.keys())

        allowed_issue_types = {
            "missing_values", "type_mismatch", "duplicates", "outliers",
            "inconsistent_format", "invalid_category", "invalid_placeholder_values"
        }
        allowed_actions = {
            "replace_invalid_values", "fill_missing", "cast_type",
            "standardize_text", "standardize_date", "remove_duplicates", "clip_outliers"
        }
        allowed_severities = {"high", "medium", "low"}

        issues = plan.get("issues", []) if isinstance(plan.get("issues", []), list) else []
        steps = plan.get("cleaning_steps", []) if isinstance(plan.get("cleaning_steps", []), list) else []
        checks = plan.get("validation_checks", []) if isinstance(plan.get("validation_checks", []), list) else []

        validated_issues = []
        for item in issues:
            if not isinstance(item, dict):
                continue
            column = item.get("column")
            if column is not None and column not in valid_columns and column != "null":
                continue
            issue_type = str(item.get("issue_type", "")).strip()
            severity = str(item.get("severity", "medium")).strip().lower()
            recommendation = str(item.get("recommendation", "")).strip()
            if issue_type not in allowed_issue_types:
                continue
            if severity not in allowed_severities:
                severity = "medium"
            # Don't surface issues for ID columns (they are expected to look odd)
            if column:
                col_profile = profile_map.get(column, {})
                if _is_protected_id_column(column, col_profile.get("semantic_type", ""), col_profile.get("unique_ratio", 0.0)):
                    continue
            validated_issues.append({
                "column": None if column in [None, "null"] else column,
                "issue_type": issue_type,
                "severity": severity,
                "recommendation": recommendation
            })

        validated_steps = []
        for item in steps:
            if not isinstance(item, dict):
                continue
            action = str(item.get("action", "")).strip()
            column = item.get("column")
            parameters = item.get("parameters", {}) if isinstance(item.get("parameters", {}), dict) else {}
            reason = str(item.get("reason", "")).strip()

            if action not in allowed_actions:
                continue

            if column is not None and column not in valid_columns:
                if not (action == "remove_duplicates" and column in [None, "null"]):
                    continue

            # PROTECTION: never clean ID-like columns
            if column and action != "remove_duplicates":
                col_profile = profile_map.get(column, {})
                semantic_type = col_profile.get("semantic_type", "")
                unique_ratio = float(col_profile.get("unique_ratio", 0.0))
                if _is_protected_id_column(column, semantic_type, unique_ratio):
                    print(f"[CleaningPlanner] Skipping {action} on protected ID column: {column}")
                    continue

            column_profile = profile_map.get(column) if column else None
            parameters = self._normalize_parameters(action, parameters, column_profile)

            validated_steps.append({
                "action": action,
                "column": None if column in [None, "null"] else column,
                "parameters": parameters,
                "reason": reason
            })

        validated_steps = self._dedupe_steps(validated_steps)

        if not validated_steps:
            return self._fallback_plan(dataset_profile)

        validated_checks = [str(c).strip() for c in checks if str(c).strip()][:8]
        if not validated_checks:
            validated_checks = self._default_validation_checks()

        return {
            "issues": validated_issues[:20],
            "cleaning_steps": validated_steps[:25],
            "validation_checks": validated_checks
        }

    def _normalize_parameters(self, action, parameters, column_profile=None):
        semantic_type = str((column_profile or {}).get("semantic_type", "")).lower().strip()
        col_name = str((column_profile or {}).get("name", "")).lower().strip()

        if action == "fill_missing":
            # Numeric/metric → median. Everything else → mode.
            if semantic_type in {"metric", "numeric"}:
                return {"strategy": "median"}
            return {"strategy": "mode"}

        if action == "cast_type":
            if semantic_type == "datetime" or any(x in col_name for x in ["date", "time", "timestamp"]):
                return {"target_type": "datetime"}
            if semantic_type in {"metric", "numeric"}:
                return {"target_type": "number"}
            return {"target_type": "string"}

        if action == "standardize_text":
            style = str(parameters.get("style", "title")).lower().strip()
            if style not in {"title", "lower", "upper"}:
                style = "title"
            return {"style": style}

        if action == "standardize_date":
            output_format = str(parameters.get("format", "%Y-%m-%d")).strip()
            return {"format": output_format or "%Y-%m-%d"}

        if action == "replace_invalid_values":
            invalid_values = parameters.get("invalid_values", ["ERROR", "UNKNOWN", "N/A", "NULL", "?", ""])
            if not isinstance(invalid_values, list):
                invalid_values = ["ERROR", "UNKNOWN", "N/A", "NULL", "?", ""]
            return {"invalid_values": invalid_values, "replacement": None}

        if action == "remove_duplicates":
            subset = parameters.get("subset")
            return {"subset": subset} if isinstance(subset, list) else {}

        return parameters

    def _fallback_plan(self, dataset_profile):
        columns = dataset_profile.get("columns", [])
        duplicate_rows = int(dataset_profile.get("duplicate_rows", 0))

        issues = []
        steps = []

        if duplicate_rows > 0:
            issues.append({
                "column": None,
                "issue_type": "duplicates",
                "severity": "medium",
                "recommendation": "Remove duplicate rows to avoid double counting."
            })
            steps.append({
                "action": "remove_duplicates",
                "column": None,
                "parameters": {},
                "reason": "Duplicate rows were detected in the dataset."
            })

        for col in columns:
            name = str(col.get("name", "")).strip()
            if not name:
                continue
            dtype = str(col.get("dtype", "")).lower().strip()
            semantic_type = str(col.get("semantic_type", "unknown")).lower().strip()
            null_pct = float(col.get("null_pct", 0.0) or 0.0)
            unique_ratio = float(col.get("unique_ratio", 0.0))
            sample_values = [str(v).upper() for v in col.get("sample_values", []) if v is not None]

            # HARD SKIP: never touch identifier columns
            if _is_protected_id_column(name, semantic_type, unique_ratio):
                continue

            # Invalid placeholder detection
            if any(v in {"ERROR", "UNKNOWN", "N/A", "NULL", "?"} for v in sample_values):
                issues.append({
                    "column": name,
                    "issue_type": "invalid_placeholder_values",
                    "severity": "medium",
                    "recommendation": f"Replace invalid placeholder values in {name}."
                })
                steps.append({
                    "action": "replace_invalid_values",
                    "column": name,
                    "parameters": {"invalid_values": ["ERROR", "UNKNOWN", "N/A", "NULL", "?", ""]},
                    "reason": f"{name} contains invalid placeholder values."
                })

            # Date columns: cast + standardise format
            if semantic_type == "datetime":
                if "object" in dtype:
                    issues.append({
                        "column": name,
                        "issue_type": "type_mismatch",
                        "severity": "medium",
                        "recommendation": f"Cast {name} to datetime."
                    })
                    steps.append({
                        "action": "cast_type",
                        "column": name,
                        "parameters": {"target_type": "datetime"},
                        "reason": f"Cast {name} to datetime."
                    })
                steps.append({
                    "action": "standardize_date",
                    "column": name,
                    "parameters": {"format": "%Y-%m-%d"},
                    "reason": f"Standardise date format in {name}."
                })

            # Numeric columns stored as string
            elif semantic_type in {"metric", "numeric"} and "object" in dtype:
                issues.append({
                    "column": name,
                    "issue_type": "type_mismatch",
                    "severity": "medium",
                    "recommendation": f"Cast {name} to number."
                })
                steps.append({
                    "action": "cast_type",
                    "column": name,
                    "parameters": {"target_type": "number"},
                    "reason": f"Cast {name} to number."
                })

            # Categorical text columns: standardise casing
            elif semantic_type == "categorical":
                issues.append({
                    "column": name,
                    "issue_type": "inconsistent_format",
                    "severity": "low",
                    "recommendation": f"Standardise text format in {name}."
                })
                steps.append({
                    "action": "standardize_text",
                    "column": name,
                    "parameters": {"style": "title"},
                    "reason": f"Standardise text in {name}."
                })

            # Missing value imputation — only for non-ID columns
            if null_pct > 0:
                issues.append({
                    "column": name,
                    "issue_type": "missing_values",
                    "severity": "high" if null_pct >= 25 else "medium" if null_pct >= 10 else "low",
                    "recommendation": f"Fill missing values in {name}."
                })
                strategy = "median" if semantic_type in {"metric", "numeric"} else "mode"
                steps.append({
                    "action": "fill_missing",
                    "column": name,
                    "parameters": {"strategy": strategy},
                    "reason": f"Fill missing values in {name} using {strategy}."
                })

            # Outlier detection for numeric columns
            stats = col.get("stats", {}) or {}
            min_val = stats.get("min")
            max_val = stats.get("max")
            if (
                semantic_type in {"metric", "numeric"}
                and min_val is not None and max_val is not None
                and max_val != 0
                and abs(max_val) > abs(min_val) * 20
                and abs(max_val) > 100
            ):
                issues.append({
                    "column": name,
                    "issue_type": "outliers",
                    "severity": "medium",
                    "recommendation": f"Review and cap extreme outliers in {name}."
                })
                steps.append({
                    "action": "clip_outliers",
                    "column": name,
                    "parameters": {},
                    "reason": f"{name} appears to have extreme values."
                })

        return {
            "issues": issues[:25],
            "cleaning_steps": self._dedupe_steps(steps)[:25],
            "validation_checks": self._default_validation_checks()
        }

    def _default_validation_checks(self):
        return [
            "Check that all date columns are in a consistent YYYY-MM-DD format.",
            "Check that all categorical text columns have standardised casing.",
            "Check that missing values in numeric columns are filled with the median.",
            "Check that missing values in categorical columns are filled with the mode.",
            "Check that there are no duplicate rows.",
            "Check that no placeholder values (ERROR, UNKNOWN, N/A, NULL, ?) remain.",
            "Check that numeric columns have the correct dtype after casting.",
        ]

    def _dedupe_steps(self, steps):
        seen = set()
        out = []
        for step in steps:
            key = (step["action"], step["column"])
            if key not in seen:
                out.append(step)
                seen.add(key)
        return out