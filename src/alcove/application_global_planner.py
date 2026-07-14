from __future__ import annotations

from alcove.application_global_ideas import _GlobalIdeaCapabilities
from alcove.application_global_routines import _GlobalRoutineCapabilities
from alcove.application_global_tasks import _GlobalTaskCapabilities


class _GlobalPlannerCapabilities(
    _GlobalTaskCapabilities,
    _GlobalIdeaCapabilities,
    _GlobalRoutineCapabilities,
):
    """Planner payload implementation for the global home capability group."""
