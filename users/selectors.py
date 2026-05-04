from typing import List
from users.models import UserDevice, UserProfile


def get_user_profile(*, user_id: int) -> UserProfile:
    return UserProfile.objects.get(user_id=user_id)


def get_active_user_devices(*, user_id: int) -> list[UserDevice]:
    return list(UserDevice.objects.filter(user_id=user_id, is_active=True))


def update_user_device_status(*, pk_ids: List[int], is_active: bool) -> None:
    UserDevice.objects.filter(id__in=pk_ids).update(is_active=is_active)
