from fastapi import FastAPI, Request, Form, UploadFile, File
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
import subprocess
import os
import sys

app = FastAPI()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TEMPLATES_DIR = os.path.join(BASE_DIR, "templates")
OUTPUTS_DIR = os.path.join(BASE_DIR, "outputs")
UPLOADS_DIR = os.path.join(BASE_DIR, "uploads")
INPUTS_DIR = os.path.join(BASE_DIR, "inputs")

templates = Jinja2Templates(directory=TEMPLATES_DIR)

# Optional static folder (only if you have one)
if os.path.exists(os.path.join(BASE_DIR, "static")):
    app.mount("/static", StaticFiles(directory="static"), name="static")


def read_output(filename: str) -> str:
    path = os.path.join(OUTPUTS_DIR, filename)
    if not os.path.exists(path):
        return "No output generated yet."
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.post("/run")
def run_pipeline(
    request: Request,
    business_requirements: str = Form(...),
    source_schemas: str = Form(...),
    dataset: UploadFile = File(...)
):
    # Create folders if not exist
    os.makedirs(UPLOADS_DIR, exist_ok=True)
    os.makedirs(INPUTS_DIR, exist_ok=True)
    os.makedirs(OUTPUTS_DIR, exist_ok=True)

    # Save uploaded dataset
    dataset_path = os.path.join(UPLOADS_DIR, dataset.filename)
    with open(dataset_path, "wb") as f:
        f.write(dataset.file.read())

    # Save text inputs
    with open(os.path.join(INPUTS_DIR, "requirements.md"), "w", encoding="utf-8") as f:
        f.write(business_requirements)

    with open(os.path.join(INPUTS_DIR, "schemas.md"), "w", encoding="utf-8") as f:
        f.write(source_schemas)

    # Save dataset path (optional, for future agents)
    with open(os.path.join(INPUTS_DIR, "dataset_path.txt"), "w", encoding="utf-8") as f:
        f.write(dataset_path)

    # Run orchestrator
    import sys
    subprocess.run([sys.executable, "orchestrator.py"], check=True)
    return RedirectResponse(url="/results", status_code=303)


@app.get("/results", response_class=HTMLResponse)
def results(request: Request):
    architecture = read_output("architecture.md")
    pipeline = read_output("pipeline_design.md")
    data_model = read_output("data_model.md")
    data_quality = read_output("data_quality_plan.md")
    performance = read_output("performance_review.md")

    return templates.TemplateResponse(
        "results.html",
        {
            "request": request,
            "architecture": architecture,
            "pipeline": pipeline,
            "data_model": data_model,
            "data_quality": data_quality,
            "performance": performance,
        },
    )


@app.get("/history", response_class=HTMLResponse)
def history(request: Request):
    files = []
    if os.path.exists(OUTPUTS_DIR):
        files = os.listdir(OUTPUTS_DIR)
    return templates.TemplateResponse(
        "history.html",
        {"request": request, "files": files}
    )