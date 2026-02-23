from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pathlib import Path

from llm.openai_client import OpenAIClient

app = FastAPI()

BASE_DIR = Path(__file__).resolve().parent

# Mount static files
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")

# Templates
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))


def read_file(path: str) -> str:
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def run_all_agents(requirements: str, schemas: str):
    llm = OpenAIClient()

    # Load shared system rules
    system_rules = read_file("system/SYSTEM.md")

    # ===== Agent 1: Requirements Interpreter =====
    req_agent = read_file("agents/requirements_interpreter.txt")
    skill_pipeline = read_file("skills/good_pipeline_design.md")
    skill_model = read_file("skills/good_data_model.md")

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
    architecture = llm.generate(prompt_1)

    # ===== Agent 2: Pipeline Architect =====
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
    pipeline_design = llm.generate(prompt_2)

    # ===== Agent 3: Data Modeler =====
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
    data_model = llm.generate(prompt_3)

    # ===== Agent 4: Data Quality Engineer =====
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
    data_quality = llm.generate(prompt_4)

    # ===== Agent 5: Performance & Cost Optimizer =====
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
{data_quality}

TASK:
Review the system and propose performance and cost optimizations as instructed.
"""
    performance = llm.generate(prompt_5)

    return {
        "architecture": architecture,
        "pipeline": pipeline_design,
        "data_model": data_model,
        "data_quality": data_quality,
        "performance": performance,
    }


@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.post("/run", response_class=HTMLResponse)
def run(request: Request, requirements: str = Form(...), schemas: str = Form(...)):
    results = run_all_agents(requirements, schemas)

    return templates.TemplateResponse(
        "results.html",
        {
            "request": request,
            "architecture": results["architecture"],
            "pipeline": results["pipeline"],
            "data_model": results["data_model"],
            "data_quality": results["data_quality"],
            "performance": results["performance"],
        },
    )