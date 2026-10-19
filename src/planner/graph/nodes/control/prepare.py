from typing import Any

from planner.graph.state import PlanState
from planner.jurisdictions.registry import REGISTRY
from planner.rules.loader import NoRulePack, resolve


def prepare(state: PlanState) -> dict[str, Any]:
    profile = state.profile
    if not profile.country:
        return {"failure": "country missing"}
    if profile.country not in REGISTRY:
        return {"failure": f"country not supported: {profile.country}"}
    if profile.planning_date is None:
        return {"failure": "planning date missing; the caller must set it"}
    try:
        pack = resolve(profile.country, profile.planning_date)
    except NoRulePack as exc:
        return {"failure": str(exc)}
    return {"jurisdiction": profile.country, "rule_pack": pack.ref}
