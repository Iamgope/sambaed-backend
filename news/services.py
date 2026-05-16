from typing import Dict, Optional

from base.exception import ServiceException
from news.models import TopicNews
from news.selectors import get_topic_news_by_topic_id

def get_topic_news_data_by_topic_id(*, topic_id: Optional[int]) -> TopicNews:
    if not topic_id:
        raise ServiceException("Topic id is required")
    news = get_topic_news_by_topic_id(topic_id=topic_id)
    if not news:
        raise ServiceException(f"No news exists for this topic id")
    return news
