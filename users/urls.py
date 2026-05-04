from django.urls import path
from users.views import FeedbackView, GetUserProfileView

urlpatterns = [
    path('getProfile/', GetUserProfileView.as_view(), name='get-user-profile'),
    path('feedback/', FeedbackView.as_view(), name='feedback'),
]
