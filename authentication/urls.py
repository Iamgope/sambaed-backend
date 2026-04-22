from django.urls import path
from authentication.views import GoogleLogin, GoogleLoginCallback

urlpatterns = [
    path("oauth/google/", GoogleLogin.as_view(), name="google_login"),
    path("oauth/google/callback/", GoogleLoginCallback.as_view(), name="google_login_callback"),
]
