import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class TraceStep:
    name: str
    started_at: float
    finished_at: Optional[float] = None
    status: str = "running"
    details: Dict[str, Any] = field(default_factory=dict)

    def finish(self, status: str = "success", **details):
        self.finished_at = time.time()
        self.status = status
        self.details.update(details)

    def to_dict(self) -> Dict[str, Any]:
        duration_ms = None
        if self.finished_at is not None:
            duration_ms = round((self.finished_at - self.started_at) * 1000, 2)

        return {
            "name": self.name,
            "status": self.status,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "duration_ms": duration_ms,
            "details": self.details,
        }


class PipelineTrace:
    def __init__(self, pipeline_name: str):
        self.pipeline_name = pipeline_name
        self.started_at = time.time()
        self.steps: List[TraceStep] = []

    def start_step(self, name: str) -> TraceStep:
        step = TraceStep(name=name, started_at=time.time())
        self.steps.append(step)
        return step

    def to_dict(self) -> Dict[str, Any]:
        finished_at = time.time()
        total_ms = round((finished_at - self.started_at) * 1000, 2)
        return {
            "pipeline_name": self.pipeline_name,
            "started_at": self.started_at,
            "finished_at": finished_at,
            "total_duration_ms": total_ms,
            "steps": [s.to_dict() for s in self.steps],
        }