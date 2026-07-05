from django.urls import path
from users.views import (
    DeviceRegistrationView,
    FeedbackView,
    GetUserProfileView,
    TopicCommentView,
)

urlpatterns = [
    path("getProfile/", GetUserProfileView.as_view(), name="get-user-profile"),
    path("feedback/", FeedbackView.as_view(), name="feedback"),
    path("devices/register/", DeviceRegistrationView.as_view(), name="device-register"),
    path("topics/comments/", TopicCommentView.as_view(), name="topic-comment"),
]
