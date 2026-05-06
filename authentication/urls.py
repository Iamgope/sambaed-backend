from django.urls import path
from authentication.views import GoogleLogin, GoogleLoginCallback, TokenRefreshView

urlpatterns = [
    path("oauth/google/", GoogleLogin.as_view(), name="google_login"),
    path("oauth/google/callback/", GoogleLoginCallback.as_view(), name="google_login_callback"),
    path("token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
]
