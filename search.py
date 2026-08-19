import html
import re
from urllib.parse import quote_plus
import aiohttp
from config import settings

async def search_web(query: str, limit: int = 6):
    if not settings.search_enabled:
        return []
    results = []
    timeout = aiohttp.ClientTimeout(total=settings.request_timeout)
    async with aiohttp.ClientSession(timeout=timeout, headers={"User-Agent": "NovaBizAI/1.0"}) as session:
        try:
            url = f"https://api.duckduckgo.com/?q={quote_plus(query)}&format=json&no_html=1"
            async with session.get(url) as response:
                if response.status == 200:
                    data = await response.json()
                    if data.get("AbstractText"):
                        results.append({"title": data.get("Heading", "DuckDuckGo"), "snippet": data["AbstractText"], "url": data.get("AbstractURL", "")})
                    for item in data.get("RelatedTopics", []):
                        if isinstance(item, dict) and item.get("Text"):
                            results.append({"title": "DuckDuckGo", "snippet": item["Text"], "url": item.get("FirstURL", "")})
        except Exception:
            pass
        for lang in ("ar", "en"):
            try:
                url = f"https://{lang}.wikipedia.org/w/api.php?action=query&list=search&srsearch={quote_plus(query)}&format=json&srlimit=3"
                async with session.get(url) as response:
                    if response.status == 200:
                        data = await response.json()
                        for item in data.get("query", {}).get("search", []):
                            title = html.unescape(re.sub("<.*?>", "", item.get("title", "")))
                            snippet = html.unescape(re.sub("<.*?>", "", item.get("snippet", "")))
                            results.append({"title": title, "snippet": snippet, "url": f"https://{lang}.wikipedia.org/wiki/{quote_plus(item.get('title', ''))}"})
            except Exception:
                pass
    unique, seen = [], set()
    for result in results:
        key = (result["title"], result["url"])
        if result.get("snippet") and key not in seen:
            seen.add(key)
            unique.append(result)
    return unique[:limit]


def format_sources(results):
    if not results:
        return "لم أجد مصادر كافية للتحقق من هذا الطلب."
    return "\n\n".join(f"[{i}] {r['title']}\n{r['snippet']}\nالمصدر: {r['url']}" for i, r in enumerate(results, 1))
