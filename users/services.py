from django.contrib.auth.models import User

from users.models import UserFeedback
from users.selectors import create_user_feedback


def create_feedback(*, user: User, feedback_type: str, title: str, message: str) -> UserFeedback:
    return create_user_feedback(
        user=user,
        feedback_type=feedback_type,
        title=title,
        message=message
    )
