from django.urls import path
from users.views import GetUserProfileView

urlpatterns = [
    path('getProfile/', GetUserProfileView.as_view(), name='get-user-profile'),
]
