from llm.openai_client import OpenAIClient

def read_file(path):
    with open(path, "r", encoding="utf-8") as f:
        return f.read()

def write_file(path, content):
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)

def main():
    llm = OpenAIClient()

    # ---------- Agent 1: Requirements Interpreter ----------
    system_rules = read_file("system/SYSTEM.md")
    req_agent = read_file("agents/requirements_interpreter.txt")
    skill_pipeline = read_file("skills/good_pipeline_design.md")
    skill_model = read_file("skills/good_data_model.md")
    requirements = read_file("inputs/requirements.md")
    schemas = read_file("inputs/schemas.md")

    prompt_1 = f"""
SYSTEM RULES:
{system_rules}

AGENT ROLE:
{req_agent}

SKILL: GOOD PIPELINE DESIGN:
{skill_pipeline}

SKILL: GOOD DATA MODEL:
{skill_model}

BUSINESS REQUIREMENTS:
{requirements}

SOURCE SCHEMAS:
{schemas}

TASK:
Produce the structured requirements analysis as instructed.
"""

    print("Running Requirements Interpreter agent...")
    architecture = llm.generate(prompt_1)
    write_file("outputs/architecture.md", architecture)
    print("Wrote outputs/architecture.md")

    # ---------- Agent 2: Pipeline Architect ----------
    pipeline_agent = read_file("agents/pipeline_architect.txt")

    prompt_2 = f"""
SYSTEM RULES:
{system_rules}

AGENT ROLE:
{pipeline_agent}

INPUT: REQUIREMENTS ANALYSIS:
{architecture}

TASK:
Design the data pipeline architecture as instructed.
"""

    print("Running Pipeline Architect agent...")
    pipeline_design = llm.generate(prompt_2)
    write_file("outputs/pipeline_design.md", pipeline_design)
    print("Wrote outputs/pipeline_design.md")

    # ---------- Agent 3: Data Modeler ----------
    data_modeler_agent = read_file("agents/data_modeler.txt")

    prompt_3 = f"""
SYSTEM RULES:
{system_rules}

AGENT ROLE:
{data_modeler_agent}

INPUT: PIPELINE DESIGN:
{pipeline_design}

TASK:
Design the analytical data model as instructed.
"""

    print("Running Data Modeler agent...")
    data_model = llm.generate(prompt_3)
    write_file("outputs/data_model.md", data_model)
    print("Wrote outputs/data_model.md")

    # ---------- Agent 4: Data Quality Engineer ----------
    dq_agent = read_file("agents/data_quality_engineer.txt")

    prompt_4 = f"""
SYSTEM RULES:
{system_rules}

AGENT ROLE:
{dq_agent}

INPUT: PIPELINE DESIGN:
{pipeline_design}

INPUT: DATA MODEL:
{data_model}

TASK:
Design the data quality strategy and checks as instructed.
"""

    print("Running Data Quality Engineer agent...")
    dq_plan = llm.generate(prompt_4)
    write_file("outputs/data_quality_plan.md", dq_plan)
    print("Wrote outputs/data_quality_plan.md")


    # ---------- Agent 5: Performance & Cost Optimization ----------
    perf_agent = read_file("agents/performance_cost_optimizer.txt")

    prompt_5 = f"""
SYSTEM RULES:
{system_rules}

AGENT ROLE:
{perf_agent}

INPUT: PIPELINE DESIGN:
{pipeline_design}

INPUT: DATA MODEL:
{data_model}

INPUT: DATA QUALITY PLAN:
{dq_plan}

TASK:
Review the system and propose performance and cost optimizations as instructed.
"""

    print("Running Performance & Cost Optimization agent...")
    perf_review = llm.generate(prompt_5)
    write_file("outputs/performance_review.md", perf_review)
    print("Wrote outputs/performance_review.md")

    # ---------- Agent 6: Documentation Writer ----------
    doc_agent = read_file("agents/documentation_writer.txt")

    prompt_6 = f"""
SYSTEM RULES:
{system_rules}

AGENT ROLE:
{doc_agent}

INPUT: REQUIREMENTS ANALYSIS:
{architecture}

INPUT: PIPELINE DESIGN:
{pipeline_design}

INPUT: DATA MODEL:
{data_model}

INPUT: DATA QUALITY PLAN:
{dq_plan}

INPUT: PERFORMANCE REVIEW:
{perf_review}

TASK:
Generate a complete, professional README-style documentation for this project.
"""

    print("Running Documentation Writer agent...")
    documentation = llm.generate(prompt_6)
    write_file("outputs/README.md", documentation)
    print("Wrote outputs/README.md")

    print("All agents finished successfully.")

if __name__ == "__main__":
    main()