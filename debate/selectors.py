from django.db.models import Q
from django.contrib.auth.models import User

from debate.models import Debate, Round, MatchQueue
from debate.constants import MatchQueueStatus


def get_active_topics():
    from debate.models import Topic
    return Topic.objects.filter(is_active=True).order_by('-created_at')


def get_debate(*, debate_id: int) -> Debate:
    return Debate.objects.select_related('topic', 'user_pro', 'user_con', 'winner').get(id=debate_id)


def get_user_debates(*, user: User):
    return (
        Debate.objects
        .filter(Q(user_pro=user) | Q(user_con=user))
        .select_related('topic', 'user_pro', 'user_con', 'winner')
        .order_by('-started_at')
    )


def get_current_round(*, debate: Debate) -> Round | None:
    return Round.objects.filter(debate=debate, ended_at__isnull=True).order_by('order').first()


def get_active_queue_entry(*, user: User) -> MatchQueue | None:
    return MatchQueue.objects.filter(user=user, status=MatchQueueStatus.PENDING).first()


def get_pending_match_for_topic(*, topic_id: int, exclude_user: User, pro_or_con: str) -> MatchQueue | None:
    return (
        MatchQueue.objects
        .select_for_update()
        .filter(topic_id=topic_id, status=MatchQueueStatus.PENDING)
        .exclude(user=exclude_user, pro_or_con=pro_or_con)
        .first()
    )


def get_latest_queue_entry(*, user: User) -> MatchQueue | None:
    return (
        MatchQueue.objects
        .filter(user=user, status__in=[MatchQueueStatus.PENDING, MatchQueueStatus.MATCHED])
        .select_related('topic', 'debate')
        .order_by('-joined_at')
        .first()
    )
