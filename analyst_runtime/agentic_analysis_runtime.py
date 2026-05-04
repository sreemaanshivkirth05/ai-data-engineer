from __future__ import annotations

from typing import Dict, Any, List, Optional

from analyst_runtime.analysis_pipeline import run_analysis_pipeline


def run_agentic_analysis_pipeline(
    dataset_path: str,
    question: str,
    question_history: Optional[List[str]] = None,
) -> Dict[str, Any]:
    question_history = question_history or []

    return run_analysis_pipeline(
        dataset_path=dataset_path,
        question=question,
        question_history=question_history,
    )