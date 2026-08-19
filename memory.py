from database import get_memories, set_memory

async def load_memory(user_id: int) -> str:
    rows = await get_memories(user_id)
    if not rows:
        return ""
    return "\n".join(f"- {key}: {value}" for key, value in rows)

async def remember(user_id: int, key: str, value: str) -> None:
    await set_memory(user_id, key[:80], value[:500])
