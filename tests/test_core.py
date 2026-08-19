import pytest

from core import safe_calculate, route


def test_safe_calculate_basic():
    assert safe_calculate("250*4+100") == 1100


def test_safe_calculate_power_limit():
    with pytest.raises(ValueError):
        safe_calculate("2^101")


def test_safe_calculate_rejects_code():
    with pytest.raises((ValueError, SyntaxError)):
        safe_calculate("__import__('os').system('echo bad')")


@pytest.mark.asyncio
async def test_router_search_and_writing():
    result = await route("ابحث عن آخر أخبار اليمن")
    assert "SEARCH" in result.kinds

    result = await route("اكتب إعلاناً لمحلي")
    assert "WRITING" in result.kinds
