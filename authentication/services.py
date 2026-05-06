# Standard Library
from typing import Dict, Optional, Tuple


# Local
from authentication.selectors import create_user_profile, get_or_create_user
from authentication.utils.google_authentication import google_oauth

# Third Party
from django.contrib.auth.models import User
from rest_framework_simplejwt.tokens import RefreshToken

from base.exception import ServiceException


def generate_google_login_url():
    return google_oauth.create_google_login_url()


def create_user_by_google_data(*, data: Dict) -> Tuple[User, bool]:
    email = data.pop("email", None)
    if not email:
        raise ServiceException("No email exists")
    user_data = {"first_name": data.pop("given_name", None), "last_name": data.pop("family_name", None)}
    user, is_created = get_or_create_user(email=email, extra_data=user_data)
    if is_created:
        create_user_profile(user=user)
        return user, True
    if not user.is_active:
        raise ServiceException("User is blocked or deleted")

    return user, is_created


def get_jwt_access_token(*, user: User) -> str:
    refresh = RefreshToken.for_user(user)
    return str(refresh.access_token)


def get_user_data_from_google_code(*, code: Optional[str]) -> Dict:
    if not code:
        raise ServiceException('No code provided.')

    access_token = google_oauth.google_get_access_token(code=code)
    if not access_token:
        raise ServiceException('Failed to obtain access token from Google.')

    user_data = google_oauth.google_get_user_info(access_token=access_token)

    return user_data
