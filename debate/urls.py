from django.urls import path

from debate.views import (
    CategoryAndGroundRule,
    OngoingDebateListView,
    TopicListView,
    DebateListView,
    DebateDetailView,
    MessageListView,
    JudgementView,
    DisputeView,
    MyDebatesListView,
)

urlpatterns = [
    path('topics/', TopicListView.as_view(), name='topic-list'),
    path('getMyDebates/', DebateListView.as_view(), name='debate-list'),
    path('<int:debate_id>/', DebateDetailView.as_view(), name='debate-detail'),
    path('<int:debate_id>/messages/', MessageListView.as_view(), name='message-list'),
    path('<int:debate_id>/judgement/', JudgementView.as_view(), name='judgement'),
    path('<int:debate_id>/dispute/', DisputeView.as_view(), name='dispute'),
    path('ongoingDebates/', OngoingDebateListView.as_view(), name='ongoing-debate-list'),
    path('myDebates/', MyDebatesListView.as_view(), name='my-debate-list'),
    path("getCategoryAndRules/", CategoryAndGroundRule.as_view(), name="category-and-rules"),
]
