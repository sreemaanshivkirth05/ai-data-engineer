import json
from llm.openai_client import OpenAIClient


class PlannerAgent:
    def __init__(self):
        self.llm = OpenAIClient()

    def run(self, question, columns):
        q = question.lower()
        
        prompt = f"""
        You are a Data Analysis Planner representing an expert data analyst.
        The user asked: "{question}"
        The dataset has the following columns: {columns}
        
        Determine the single most appropriate 'target' variable (the primary metric or column to analyze, usually numeric)
        and 'drivers' (a list of other relevant columns that influence or group the target, usually categorical or date).
        
        Return ONLY a JSON object with this shape:
        {{"target": "string", "drivers": ["string", "string"]}}
        """
        
        target = None
        drivers = []
        
        try:
            response = self.llm.generate(prompt)
            # Remove markdown formatting if present
            response = response.replace("```json", "").replace("```", "").strip()
            plan = json.loads(response)
            
            target = plan.get("target")
            drivers = plan.get("drivers", [])
            
            # Validation
            if target not in columns:
                target = None
                
            drivers = [d for d in drivers if d in columns and d != target]
            
        except Exception as e:
            print("PlannerAgent LLM error:", e)
            
        # Fallbacks for safety
        if target is None:
            for col in columns:
                if col.lower() in ["amount", "revenue", "sales"]:
                    target = col
                    break
            if target is None and len(columns) > 0:
                target = columns[-1]
                
        if not drivers:
            drivers = [c for c in columns if c != target]

        return {
            "target": target,
            "drivers": drivers
        }