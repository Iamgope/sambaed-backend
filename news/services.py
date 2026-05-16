import json
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
from news.models import Perspective, TopicNews
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
            "has_context": bool(body and len(body) > 200),
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
            "has_context": False,
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
            "has_context": bool(body and len(body) > 200),
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
            "has_context": False,
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
                logger.warning("Source %s skipped: %s", name, e)
    return results


# --- Perspective generation ---------------------------------------------------

PERSPECTIVE_MODEL = "claude-sonnet-4-6"
PERSPECTIVE_MAX_TOKENS = 700
PERSPECTIVE_TEMPERATURE = 0.3

PERSPECTIVE_SYSTEM_PROMPT = """You brief a reader on why thoughtful people disagree about an event, so they understand the real shape of the disagreement before forming their own view. You are NOT writing arguments to be judged. You are NOT summarizing news. You orient.
Return STRICT JSON only, first char {, last char }, no markdown. Schema:
{"debatable": true|false,
 "drop_reason": "<one sentence; empty if debatable. Drop: pure events with no disagreement; settled-factual questions; topics where everyone has a locked tribal answer and no real reasoning happens>",
 "question": "<one resolved answerable position, 'X should Y', not a theme>",
 "context_2line": "<EXACTLY two sentences, plain factual, zero loaded words, must be side-neutral>",
 "view_1": {"label":"<2-4 words>","view":"<2-3 sentences, the STRONGEST version a real holder of this view would endorse verbatim, not a critic's caricature>"},
 "view_2": {"label":"<2-4 words>","view":"<2-3 sentences, SAME strength and length as view_1>"}}
Non-negotiable: each view must pass the steelman test — its real holders would say 'yes, exactly'. If one view is sharper than the other you have failed; asymmetry must live in the reader's judgement, not your writing. Invent no facts beyond the context given. Output ONLY the JSON."""

PERSPECTIVE_USER_TEMPLATE = "EVENT: {event}\n\nCONTEXT: {context}"

_JSON_FENCE_OPEN = re.compile(r"^```(?:json)?\s*", re.IGNORECASE)
_JSON_FENCE_CLOSE = re.compile(r"\s*```\s*$")


def _strip_json_fences(raw: str) -> str:
    raw = raw.strip()
    raw = _JSON_FENCE_OPEN.sub("", raw)
    raw = _JSON_FENCE_CLOSE.sub("", raw)
    return raw.strip()


def _normalize_title(title: str) -> str:
    return re.sub(r"[^a-z0-9]", "", (title or "").lower())


def generate_perspective(*, event: Dict) -> Dict:
    """Call Anthropic to produce a steelmanned briefing for a single event.

    Returns the parsed JSON dict, or {"_parse_error": True, "_raw": ...} on
    JSON failure. Never raises for the model's output shape.
    """
    if not settings.ANTHROPIC_API_KEY:
        raise ServiceException("ANTHROPIC_API_KEY not configured")

    import anthropic

    client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
    response = client.messages.create(
        model=PERSPECTIVE_MODEL,
        max_tokens=PERSPECTIVE_MAX_TOKENS,
        temperature=PERSPECTIVE_TEMPERATURE,
        system=[{
            "type": "text",
            "text": PERSPECTIVE_SYSTEM_PROMPT,
            "cache_control": {"type": "ephemeral"},
        }],
        messages=[{
            "role": "user",
            "content": PERSPECTIVE_USER_TEMPLATE.format(
                event=event.get("event", ""),
                context=event.get("context", ""),
            ),
        }],
    )

    raw = response.content[0].text if response.content else ""
    cleaned = _strip_json_fences(raw)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        return {"_parse_error": True, "_raw": raw[:500]}


def generate_perspectives_for_events(*, events: List[Dict]) -> Dict:
    """Filter, dedup, generate, and persist perspectives for a batch of events.

    Save policy: every successfully-parsed LLM output is persisted. Debatable
    rows land as `status=pending`; non-debatable rows land as `status=dropped`
    with `drop_reason` preserved. Parse errors are counted but not stored.
    """
    stats = {
        "seen": len(events),
        "skipped_no_context": 0,
        "deduped": 0,
        "generated": 0,
        "dropped_not_debatable": 0,
        "parse_errors": 0,
    }

    with_context: List[Dict] = []
    for e in events:
        if e.get("has_context"):
            with_context.append(e)
        else:
            stats["skipped_no_context"] += 1

    survivors: List[Dict] = []
    seen_titles = set()
    for e in with_context:
        key = _normalize_title(e.get("event", ""))
        if not key or key in seen_titles:
            stats["deduped"] += 1
            continue
        seen_titles.add(key)
        survivors.append(e)

    rows: List[Perspective] = []
    for e in survivors:
        try:
            result = generate_perspective(event=e)
        except Exception as exc:
            stats["parse_errors"] += 1
            logger.warning(
                "generate_perspective failed for %s: %s",
                e.get("url"), exc, exc_info=True,
            )
            continue
        if result.get("_parse_error"):
            stats["parse_errors"] += 1
            logger.warning(
                "Perspective parse error for %s: %s",
                e.get("url"), result.get("_raw"),
            )
            continue

        debatable = bool(result.get("debatable"))
        view_1 = result.get("view_1") or {}
        view_2 = result.get("view_2") or {}
        rows.append(Perspective(
            event_title=(e.get("event") or "").strip(),
            event_context=(e.get("context") or "")[:2000],
            event_source=(e.get("source") or "")[:64],
            event_date=(e.get("date") or "")[:10],
            question=(result.get("question") or "").strip(),
            context_2line=(result.get("context_2line") or "").strip(),
            view_1_label=(view_1.get("label") or "").strip()[:64],
            view_1_text=(view_1.get("view") or "").strip(),
            view_2_label=(view_2.get("label") or "").strip()[:64],
            view_2_text=(view_2.get("view") or "").strip(),
            debatable=debatable,
            drop_reason=(result.get("drop_reason") or "").strip(),
            source_event_url=e.get("url") or "",
            status=Perspective.STATUS_PENDING if debatable
                   else Perspective.STATUS_DROPPED,
        ))
        if debatable:
            stats["generated"] += 1
        else:
            stats["dropped_not_debatable"] += 1

    if rows:
        Perspective.objects.bulk_create(rows)

    return stats
