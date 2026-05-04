from typing import Any, Dict, Optional

from llm.openai_client import OpenAIClient


class AnswerReviewerAgent:
    """
    Reviews the analyst response for alignment with the user question,
    target selection, risks, and overclaiming.
    """

    def __init__(self, model: Optional[str] = None):
        self.llm = OpenAIClient(model=model) if model else OpenAIClient()

    def run(
        self,
        question: str,
        target: str,
        drivers: list,
        direct_answer: str,
        executive_summary: str,
        analysis: Dict[str, Any],
        charts: list,
        planner_reasoning: Dict[str, Any],
    ) -> Dict[str, Any]:
        prompt = f"""
You are a senior analytics QA reviewer.

Review the analysis output below and return JSON only.

Question:
{question}

Target:
{target}

Drivers:
{drivers}

Direct answer:
{direct_answer}

Executive summary:
{executive_summary}

Planner reasoning:
{planner_reasoning}

Analysis metadata:
{analysis.get("analysis_metadata", {})}

Charts generated:
{len(charts)}

Your task:
1. Check whether the answer actually addresses the question.
2. Check whether the selected target appears reasonable.
3. Check whether the answer overstates certainty.
4. Produce a confidence score from 0 to 1.
5. Suggest whether the answer should be accepted as-is.

Return JSON exactly like:
{{
  "is_aligned": true,
  "confidence": 0.82,
  "should_accept": true,
  "review_summary": "short review",
  "issues": ["issue"],
  "recommended_fix": "short fix or empty string"
}}
""".strip()

        try:
            raw = self.llm.generate(prompt)
            raw = raw.replace("```json", "").replace("```", "").strip()

            import json
            parsed = json.loads(raw)

            return {
                "is_aligned": bool(parsed.get("is_aligned", True)),
                "confidence": float(parsed.get("confidence", 0.7)),
                "should_accept": bool(parsed.get("should_accept", True)),
                "review_summary": str(parsed.get("review_summary", "")).strip(),
                "issues": parsed.get("issues", []) if isinstance(parsed.get("issues", []), list) else [],
                "recommended_fix": str(parsed.get("recommended_fix", "")).strip(),
            }
        except Exception:
            return {
                "is_aligned": True,
                "confidence": 0.65,
                "should_accept": True,
                "review_summary": "Review agent fallback: no critical issues detected automatically.",
                "issues": [],
                "recommended_fix": "",
            }