import logging
from typing import Any, Dict
from urllib.parse import urlencode

import requests
from django.conf import settings

from base.exception import ServiceException

logger = logging.getLogger(__name__)


class GoogleOAuth:
    def __init__(self, google_config: Dict):
        self.client_id = google_config["GOOGLE_OAUTH_CLIENT_ID"]
        self.client_secret = google_config["GOOGLE_OAUTH_CLIENT_SECRET"]
        self.redirect_uri = google_config["GOOGLE_OAUTH_CALLBACK_URL"]
        self.authorization_url = google_config["GOOGLE_AUTHORIZATION_URL"]
        self.access_token_obtain_url = google_config["GOOGLE_ACCESS_TOKEN_OBTAIN_URL"]
        self.user_info_url = google_config["GOOGLE_USER_INFO_URL"]
        self.id_token_info_url = google_config["GOOGLE_ID_TOKEN_INFO_URL"]

    def google_get_user_info_from_id_token(self, id_token: str) -> Dict[str, Any]:
        # Reference: https://developers.google.com/identity/sign-in/web/backend-auth#verify-the-integrity-of-the-id-token
        response = requests.get(self.id_token_info_url, params={"id_token": id_token})

        if not response.ok:
            raise ServiceException("Failed to validate id_token with Google.")

        payload = response.json()

        if payload.get("aud") != self.client_id:
            raise ServiceException("Invalid id_token audience.")

        return payload

    def google_get_access_token(self, code: str) -> str:
        # Reference: https://developers.google.com/identity/protocols/oauth2/web-server#obtainingaccesstokens
        data = {
            "code": code,
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "redirect_uri": self.redirect_uri,
            "grant_type": "authorization_code",
        }

        response = requests.post(self.access_token_obtain_url, data=data)
        logger.info(f"{response.text=}, {response.status_code=}")
        if not response.ok:
            raise ServiceException("Failed to obtain access token from Google.")

        access_token = response.json()["access_token"]

        return access_token

    def google_get_user_info(self, access_token: str) -> Dict[str, Any]:
        # Reference: https://developers.google.com/identity/protocols/oauth2/web-server#callinganapi
        response = requests.get(
            self.user_info_url, params={"access_token": access_token}
        )

        if not response.ok:
            raise Exception("Failed to obtain user info from Google.")

        return response.json()

    def create_google_login_url(self):
        params = {
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "response_type": "code",
            "scope": "openid email profile",
            "prompt": "select_account",
            "access_type": "offline",
        }

        return f"{self.authorization_url}?{urlencode(params)}"


google_oauth = GoogleOAuth(settings.GOOGLE_OAUTH_CONFIG)
