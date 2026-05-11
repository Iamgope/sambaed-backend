from typing import Dict, Tuple
from django.contrib.auth.models import User

from users.models import UserProfile


def get_or_create_user(*, email: str, extra_data: Dict) -> Tuple[User, bool]:
    user, created = User.objects.get_or_create(email=email, defaults=extra_data, username=email)
    return user, created

def create_user_profile(*, user: User) -> UserProfile:
    return UserProfile.objects.get_or_create(user=user)
