import html
import re
import xml.etree.ElementTree as ET
from urllib.parse import quote_plus, quote
import aiohttp
from config import settings


def _add(results, title, snippet, url, source_type="web", published_at=None):
    if title and snippet and url:
        results.append({
            "title": title.strip(),
            "snippet": snippet.strip(),
            "url": url.strip(),
            "source_type": source_type,
            "published_at": published_at,
        })


async def search_web(query: str, limit: int = 8):
    if not settings.search_enabled:
        return []

    results = []
    timeout = aiohttp.ClientTimeout(total=settings.request_timeout)
    headers = {"User-Agent": "NovaBizAI/1.1"}

    async with aiohttp.ClientSession(timeout=timeout, headers=headers) as session:
        # DuckDuckGo instant answers / related results.
        try:
            url = f"https://api.duckduckgo.com/?q={quote_plus(query)}&format=json&no_html=1"
            async with session.get(url) as response:
                if response.status == 200:
                    data = await response.json()
                    _add(results, data.get("Heading", "DuckDuckGo"), data.get("AbstractText", ""), data.get("AbstractURL", ""), "search")
                    for item in data.get("RelatedTopics", []):
                        if isinstance(item, dict):
                            _add(results, "DuckDuckGo", item.get("Text", ""), item.get("FirstURL", ""), "search")
        except Exception:
            pass

        # Google News RSS: useful for recent news without requiring an API key.
        try:
            rss_url = (
                "https://news.google.com/rss/search?q=" + quote_plus(query) +
                "&hl=ar&gl=YE&ceid=YE:ar"
            )
            async with session.get(rss_url) as response:
                if response.status == 200:
                    root = ET.fromstring(await response.text())
                    for item in root.findall("./channel/item")[:5]:
                        title = item.findtext("title", "")
                        link = item.findtext("link", "")
                        published = item.findtext("pubDate", "")
                        description = item.findtext("description", "")
                        snippet = html.unescape(re.sub(r"<[^>]+>", " ", description)).strip() or title
                        _add(results, title, snippet, link, "news", published)
        except Exception:
            pass

        # Wikipedia Arabic + English for reference/background knowledge.
        for lang in ("ar", "en"):
            try:
                url = (
                    f"https://{lang}.wikipedia.org/w/api.php?action=query&list=search"
                    f"&srsearch={quote_plus(query)}&format=json&srlimit=3"
                )
                async with session.get(url) as response:
                    if response.status == 200:
                        data = await response.json()
                        for item in data.get("query", {}).get("search", []):
                            title = html.unescape(re.sub(r"<.*?>", "", item.get("title", "")))
                            snippet = html.unescape(re.sub(r"<.*?>", "", item.get("snippet", "")))
                            wiki_url = f"https://{lang}.wikipedia.org/wiki/{quote(item.get('title', ''), safe='')}"
                            _add(results, title, snippet, wiki_url, "reference")
            except Exception:
                pass

    unique = []
    seen = set()
    for result in results:
        key = result["url"]
        if key not in seen:
            seen.add(key)
            unique.append(result)

    return unique[:limit]


def format_sources(results):
    if not results:
        return "لم أجد مصادر كافية للتحقق من هذا الطلب."
    lines = []
    for i, result in enumerate(results, 1):
        meta = result.get("source_type", "web")
        published = result.get("published_at")
        if published:
            meta += f" | {published}"
        lines.append(
            f"[{i}] {result['title']}\n"
            f"النوع: {meta}\n"
            f"المقتطف: {result['snippet']}\n"
            f"الرابط: {result['url']}"
        )
    return "\n\n".join(lines)
