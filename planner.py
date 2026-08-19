from dataclasses import dataclass
from core import route

@dataclass
class Plan:
    steps: list[str]

async def make_plan(text: str) -> Plan:
    intent = await route(text)
    kinds = intent.kinds
    steps = []
    if "SEARCH" in kinds or "NEWS" in kinds:
        steps.append("search")
    if "CALCULATOR" in kinds:
        steps.append("calculate")
    steps.append("generate")
    steps.append("verify")
    return Plan(steps=steps)
