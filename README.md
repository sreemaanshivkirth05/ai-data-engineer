# AI Data Engineer 2.0

**An interactive workspace for data quality, analysis, and architecture design.**

This is an upgrade of an existing FastAPI / Jinja application. The interface provides interconnected Data Cleaner, Analysis, and Architecture workspaces with a shared-session dataset workflow. The cleaner uses deterministic safeguards even when an LLM proposes transformations.

## What currently works

| Workspace | Functionality |
| --- | --- |
| Data Cleaner | Upload, profile, propose cleaning steps, review decisions, validate results, compare previews and download outputs |
| Data Analysis | Ask dataset questions, generate insights and view reports through the existing analytics runtime |
| Data Architecture | Request data architecture recommendations and view architecture reports |
| Shared dataset | Pass the active file between workspaces within the current browser session |

The Data Quality Studio assesses likely identifiers, ambiguous dates, booleans, email formats, blank text, numeric values and missing fields. It preserves original data when an operation requires review. **The review screen is informational: manual approval execution is not yet available.**

## Quick start

Requires Python 3.11 and optional Ollama for locally hosted planning.

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
```

For local LLM planning:

```bash
ollama pull qwen2.5:3b
ollama serve
```

In a separate terminal:

```bash
uvicorn app:app --reload
```

Open http://127.0.0.1:8000. Without Ollama, set `MODEL_PROVIDER=deterministic` to run the cleaner's rules-based planner. With the default `MODEL_PROVIDER=ollama`, unavailable local inference falls back to deterministic planning.

For explicit Hugging Face planning, set `MODEL_PROVIDER=huggingface` and `HF_TOKEN`. That option sends sanitized column metadata to the selected remote provider. Other legacy agents may still have separate model dependencies.

## Supported data input

The shared data loader supports CSV, TSV, XLSX, JSON, JSONL/NDJSON and Parquet; legacy XLS compatibility may require an additional reader. CSV and TSV explicitly preserve identifier-like text fields and literal placeholder strings such as `NULL` until policy-approved changes are made. The cleaning workflow writes the cleaned file in the source format where a writer is supported, otherwise CSV.

## Validation

```bash
python -m compileall -q app.py agents engineer_runtime analyst_runtime architect_runtime
python -m unittest discover -s tests -p 'test_*.py'
```

GitHub Actions runs these checks for the upgrade branch and pull requests. The integration suite exercises UI rendering, secure download routing, parser behavior and no-key deterministic cleaning.

## Safe handling

- Source values are not silently overwritten when cleaning steps are deferred.
- Identifier-like fields are protected from automatic modification.
- Public static output serving is restricted to visualization assets; raw cleaned files use a session-scoped download endpoint.
- Production mode requires `SESSION_SECRET_KEY`; enable HTTPS in deployment.
- Raw samples may contain sensitive information. Use synthetic or suitably sanitized datasets for public demonstrations.

## Current limitations

This is a portfolio-oriented work in progress, **not yet production-ready or multi-tenant secure**. The cleaning approval workflow does not yet execute human-approved changes; some upstream analysis/architecture agents still depend on older model-client implementations. Comprehensive browser visual testing, performance profiling, dependency pinning, and cleanup of previously tracked generated files remain outstanding. Avoid deploying it with private datasets until a fuller security audit is complete.
