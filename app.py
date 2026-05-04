import os
import json
import uuid
import shutil
from datetime import datetime
from typing import Optional, Dict, Any

from fastapi import FastAPI, UploadFile, File, Form, Request
from fastapi.responses import JSONResponse, RedirectResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

from analyst_runtime.agentic_analysis_runtime import run_agentic_analysis_pipeline
from engineer_runtime.cleaning_pipeline import run_cleaning_pipeline
from architect_runtime.architect_pipeline import run_architect_pipeline
from orchestrator import run_full_pipeline

# ======================================================
# APP SETUP
# ======================================================

app = FastAPI()
app.add_middleware(
    SessionMiddleware,
    secret_key="ai-data-platform-dev-secret-key-change-later",
    same_site="lax",
    https_only=False,
)

templates = Jinja2Templates(directory="templates")

os.makedirs("outputs", exist_ok=True)
os.makedirs("datasets", exist_ok=True)
os.makedirs("outputs/session_state", exist_ok=True)

app.mount("/outputs", StaticFiles(directory="outputs"), name="outputs")

# ======================================================
# CONSTANTS
# ======================================================

SESSION_STATE_DIR = "outputs/session_state"

EMPTY_SHARED_DATASET = {
    "path": None,
    "name": None,
    "source": None,
    "size_kb": None,
    "format": None,
}

EMPTY_SESSION_STATE = {
    "shared_dataset": EMPTY_SHARED_DATASET.copy(),
    "latest_analysis_report": None,
    "latest_architecture_report": None,
    "created_at": None,
    "updated_at": None,
}

# ======================================================
# SESSION / STATE HELPERS
# ======================================================

def ensure_session_id(request: Request) -> str:
    """
    Create or return a stable session id stored in the signed session cookie.
    """
    session_id = request.session.get("session_id")
    if not session_id:
        session_id = str(uuid.uuid4())
        request.session["session_id"] = session_id
    return session_id


def session_state_path(session_id: str) -> str:
    return os.path.join(SESSION_STATE_DIR, f"{session_id}.json")


