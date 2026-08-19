"""Per-stage audit reporting, shared by every pipeline module.

Every stage of the change-detection pipeline (preprocessing, detection,
discrimination, postprocessing) must report exactly what it did — no stage
is allowed to silently drop a detected change or apply a filter without
recording it. `run_step` is the single place that timestamps a stage and
wraps its output in a `StepReport`; pipeline modules should not construct
`StepReport` by hand outside of this helper.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass
class StepReport:
    step_name: str
    description: str
    duration_ms: float
    details: dict[str, Any] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "step_name": self.step_name,
            "description": self.description,
            "duration_ms": round(self.duration_ms, 2),
            "details": self.details,
            "warnings": self.warnings,
        }


def run_step(
    step_name: str,
    description: str,
    fn: Callable[[], tuple[Any, dict[str, Any], list[str]]],
) -> tuple[Any, StepReport]:
    """Run `fn`, timing it and wrapping its (result, details, warnings) in a StepReport.

    `fn` takes no arguments (callers close over their inputs) and must return
    (result, details, warnings) — this mirrors AutoClean AI's pipeline audit
    contract so every stage is independently inspectable.
    """
    start = time.perf_counter()
    result, details, warnings = fn()
    duration_ms = (time.perf_counter() - start) * 1000
    report = StepReport(
        step_name=step_name,
        description=description,
        duration_ms=duration_ms,
        details=details,
        warnings=warnings,
    )
    return result, report
