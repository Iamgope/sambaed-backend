import logging
import re
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Callable, Dict, List, Optional

import requests
from django.conf import settings

from base.exception import ServiceException
from news.models import TopicNews
from news.selectors import get_topic_news_by_topic_id

logger = logging.getLogger(__name__)

ALLOWED_TIME_FILTERS = {"week", "month", "year", "all"}

# GDELT timespan map. "all" omits the param; GDELT then defaults to ~3 months.
GDELT_TIMESPAN = {"week": "7d", "month": "1m", "year": "1y"}

HTTP_TIMEOUT = 8


def get_topic_news_data_by_topic_id(*, topic_id: Optional[int]) -> TopicNews:
    if not topic_id:
        raise ServiceException("Topic id is required")
    news = get_topic_news_by_topic_id(topic_id=topic_id)
    if not news:
        raise ServiceException(f"No news exists for this topic id")
    return news


# --- Source fetchers. Each returns a list of normalized event dicts or [] on
# missing credentials. Network/parse exceptions bubble up; the orchestrator
# catches and skips the failing source so one bad source can't kill the batch.

def _fetch_reddit_cmv(limit: int, time_filter: str) -> List[Dict]:
    cid = settings.REDDIT_CLIENT_ID
    csec = settings.REDDIT_CLIENT_SECRET
    ua = settings.REDDIT_USER_AGENT
    if not (cid and csec and ua):
        return []

    import praw

    reddit = praw.Reddit(client_id=cid, client_secret=csec, user_agent=ua)
    reddit.read_only = True

    events: List[Dict] = []
    for s in reddit.subreddit("changemyview").top(
        time_filter=time_filter, limit=limit
    ):
        if s.stickied:
            continue
        body = (s.selftext or "").strip()
        if body in ("[removed]", "[deleted]", ""):
            continue
        title = re.sub(r"^\s*CMV\s*[:\-]?\s*", "", s.title, flags=re.I).strip()
        events.append({
            "event": title,
            "context": body[:2000],
            "url": f"https://www.reddit.com{s.permalink}",
            "date": datetime.fromtimestamp(
                s.created_utc, tz=timezone.utc
            ).date().isoformat(),
            "score": int(s.score),
            "source": "reddit_cmv",
        })
    return events


def _fetch_gdelt(limit: int, time_filter: str) -> List[Dict]:
    """GDELT DOC API, India-focused. No key required."""
    params = {
        "query": "sourcecountry:IN",
        "mode": "ArtList",
        "format": "json",
        "maxrecords": min(limit, 250),
        "sort": "DateDesc",
    }
    span = GDELT_TIMESPAN.get(time_filter)
    if span:
        params["timespan"] = span

    r = requests.get(
        "https://api.gdeltproject.org/api/v2/doc/doc",
        params=params,
        timeout=HTTP_TIMEOUT,
    )
    r.raise_for_status()
    payload = r.json() if r.content else {}
    events: List[Dict] = []
    for art in (payload.get("articles") or [])[:limit]:
        seendate = art.get("seendate", "") or ""
        # seendate is YYYYMMDDTHHMMSSZ. Slice to ISO date.
        iso_date = (
            f"{seendate[:4]}-{seendate[4:6]}-{seendate[6:8]}"
            if len(seendate) >= 8 else ""
        )
        events.append({
            "event": (art.get("title") or "").strip(),
            "context": (art.get("domain") or "").strip(),
            "url": art.get("url", ""),
            "date": iso_date,
            "score": 0,
            "source": "gdelt",
        })
    return events


def _fetch_guardian(limit: int, time_filter: str) -> List[Dict]:
    """Guardian Open Platform, India tag. Requires GUARDIAN_API_KEY."""
    key = settings.GUARDIAN_API_KEY
    if not key:
        return []

    params = {
        "api-key": key,
        "tag": "world/india",
        "page-size": min(limit, 50),
        "order-by": "newest",
        "show-fields": "trailText,bodyText",
    }
    r = requests.get(
        "https://content.guardianapis.com/search",
        params=params,
        timeout=HTTP_TIMEOUT,
    )
    r.raise_for_status()
    payload = r.json().get("response", {}) or {}
    events: List[Dict] = []
    for art in (payload.get("results") or [])[:limit]:
        fields = art.get("fields", {}) or {}
        body = fields.get("bodyText") or fields.get("trailText") or ""
        events.append({
            "event": (art.get("webTitle") or "").strip(),
            "context": body[:2000],
            "url": art.get("webUrl", ""),
            "date": (art.get("webPublicationDate") or "")[:10],
            "score": 0,
            "source": "guardian",
        })
    return events


def _fetch_google_news_in(limit: int, time_filter: str) -> List[Dict]:
    """Google News RSS top stories, India locale (en-IN)."""
    r = requests.get(
        "https://news.google.com/rss",
        params={"hl": "en-IN", "gl": "IN", "ceid": "IN:en"},
        headers={"User-Agent": "Mozilla/5.0"},
        timeout=HTTP_TIMEOUT,
    )
    r.raise_for_status()
    root = ET.fromstring(r.content)
    events: List[Dict] = []
    for item in root.findall(".//item")[:limit]:
        title = (item.findtext("title") or "").strip()
        link = (item.findtext("link") or "").strip()
        pub_date = (item.findtext("pubDate") or "").strip()
        try:
            d = parsedate_to_datetime(pub_date).date().isoformat()
        except (TypeError, ValueError):
            d = ""
        description = (item.findtext("description") or "").strip()
        description = re.sub(r"<[^>]+>", " ", description)
        events.append({
            "event": title,
            "context": description[:2000],
            "url": link,
            "date": d,
            "score": 0,
            "source": "google_news_in",
        })
    return events


_SOURCES: Dict[str, Callable[[int, str], List[Dict]]] = {
    "reddit_cmv": _fetch_reddit_cmv,
    "gdelt": _fetch_gdelt,
    "guardian": _fetch_guardian,
    "google_news_in": _fetch_google_news_in,
}


def fetch_world_events(*, limit: int = 50, time_filter: str = "week") -> List[Dict]:
    """Live-fetch events from all configured sources, in parallel.

    `limit` is the per-source cap (not total). Sources with missing creds
    silently return []. Per-source failures are logged and skipped so one
    bad source can't kill the response.
    """
    if time_filter not in ALLOWED_TIME_FILTERS:
        raise ServiceException(
            f"time must be one of {sorted(ALLOWED_TIME_FILTERS)}"
        )
    if not (1 <= limit <= 100):
        raise ServiceException("limit must be between 1 and 100")

    results: List[Dict] = []
    with ThreadPoolExecutor(max_workers=len(_SOURCES)) as ex:
        futures = {
            ex.submit(fn, limit, time_filter): name
            for name, fn in _SOURCES.items()
        }
        for fut in as_completed(futures):
            name = futures[fut]
            try:
                results.extend(fut.result())
            except Exception as e:
                logger.warning("Source %s failed: %s", name, e, exc_info=True)
    return results
