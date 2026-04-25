from django.urls import path

from debate.views import (
    TopicListView,
    DebateListView,
    DebateDetailView,
    MessageListView,
    JudgementView,
    DisputeView,
)

urlpatterns = [
    path('topics/', TopicListView.as_view(), name='topic-list'),
    path('debates/', DebateListView.as_view(), name='debate-list'),
    path('debates/<int:debate_id>/', DebateDetailView.as_view(), name='debate-detail'),
    path('debates/<int:debate_id>/messages/', MessageListView.as_view(), name='message-list'),
    path('debates/<int:debate_id>/judgement/', JudgementView.as_view(), name='judgement'),
    path('debates/<int:debate_id>/dispute/', DisputeView.as_view(), name='dispute'),
]