def load_session_state(request: Request) -> Dict[str, Any]:
    session_id = ensure_session_id(request)
    path = session_state_path(session_id)

    if not os.path.exists(path):
        state = EMPTY_SESSION_STATE.copy()
        state["shared_dataset"] = EMPTY_SHARED_DATASET.copy()
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        state["created_at"] = now
        state["updated_at"] = now
        save_session_state(request, state)
        return state

    try:
        with open(path, "r", encoding="utf-8") as f:
            state = json.load(f)
    except Exception:
        state = EMPTY_SESSION_STATE.copy()
        state["shared_dataset"] = EMPTY_SHARED_DATASET.copy()

    if "shared_dataset" not in state or not isinstance(state["shared_dataset"], dict):
        state["shared_dataset"] = EMPTY_SHARED_DATASET.copy()

    if "latest_analysis_report" not in state:
        state["latest_analysis_report"] = None

    if "latest_architecture_report" not in state:
        state["latest_architecture_report"] = None

    if "created_at" not in state:
        state["created_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    if "updated_at" not in state:
        state["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    return state


def save_session_state(request: Request, state: Dict[str, Any]) -> None:
    session_id = ensure_session_id(request)
    path = session_state_path(session_id)
    state["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def get_current_shared_dataset(request: Request) -> Optional[Dict[str, Any]]:
    state = load_session_state(request)
    dataset = state.get("shared_dataset") or {}
    if dataset.get("path"):
        return dataset
    return None


def set_current_shared_dataset(request: Request, path: str, source: str) -> Dict[str, Any]:
    state = load_session_state(request)
    state["shared_dataset"] = build_dataset_meta(path, source=source)
    save_session_state(request, state)
    return state["shared_dataset"]


def clear_current_shared_dataset(request: Request) -> None:
    state = load_session_state(request)
    state["shared_dataset"] = EMPTY_SHARED_DATASET.copy()
    save_session_state(request, state)


def get_latest_analysis_report(request: Request) -> Optional[Dict[str, Any]]:
    state = load_session_state(request)
    return state.get("latest_analysis_report")


def set_latest_analysis_report(request: Request, report: Dict[str, Any]) -> Dict[str, Any]:
    state = load_session_state(request)
    payload = build_analysis_report_payload(report)
    state["latest_analysis_report"] = payload
    save_session_state(request, state)
    return payload


def get_latest_architecture_report(request: Request) -> Optional[Dict[str, Any]]:
    state = load_session_state(request)
    return state.get("latest_architecture_report")


def set_latest_architecture_report(request: Request, result: Dict[str, Any]) -> Dict[str, Any]:
    state = load_session_state(request)
    payload = build_architecture_report_payload(result)
    state["latest_architecture_report"] = payload
    save_session_state(request, state)
    return payload


# ======================================================
# FILE / DATASET HELPERS
# ======================================================

def save_upload_file(upload_file: UploadFile, folder: str = "datasets") -> str:
    os.makedirs(folder, exist_ok=True)

    filename = os.path.basename(upload_file.filename or "uploaded_file")
    dataset_path = os.path.join(folder, filename)

    with open(dataset_path, "wb") as buffer:
        shutil.copyfileobj(upload_file.file, buffer)

    return dataset_path.replace("\\", "/")


def infer_format_from_path(path: str) -> str:
    ext = os.path.splitext(path)[1].lower()
    mapping = {
        ".csv": "csv",
        ".tsv": "tsv",
        ".xlsx": "excel",
        ".xls": "excel",
        ".json": "json",
        ".jsonl": "jsonl",
        ".ndjson": "ndjson",
        ".parquet": "parquet",
    }
    return mapping.get(ext, ext.replace(".", "") if ext else "unknown")


def build_dataset_meta(path: str, source: str = "manual_upload") -> Dict[str, Any]:
    filename = os.path.basename(path)
    try:
        size_kb = round(os.path.getsize(path) / 1024, 1)
    except Exception:
        size_kb = None

    return {
        "path": path.replace("\\", "/"),
        "name": filename,
        "source": source,
        "size_kb": size_kb,
        "format": infer_format_from_path(path),
    }


def resolve_dataset_for_analysis(
    request: Request,
    uploaded_file: Optional[UploadFile],
    existing_dataset_path: str
) -> Optional[str]:
    dataset_path = None

    if uploaded_file and uploaded_file.filename:
        dataset_path = save_upload_file(upload_file=uploaded_file)
        set_current_shared_dataset(request, dataset_path, source="manual_upload")
        return dataset_path

    if existing_dataset_path:
        normalized = existing_dataset_path.replace("\\", "/")
        if os.path.exists(normalized):
            return normalized

    current = get_current_shared_dataset(request)
    if current and current.get("path") and os.path.exists(current["path"]):
        return current["path"]

    return None


# ======================================================
# REPORT HELPERS
# ======================================================

def safe_str(value, default="N/A"):
    if value is None or value == "":
        return default
    return str(value)


def build_analysis_report_payload(report: Dict[str, Any]) -> Dict[str, Any]:
    dataset = report.get("active_dataset") or report.get("shared_dataset") or {}
    narrative = report.get("narrative") or {}
    story = report.get("story") or {}
    kpis = report.get("kpis") or {}
    quality = report.get("data_quality_summary") or {}
    dataset_summary = report.get("dataset_summary") or {}

    return {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "question": report.get("question", ""),
        "intent": report.get("intent", ""),
        "target": report.get("target", ""),
        "dataset_name": dataset.get("name", "Unknown dataset"),
        "dataset_source": dataset.get("source", "Unknown"),
        "dataset_size_kb": dataset.get("size_kb"),
        "direct_answer": report.get("direct_answer", ""),
        "executive_summary": report.get("executive_summary", ""),
        "question_goal": report.get("question_goal", ""),
        "top_insights": report.get("top_insights", []),
        "business_impact": report.get("business_impact", []),
        "recommended_actions": report.get("recommended_actions", []),
        "risks_or_limitations": report.get("risks_or_limitations", []),
        "follow_up_questions": report.get("follow_up_questions", []),
        "drivers": report.get("drivers", []),
        "aggregation": report.get("aggregation", ""),
        "time_column": report.get("time_column", ""),
        "kpis": kpis,
        "quality": quality,
        "dataset_summary": dataset_summary,
        "narrative_title": narrative.get("title", ""),
        "narrative_summary": narrative.get("summary", ""),
        "narrative_paragraphs": narrative.get("paragraphs", []),
        "story_title": story.get("title", ""),
        "story_headline": story.get("headline", ""),
        "story_points": story.get("key_points", []),
        "story_business_view": story.get("business_view", []),
        "raw_report": report,
    }


def build_architecture_report_payload(result: Dict[str, Any]) -> Dict[str, Any]:
    dataset = result.get("shared_dataset") or {}

    return {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "dataset_name": dataset.get("name", "No shared dataset"),
        "dataset_source": dataset.get("source", "Unknown"),
        "dataset_size_kb": dataset.get("size_kb"),
        "data_contract": result.get("data_contract", ""),
        "pipeline_architecture": result.get("pipeline_architecture", ""),
        "storage": result.get("storage", ""),
        "orchestration": result.get("orchestration", ""),
        "security": result.get("security", ""),
        "cost": result.get("cost", ""),
        "diagram": result.get("diagram", ""),
        "raw_result": result,
    }


def build_analysis_markdown(report: Dict[str, Any]) -> str:
    lines = [
        "# Analysis Report",
        "",
        f"**Generated at:** {safe_str(report.get('generated_at'))}",
        f"**Dataset:** {safe_str(report.get('dataset_name'))}",
        f"**Dataset source:** {safe_str(report.get('dataset_source'))}",
        f"**Question:** {safe_str(report.get('question'))}",
        f"**Intent:** {safe_str(report.get('intent'))}",
        f"**Target:** {safe_str(report.get('target'))}",
        "",
        "## Direct Answer",
        safe_str(report.get("direct_answer"), ""),
        "",
        "## Executive Summary",
        safe_str(report.get("executive_summary"), ""),
        "",
        "## Business Goal",
        safe_str(report.get("question_goal"), ""),
        "",
        "## Top Insights",
    ]

    insights = report.get("top_insights") or []
    if insights:
        for item in insights:
            title = safe_str(item.get("title"), "Insight")
            value = safe_str(item.get("value"), "")
            detail = safe_str(item.get("detail"), "")
            lines.append(f"- **{title}:** {value} — {detail}")
    else:
        lines.append("- No insights available.")

    lines.extend(["", "## KPI Summary"])
    kpis = report.get("kpis") or {}
    if kpis:
        for key, value in kpis.items():
            lines.append(f"- **{key}:** {value}")
    else:
        lines.append("- No KPI data available.")

    lines.extend(["", "## Business Impact"])
    impacts = report.get("business_impact") or []
    if impacts:
        for item in impacts:
            lines.append(f"- {item}")
    else:
        lines.append("- No business impact notes available.")

    lines.extend(["", "## Recommended Actions"])
    actions = report.get("recommended_actions") or []
    if actions:
        for item in actions:
            lines.append(f"- {item}")
    else:
        lines.append("- No recommended actions available.")

    lines.extend(["", "## Risks and Limitations"])
    risks = report.get("risks_or_limitations") or []
    if risks:
        for item in risks:
            lines.append(f"- {item}")
    else:
        lines.append("- No risks or limitations available.")

    lines.extend(["", "## Narrative"])
    lines.append(safe_str(report.get("narrative_summary"), ""))

    for paragraph in report.get("narrative_paragraphs") or []:
        lines.extend(["", paragraph])

    lines.extend(["", "## Story"])
    if report.get("story_headline"):
        lines.append(report["story_headline"])

    for point in report.get("story_points") or []:
        lines.append(f"- {point}")

    for paragraph in report.get("story_business_view") or []:
        lines.extend(["", paragraph])

    lines.extend(["", "## Follow-up Questions"])
    followups = report.get("follow_up_questions") or []
    if followups:
        for item in followups:
            lines.append(f"- {item}")
    else:
        lines.append("- No follow-up questions available.")

    return "\n".join(lines)


def build_architecture_markdown(report: Dict[str, Any]) -> str:
    lines = [
        "# Architecture Report",
        "",
        f"**Generated at:** {safe_str(report.get('generated_at'))}",
        f"**Dataset:** {safe_str(report.get('dataset_name'))}",
        f"**Dataset source:** {safe_str(report.get('dataset_source'))}",
        "",
        "## Data Contract",
        safe_str(report.get("data_contract"), ""),
        "",
        "## Ingestion Strategy",
        safe_str(report.get("pipeline_architecture"), ""),
        "",
        "## Storage Layout",
        safe_str(report.get("storage"), ""),
        "",
        "## Orchestration",
        safe_str(report.get("orchestration"), ""),
        "",
        "## Security and Governance",
        safe_str(report.get("security"), ""),
        "",
        "## Cost Estimation",
        safe_str(report.get("cost"), ""),
        "",
        "## Diagram",
        "```mermaid",
        safe_str(report.get("diagram"), ""),
        "```",
    ]
    return "\n".join(lines)


# ======================================================
# PAGE ROUTES
# ======================================================

@app.get("/")
async def home(request: Request):
    ensure_session_id(request)
    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "shared_dataset": get_current_shared_dataset(request),
        }
    )


@app.get("/home")
async def home_alt(request: Request):
    ensure_session_id(request)
    return templates.TemplateResponse(
        "home.html",
        {
            "request": request,
            "shared_dataset": get_current_shared_dataset(request),
        }
    )


@app.get("/analyst")
async def analyst_page(request: Request):
    ensure_session_id(request)
    shared_dataset = get_current_shared_dataset(request)
    return templates.TemplateResponse(
        "analyst.html",
        {
            "request": request,
            "preloaded_dataset": shared_dataset,
            "shared_dataset": shared_dataset,
        }
    )


@app.get("/engineer")
async def engineer_page(request: Request):
    ensure_session_id(request)
    return templates.TemplateResponse(
        "engineer.html",
        {
            "request": request,
            "result": None,
            "shared_dataset": get_current_shared_dataset(request),
        }
    )


@app.get("/clean")
async def clean_page(request: Request):
    ensure_session_id(request)
    return templates.TemplateResponse(
        "engineer.html",
        {
            "request": request,
            "result": None,
            "business_requirements": "",
            "shared_dataset": get_current_shared_dataset(request),
        }
    )


@app.get("/architect")
async def architect_page(request: Request):
    ensure_session_id(request)
    return templates.TemplateResponse(
        "architect.html",
        {
            "request": request,
            "result": None,
            "shared_dataset": get_current_shared_dataset(request),
        }
    )


@app.get("/analysis-report")
async def analysis_report_page(request: Request):
    ensure_session_id(request)
    report = get_latest_analysis_report(request)
    return templates.TemplateResponse(
        "analysis_report.html",
        {
            "request": request,
            "report": report,
            "shared_dataset": get_current_shared_dataset(request),
        }
    )


@app.get("/architecture-report")
async def architecture_report_page(request: Request):
    ensure_session_id(request)
    report = get_latest_architecture_report(request)
    return templates.TemplateResponse(
        "architecture_report.html",
        {
            "request": request,
            "report": report,
            "shared_dataset": get_current_shared_dataset(request),
        }
    )


# ======================================================
# SHARED DATASET ENDPOINTS
# ======================================================

@app.get("/shared-dataset")
async def shared_dataset_status(request: Request):
    ensure_session_id(request)
    dataset = get_current_shared_dataset(request)
    return JSONResponse({"shared_dataset": dataset})


@app.post("/set-shared-dataset")
async def set_shared_dataset_endpoint(
    request: Request,
    dataset_path: str = Form(...),
    dataset_source: str = Form("manual_set")
):
    ensure_session_id(request)
    normalized = dataset_path.replace("\\", "/")

    if not os.path.exists(normalized):
        return JSONResponse(
            {"error": f"Dataset not found: {normalized}"},
            status_code=400
        )

    shared = set_current_shared_dataset(request, normalized, source=dataset_source)
    return JSONResponse(
        {
            "status": "ok",
            "shared_dataset": shared
        }
    )


@app.post("/clear-shared-dataset")
async def clear_shared_dataset_endpoint(request: Request):
    ensure_session_id(request)
    clear_current_shared_dataset(request)
    return JSONResponse({"status": "cleared"})


@app.post("/use-shared-dataset-for-analysis")
async def use_shared_dataset_for_analysis(request: Request):
    ensure_session_id(request)
    current = get_current_shared_dataset(request)
    if not current or not current.get("path") or not os.path.exists(current["path"]):
        return JSONResponse(
            {"error": "No shared dataset is currently available."},
            status_code=400
        )
    return RedirectResponse(url="/analyst", status_code=303)


@app.post("/use-shared-dataset-for-architecture")
async def use_shared_dataset_for_architecture(request: Request):
    ensure_session_id(request)
    current = get_current_shared_dataset(request)
    if not current or not current.get("path") or not os.path.exists(current["path"]):
        return JSONResponse(
            {"error": "No shared dataset is currently available."},
            status_code=400
        )
    return RedirectResponse(url="/architect", status_code=303)


# ======================================================
# REPORT DOWNLOAD ENDPOINTS
# ======================================================

@app.get("/download-analysis-report")
async def download_analysis_report(request: Request):
    ensure_session_id(request)
    report = get_latest_analysis_report(request)
    if not report:
        return PlainTextResponse("No analysis report available yet.", status_code=404)

    markdown = build_analysis_markdown(report)
    headers = {
        "Content-Disposition": "attachment; filename=analysis_report.md"
    }
    return PlainTextResponse(markdown, headers=headers)


@app.get("/download-architecture-report")
async def download_architecture_report(request: Request):
    ensure_session_id(request)
    report = get_latest_architecture_report(request)
    if not report:
        return PlainTextResponse("No architecture report available yet.", status_code=404)

    markdown = build_architecture_markdown(report)
    headers = {
        "Content-Disposition": "attachment; filename=architecture_report.md"
    }
    return PlainTextResponse(markdown, headers=headers)


# ======================================================
# ANALYSIS ENDPOINTS
# ======================================================

@app.post("/analyze")
async def analyze_dataset(
    request: Request,
    file: Optional[UploadFile] = File(None),
    question: str = Form(...),
    question_history: str = Form("[]"),
    existing_dataset_path: str = Form("")
):
    ensure_session_id(request)

    try:
        dataset_path = resolve_dataset_for_analysis(
            request=request,
            uploaded_file=file,
            existing_dataset_path=existing_dataset_path
        )

        if not dataset_path:
            return JSONResponse(
                {"error": "No dataset available. Please upload a dataset first."},
                status_code=400
            )

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

        report = run_agentic_analysis_pipeline(
            dataset_path=dataset_path,
            question=question,
            question_history=parsed_history
        )

        current_meta = get_current_shared_dataset(request) or build_dataset_meta(
            dataset_path,
            source="manual_upload"
        )

        report["active_dataset"] = current_meta
        report["shared_dataset"] = current_meta

        set_latest_analysis_report(request, report)

        return JSONResponse(report)

    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@app.post("/use-cleaned-for-analysis")
async def use_cleaned_for_analysis(
    request: Request,
    cleaned_file_path: str = Form(...)
):
    ensure_session_id(request)
    normalized = cleaned_file_path.replace("\\", "/")

    if not os.path.exists(normalized):
        return JSONResponse(
            {"error": f"Cleaned dataset not found: {normalized}"},
            status_code=400
        )

    set_current_shared_dataset(request, normalized, source="cleaner_output")
    return RedirectResponse(url="/analyst", status_code=303)


# ======================================================
# CLEANING ENDPOINTS
# ======================================================

@app.post("/clean")
async def clean_dataset(
    request: Request,
    dataset: UploadFile = File(...),
    business_requirements: str = Form("")
):
    ensure_session_id(request)

    try:
        dataset_path = save_upload_file(dataset)
        set_current_shared_dataset(request, dataset_path, source="raw_upload")

        result = run_cleaning_pipeline(
            dataset_path=dataset_path,
            business_requirements=business_requirements
        )

        cleaned_path = result.get("cleaned_file_path")
        if cleaned_path and os.path.exists(cleaned_path):
            set_current_shared_dataset(request, cleaned_path, source="cleaner_output")

        return templates.TemplateResponse(
            "engineer.html",
            {
                "request": request,
                "result": result,
                "business_requirements": business_requirements,
                "shared_dataset": get_current_shared_dataset(request),
            }
        )

    except Exception as e:
        print("CLEANING ENDPOINT ERROR:", str(e))
        return templates.TemplateResponse(
            "engineer.html",
            {
                "request": request,
                "result": {"status": "error", "report": {"error": str(e)}},
                "business_requirements": business_requirements,
                "shared_dataset": get_current_shared_dataset(request),
            }
        )


# ======================================================
# ARCHITECTURE ENDPOINTS
# ======================================================

@app.post("/design")
async def design_architecture(
    request: Request,
    requirements: str = Form(""),
    schemas: str = Form(""),
    dataset: Optional[UploadFile] = File(None),
    existing_dataset_path: str = Form("")
):
    ensure_session_id(request)

    try:
        dataset_profile = {}
        shared_meta = get_current_shared_dataset(request)

        dataset_path = None

        if dataset and dataset.filename:
            dataset_path = save_upload_file(dataset)
            set_current_shared_dataset(request, dataset_path, source="manual_upload_architecture")
        elif existing_dataset_path:
            normalized = existing_dataset_path.replace("\\", "/")
            if os.path.exists(normalized):
                dataset_path = normalized
        elif shared_meta and shared_meta.get("path") and os.path.exists(shared_meta["path"]):
            dataset_path = shared_meta["path"]

        if dataset_path:
            try:
                from agents.engineer_agents.dataset_profiler import DatasetProfilerAgent
                profiler = DatasetProfilerAgent(dataset_path)
                profile_result = profiler.run()
                dataset_profile = profile_result.get("profile", {})
            except Exception as profile_err:
                print(f"Dataset profiling skipped: {profile_err}")

        result = run_architect_pipeline(
            business_requirements=requirements,
            dataset_profile=dataset_profile,
            enable_web_search=True
        )

        result["pipeline_architecture"] = result.get("ingestion_strategy", "")
        result["security"] = result.get("security_governance", "")
        result["cost"] = result.get("cost_estimation", "")
        result["diagram"] = result.get("mermaid_diagram", "")
        result["data_contract"] = result.get("data_contract", "")
        result["storage"] = result.get("storage_layout", "")
        result["orchestration"] = result.get("orchestration", "")
        result["shared_dataset"] = get_current_shared_dataset(request)

        set_latest_architecture_report(request, result)

        return templates.TemplateResponse(
            "architect.html",
            {
                "request": request,
                "result": result,
                "shared_dataset": get_current_shared_dataset(request),
            }
        )

    except Exception as e:
        error_result = {
            "status": "error",
            "pipeline_architecture": f"Error: {str(e)}",
            "security": "",
            "cost": "",
            "diagram": "",
            "data_contract": "",
            "storage": "",
            "orchestration": "",
            "shared_dataset": get_current_shared_dataset(request),
        }

        return templates.TemplateResponse(
            "architect.html",
            {
                "request": request,
                "result": error_result,
                "shared_dataset": get_current_shared_dataset(request),
            }
        )


# ======================================================
# FULL SYSTEM ENDPOINT
# ======================================================

@app.post("/run-full-system")
async def run_full_system(
    request: Request,
    file: UploadFile = File(...),
    requirements: str = Form(""),
    schemas: str = Form(""),
    enable_web_search: bool = Form(True)
):
    ensure_session_id(request)

    try:
        dataset_path = save_upload_file(file)
        set_current_shared_dataset(request, dataset_path, source="full_system_upload")

        result = run_full_pipeline(
            dataset_path=dataset_path,
            requirements_text=requirements,
            schemas_text=schemas,
            enable_web_search=enable_web_search
        )

        result["shared_dataset"] = get_current_shared_dataset(request)
        return JSONResponse(result)

    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


# ======================================================
# OPTIONAL DEBUG ENDPOINT
# ======================================================

@app.get("/session-debug")
async def session_debug(request: Request):
    state = load_session_state(request)
    return JSONResponse({
        "session_id": ensure_session_id(request),
        "state": state,
    })