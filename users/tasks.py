from celery import shared_task

@shared_task
def send_push_notification(*, user_id: int, title: str, body: str, data: dict | None = None) -> None:
    from users.models import UserDevice
    from users.firebase import send_push_notifications_to_user

    devices = UserDevice.objects.filter(user_id=user_id, is_active=True)
    if not devices:
        return

    send_push_notifications_to_user(user_id=user_id, title=title, body=body, data=data)
