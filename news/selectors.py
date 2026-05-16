from typing import Optional

from news.models import Perspective, TopicNews


def get_topic_news_by_topic_id(*, topic_id: int):
    return TopicNews.objects.select_related("topic").filter(topic_id=topic_id).order_by("-id")


def get_latest_perspectives(*, status: Optional[str] = None):
    """Return one Perspective row per source URL — the latest by created_at.

    Uses Postgres DISTINCT ON, which requires ordering by the distinct field
    first. The outer query then re-sorts by created_at DESC for display.
    """
    qs = Perspective.objects.all()
    if status:
        qs = qs.filter(status=status)
    latest_ids = (
        qs.order_by("source_event_url", "-created_at")
        .distinct("source_event_url")
        .values_list("id", flat=True)
    )
    return Perspective.objects.filter(id__in=list(latest_ids)).order_by("-created_at")
