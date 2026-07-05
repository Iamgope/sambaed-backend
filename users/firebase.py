import firebase_admin
from firebase_admin import credentials, messaging
from django.conf import settings

from users.selectors import get_active_user_devices, update_user_device_status


def _get_app() -> firebase_admin.App:
    if not firebase_admin._apps:
        cred_path = getattr(settings, "FIREBASE_CREDENTIALS_PATH", "")
        if cred_path:
            firebase_admin.initialize_app(credentials.Certificate(cred_path))
        else:
            firebase_admin.initialize_app()
    return firebase_admin.get_app()


def send_push_notification(
    *, token: str, title: str, body: str, data: dict | None = None
) -> str:
    _get_app()
    message = messaging.Message(
        notification=messaging.Notification(title=title, body=body),
        data={str(k): str(v) for k, v in (data or {}).items()},
        token=token,
    )
    return messaging.send(message)


def send_push_notifications_to_user(
    *, user_id: int, title: str, body: str, data: dict | None = None
) -> None:

    devices = get_active_user_devices(user_id=user_id)
    if not devices:
        return

    _get_app()
    tokens = [d.device_token for d in devices]
    multicast = messaging.MulticastMessage(
        notification=messaging.Notification(title=title, body=body),
        data={str(k): str(v) for k, v in (data or {}).items()},
        tokens=tokens,
    )
    response = messaging.send_each_for_multicast(multicast)

    stale = [devices[i].pk for i, r in enumerate(response.responses) if not r.success]
    if stale:
        update_user_device_status(pk_ids=stale, is_active=False)
