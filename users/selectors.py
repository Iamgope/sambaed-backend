from users.models import UserProfile


def get_user_profile(*, user_id: int) -> UserProfile:
    return UserProfile.objects.get(user_id=user_id)
