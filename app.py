import os
import json
import shutil

from fastapi import FastAPI, UploadFile, File, Form, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from analyst_runtime.analysis_pipeline import run_analysis_pipeline
from engineer_runtime.cleaning_pipeline import run_cleaning_pipeline
from architect_runtime.architecture_pipeline import run_architecture_pipeline
from orchestrator import run_full_pipeline

# ======================================================
# APP SETUP
# ======================================================

app = FastAPI()

templates = Jinja2Templates(directory="templates")

os.makedirs("outputs", exist_ok=True)
os.makedirs("datasets", exist_ok=True)

app.mount("/outputs", StaticFiles(directory="outputs"), name="outputs")

# ======================================================
# HELPERS
# ======================================================

def save_upload_file(upload_file: UploadFile, folder: str = "datasets") -> str:
    os.makedirs(folder, exist_ok=True)
    dataset_path = os.path.join(folder, upload_file.filename)

    with open(dataset_path, "wb") as buffer:
        shutil.copyfileobj(upload_file.file, buffer)

    return dataset_path


# ======================================================
# PAGES
# ======================================================

@app.get("/")
async def home(request: Request):
    return templates.TemplateResponse(
        "index.html",
        {"request": request}
    )


@app.get("/home")
async def home_alt(request: Request):
    return templates.TemplateResponse(
        "home.html",
        {"request": request}
    )


@app.get("/analyst")
async def analyst_page(request: Request):
    return templates.TemplateResponse(
        "analyst.html",
        {"request": request}
    )


@app.get("/engineer")
async def engineer_page(request: Request):
    return templates.TemplateResponse(
        "engineer.html",
        {"request": request, "result": None}
    )


@app.get("/architect")
async def architect_page(request: Request):
    return templates.TemplateResponse(
        "architect.html",
        {"request": request, "result": None}
    )


# ======================================================
# ANALYST ENDPOINT
# ======================================================

@app.post("/analyze")
async def analyze_dataset(
    file: UploadFile = File(...),
    question: str = Form(...),
    question_history: str = Form("[]")
):
    try:
        dataset_path = save_upload_file(file)

        try:
            parsed_history = json.loads(question_history)
            if not isinstance(parsed_history, list):
                parsed_history = []
        except Exception:
            parsed_history = []

        parsed_history = [
            str(item).strip()
            for item in parsed_history
            if str(item).strip()
        ]

        report = run_analysis_pipeline(
            dataset_path=dataset_path,
            question=question,
            question_history=parsed_history
        )

        return JSONResponse(report)

    except Exception as e:
        return JSONResponse(
            {"error": str(e)},
            status_code=500
        )


# ======================================================
# ENGINEER ENDPOINT
# ======================================================

@app.get("/clean")
async def clean_page(request: Request):
    return templates.TemplateResponse(
        "engineer.html",
        {
            "request": request,
            "result": None,
            "business_requirements": ""
        }
    )


@app.post("/clean")
async def clean_dataset(
    request: Request,
    dataset: UploadFile = File(...),
    business_requirements: str = Form("")
):
    try:
        dataset_path = save_upload_file(dataset)

        result = run_cleaning_pipeline(
            dataset_path=dataset_path,
            business_requirements=business_requirements
        )

        return templates.TemplateResponse(
            "engineer.html",
            {
                "request": request,
                "result": result,
                "business_requirements": business_requirements
            }
        )

    except Exception as e:
        print("CLEANING ENDPOINT ERROR:", str(e))
        return templates.TemplateResponse(
            "engineer.html",
            {
                "request": request,
                "result": {
                    "status": "error",
                    "report": {"error": str(e)}
                },
                "business_requirements": business_requirements
            }
        )


# ======================================================
# ARCHITECT ENDPOINT
# ======================================================

@app.post("/design")
async def design_architecture(
    request: Request,
    requirements: str = Form(""),
    schemas: str = Form("")
):
    try:
        result = run_architecture_pipeline(
            requirements_text=requirements,
            schemas_text=schemas
        )

        return templates.TemplateResponse(
            "architect.html",
            {
                "request": request,
                "result": result
            }
        )

    except Exception as e:
        return templates.TemplateResponse(
            "architect.html",
            {
                "request": request,
                "result": {
                    "status": "error",
                    "pipeline_architecture": f"Error: {str(e)}",
                    "security": "",
                    "cost": "",
                    "diagram": ""
                }
            }
        )


# ======================================================
# FULL AI DATA PLATFORM ENDPOINT
# ======================================================

@app.post("/run-full-system")
async def run_full_system(
    file: UploadFile = File(...),
    requirements: str = Form(""),
    schemas: str = Form("")
):
    try:
        dataset_path = save_upload_file(file)

        result = run_full_pipeline(
            dataset_path=dataset_path,
            requirements_text=requirements,
            schemas_text=schemas
        )

        return JSONResponse(result)

    except Exception as e:
        return JSONResponse(
            {"error": str(e)},
            status_code=500
        )