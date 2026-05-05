from typing import List

from django.contrib.auth.models import User
from users.models import ApplicationConfig, UserDevice, UserFeedback, UserProfile


def get_user_profile(*, user_id: int) -> UserProfile:
    return UserProfile.objects.get(user_id=user_id)


def get_active_user_devices(*, user_id: int) -> list[UserDevice]:
    return list(UserDevice.objects.filter(user_id=user_id, is_active=True))


def update_user_device_status(*, pk_ids: List[int], is_active: bool) -> None:
    UserDevice.objects.filter(id__in=pk_ids).update(is_active=is_active)


def get_user_feedbacks(*, user_id: int) -> List[UserFeedback]:
    return list(UserFeedback.objects.filter(user_id=user_id))

def create_user_feedback(*, user: User, feedback_type: str, title: str, message: str) -> UserFeedback:
    return UserFeedback.objects.create(
        user=user,
        feedback_type=feedback_type,
        title=title,
        message=message,
    )


def get_application_config_by_name(*, name: str) -> ApplicationConfig:
    return ApplicationConfig.objects.filter(name=name, is_active=True).first()
