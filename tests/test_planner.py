import asyncio

from planner import make_plan


def test_search_plan_is_deterministic():
    async def run():
        plan = await make_plan("ابحث عن آخر أخبار اليمن")
        assert "SEARCH" in plan.intents
        assert plan.steps == ["search", "generate", "verify"]

    asyncio.run(run())
