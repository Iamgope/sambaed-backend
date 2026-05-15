from typing import Dict, Iterable, Optional, Set
from django.contrib.auth.models import User

from users.models import UserProfile


def get_user_by_email(*, email: str) -> Optional[User]:
    return User.objects.filter(email=email).first()


def get_taken_usernames(*, usernames: Iterable[str]) -> Set[str]:
    return set(User.objects.filter(username__in=usernames).values_list("username", flat=True))


def create_user(*, email: str, username: str, extra_data: Dict) -> User:
    return User.objects.create(email=email, username=username, **extra_data)


def create_user_profile(*, user: User) -> UserProfile:
    return UserProfile.objects.get_or_create(user=user)
