from celery import shared_task

from users.firebase import send_push_notifications_to_user

@shared_task
def send_push_notification(*, user_id: int, title: str, body: str, data: dict | None = None) -> None:
    send_push_notifications_to_user(user_id=user_id, title=title, body=body, data=data)
