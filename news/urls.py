from django.urls import path

from news.views import EventListView, PerspectiveListView, TopicNewsListView

urlpatterns = [
    path("topics/<int:topic_id>/", TopicNewsListView.as_view(), name="topic-news-list"),
    path("events/", EventListView.as_view(), name="news-events"),
    path("perspectives/", PerspectiveListView.as_view(), name="news-perspectives"),
]
