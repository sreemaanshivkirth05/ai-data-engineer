class QuestionAgent:

    def run(self, question):
        q = question.lower()

        intent = "general_analysis"
        show_kpis = False

        if "trend" in q or "over time" in q:
            intent = "trend_analysis"

        elif "compare" in q or "comparison" in q:
            intent = "comparison"
            show_kpis = True

        elif "distribution" in q or "outlier" in q or "histogram" in q:
            intent = "distribution_analysis"

        elif "relationship" in q or "correlation" in q or "impact" in q:
            intent = "relationship_analysis"

        elif "summary" in q or "overview" in q or "dashboard" in q or "kpi" in q or "performance" in q or "report" in q:
            intent = "summary_analysis"
            show_kpis = True

        if any(word in q for word in ["total", "average", "avg", "top", "best", "highest", "lowest"]):
            show_kpis = True

        return {
            "question": question,
            "intent": intent,
            "show_kpis": show_kpis
        }