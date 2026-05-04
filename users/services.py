from django.contrib.auth.models import User

from users.models import UserDevice, UserFeedback
from users.selectors import create_user_feedback


def create_feedback(*, user: User, feedback_type: str, title: str, message: str) -> UserFeedback:
    return create_user_feedback(
        user=user,
        feedback_type=feedback_type,
        title=title,
        message=message
    )


def register_device(*, user: User, device_id: str, device_type: str, device_token: str) -> UserDevice:
    device, _ = UserDevice.objects.update_or_create(
        device_id=device_id,
        defaults={
            "user": user,
            "device_type": device_type,
            "device_token": device_token,
            "is_active": True,
        },
    )
    return device
