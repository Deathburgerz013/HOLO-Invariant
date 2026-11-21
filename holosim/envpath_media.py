"""YouTube search for the local EnvPath media panel."""

from html import unescape
import json
import re
from urllib.parse import urlencode
from urllib.request import Request, urlopen


def search_youtube(query: str, api_key: str) -> list[dict[str, str]]:
    """Return only fields needed by the player. Keep the key server-side."""
    params = urlencode({
        "part": "snippet", "type": "video", "videoEmbeddable": "true",
        "maxResults": 8, "q": query, "key": api_key,
    })
    request = Request("https://www.googleapis.com/youtube/v3/search?" + params)
    with urlopen(request, timeout=8) as response:
        raw = response.read(256 * 1024 + 1)
    if len(raw) > 256 * 1024:
        raise ValueError("YouTube response exceeded its limit.")
    results = []
    for item in json.loads(raw)["items"][:8]:
        video = item["id"]["videoId"]
        if re.fullmatch(r"[A-Za-z0-9_-]{11}", video):
            snippet = item["snippet"]
            results.append({"id": video, "title": unescape(snippet["title"])[:200],
                            "channel": unescape(snippet["channelTitle"])[:100]})
    return results
