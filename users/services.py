from django.contrib.auth.models import User

from users.models import UserDevice, UserFeedback, UserProfile
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


def update_user_profile(*, user_id: int, username: str, bio: str, name: str):
    first, _, last = name.strip().partition(" ")
    User.objects.filter(id=user_id).update(username=username, first_name=first, last_name=last)
    UserProfile.objects.filter(user_id=user_id).update(bio=bio)
