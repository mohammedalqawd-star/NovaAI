from dataclasses import dataclass
from core import route


@dataclass(frozen=True)
class Plan:
    steps: list[str]
    intents: list[str]


async def make_plan(text: str) -> Plan:
    """Create a deterministic, safe execution plan from the user's intent.

    The planner only selects known internal capabilities; it never executes
    arbitrary code or accepts tool names from model output.
    """
    intent = await route(text)
    kinds = list(dict.fromkeys(intent.kinds))
    steps: list[str] = []

    if "SEARCH" in kinds or "NEWS" in kinds:
        steps.append("search")
    if "CALCULATOR" in kinds:
        steps.append("calculate")
    if "FILE_ANALYSIS" in kinds:
        steps.append("file_analysis")
    if "IMAGE_ANALYSIS" in kinds:
        steps.append("vision")
    if "VOICE" in kinds:
        steps.append("speech")
    if "TRANSLATION" in kinds:
        steps.append("translate")
    if not steps:
        steps.append("generate")
    elif "generate" not in steps:
        steps.append("generate")
    steps.append("verify")
    return Plan(steps=steps, intents=kinds)
