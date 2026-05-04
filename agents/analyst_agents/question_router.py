import re
from typing import Dict, Any


class QuestionRouter:
    """
    Deterministic first-pass router for common analytics question types.
    """

    def __init__(self) -> None:
        self.patterns = {
            "ranking": [
                r"\btop\s+\d+",
                r"\bbottom\s+\d+",
                r"\bhighest\b",
                r"\blowest\b",
                r"\btop\b",
                r"\bbest\b",
                r"\bworst\b",
                r"\brank\b",
            ],
            "trend": [
                r"\btrend\b",
                r"\bover time\b",
                r"\bmonthly\b",
                r"\bweekly\b",
                r"\bdaily\b",
                r"\byearly\b",
                r"\bstrongest month\b",
                r"\bweakest month\b",
                r"\bmonth\b",
                r"\bquarter\b",
                r"\bperiod\b",
            ],
            "comparison": [
                r"\bcompare\b",
                r"\bcomparison\b",
                r"\bversus\b",
                r"\bvs\b",
                r"\bdifference\b",
                r"\bhigher than\b",
                r"\blower than\b",
            ],
            "summary": [
                r"\bsummary\b",
                r"\bexecutive summary\b",
                r"\boverview\b",
                r"\bmain insights\b",
                r"\bimportant kpis\b",
                r"\bkpis\b",
            ],
            "contribution": [
                r"\bcontributes?\b",
                r"\bdrives?\b",
                r"\bshare\b",
                r"\bcontribution\b",
                r"\bportion\b",
            ],
            "distribution": [
                r"\bdistribution\b",
                r"\bspread\b",
                r"\bhow are .* distributed\b",
                r"\bbreakdown\b",
                r"\bcomposition\b",
            ],
        }

    def route(self, question: str) -> Dict[str, Any]:
        q = question.strip().lower()

        scores = {key: 0 for key in self.patterns}
        for intent, patterns in self.patterns.items():
            for pattern in patterns:
                if re.search(pattern, q):
                    scores[intent] += 1

        # priority rules
        if scores["summary"] > 0:
            question_type = "summary"
        elif scores["comparison"] > 0:
            question_type = "comparison"
        elif scores["trend"] > 0:
            question_type = "trend"
        elif scores["ranking"] > 0:
            question_type = "ranking"
        elif scores["contribution"] > 0:
            question_type = "contribution"
        elif scores["distribution"] > 0:
            question_type = "distribution"
        else:
            question_type = "summary"

        show_kpis = question_type in {"summary", "trend", "ranking", "contribution"}

        return {
            "question_type": question_type,
            "show_kpis": show_kpis,
            "router_scores": scores,
        }