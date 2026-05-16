from django.urls import path

from news.views import TopicNewsListView

urlpatterns = [
    path("topics/<int:topic_id>/", TopicNewsListView.as_view(), name="topic-news-list"),
]
