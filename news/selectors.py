from news.models import TopicNews


def get_topic_news_by_topic_id(*, topic_id: int):
    return TopicNews.objects.select_related("topic").filter(topic_id=topic_id).order_by("-id")
