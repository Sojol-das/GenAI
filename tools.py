import os
import re
import requests
from dotenv import load_dotenv

load_dotenv()

_SERPER_KEY = os.getenv("SERPER_API_KEY", "")
_SERPER_URL = "https://google.serper.dev/search"
_HEADERS_JSON = {"X-API-KEY": _SERPER_KEY, "Content-Type": "application/json"}


def web_search(query: str, num_results: int = 5) -> str:
    """Search the web via Serper and return a compact result string."""
    if not _SERPER_KEY:
        return "[ERROR] SERPER_API_KEY not set in .env"
    try:
        resp = requests.post(
            _SERPER_URL,
            headers=_HEADERS_JSON,
            json={"q": query, "num": num_results},
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        return f"[ERROR] web_search failed: {e}"

    lines = []
    for item in data.get("organic", [])[:num_results]:
        title = item.get("title", "")
        link = item.get("link", "")
        snippet = item.get("snippet", "")
        lines.append(f"- {title}\n  {link}\n  {snippet}")

    answer_box = data.get("answerBox", {}).get("answer") or data.get("answerBox", {}).get("snippet")
    if answer_box:
        lines.insert(0, f"[Answer box] {answer_box}\n")

    return "\n\n".join(lines) if lines else "No results found."


def fetch_page(url: str, max_chars: int = 4000) -> str:
    """Fetch a URL and return cleaned plain text (no HTML tags)."""
    try:
        resp = requests.get(
            url,
            headers={"User-Agent": "Mozilla/5.0 (research-agent/1.0)"},
            timeout=12,
        )
        resp.raise_for_status()
        text = resp.text
    except Exception as e:
        return f"[ERROR] fetch_page failed: {e}"

    # Strip script/style blocks
    text = re.sub(r"<(script|style)[^>]*>.*?</(script|style)>", " ", text, flags=re.DOTALL | re.IGNORECASE)
    # Strip all remaining HTML tags
    text = re.sub(r"<[^>]+>", " ", text)
    # Collapse whitespace
    text = re.sub(r"\s+", " ", text).strip()

    return text[:max_chars] + ("…[truncated]" if len(text) > max_chars else "")


def search_arxiv(query: str, max_results: int = 5) -> str:
    """Search arXiv for academic papers matching a query."""
    try:
        resp = requests.get(
            "https://export.arxiv.org/api/query",
            params={
                "search_query": f"all:{query}",
                "start": 0,
                "max_results": max_results,
                "sortBy": "relevance",
            },
            timeout=12,
        )
        resp.raise_for_status()
        xml = resp.text
    except Exception as e:
        return f"[ERROR] search_arxiv failed: {e}"

    # Parse titles, authors, summaries, and links from Atom XML
    entries = re.findall(r"<entry>(.*?)</entry>", xml, re.DOTALL)
    if not entries:
        return "No papers found."

    lines = []
    for entry in entries[:max_results]:
        title = re.search(r"<title>(.*?)</title>", entry, re.DOTALL)
        summary = re.search(r"<summary>(.*?)</summary>", entry, re.DOTALL)
        link = re.search(r'<id>(.*?)</id>', entry, re.DOTALL)
        title = re.sub(r"\s+", " ", title.group(1)).strip() if title else "Unknown"
        summary = re.sub(r"\s+", " ", summary.group(1)).strip()[:300] if summary else ""
        url = link.group(1).strip() if link else ""
        lines.append(f"- {title}\n  {url}\n  {summary}")

    return "\n\n".join(lines)
