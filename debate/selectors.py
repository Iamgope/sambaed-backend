from __future__ import annotations

from datetime import datetime
from time import timezone
from typing import Optional

from django.db.models import Q, QuerySet
from django.contrib.auth.models import User

from debate.models import Debate, DebateViewer, Judgement, MatchQueue, Message, Round, Topic
from debate.constants import DebateStatus, DebateViewerStatus, MatchQueueStatus, ProOrCon, RoundType


# ── Topics & debates (read) ──────────────────────────────────────────────

def get_active_topics() -> QuerySet[Topic]:
    return Topic.objects.select_related("category").filter(is_active=True).order_by("priority")


def get_debate(*, debate_id: int) -> Debate:
    return Debate.objects.select_related("topic", "user_pro", "user_con", "winner").get(id=debate_id)


def get_user_debates(*, user: User) -> QuerySet[Debate]:
    return (
        Debate.objects.filter(Q(user_pro=user) | Q(user_con=user))
        .select_related("topic", "user_pro", "user_con", "winner")
        .order_by("-started_at")
    )


def get_debate_by_id(*, debate_id: int) -> Debate | None:
    return (
        Debate.objects.select_related("topic", "user_pro", "user_con", "winner")
        .filter(id=debate_id)
        .first()
    )


def get_debate_for_serializer(*, debate_id: int) -> Debate:
    return Debate.objects.select_related("topic", "user_pro", "user_con", "winner").get(
        id=debate_id
    )


# ── Rounds & messages (read) ─────────────────────────────────────────────

def get_current_round(*, debate: Debate) -> Round | None:
    return Round.objects.filter(debate=debate, ended_at__isnull=True).order_by("order").first()


def get_messages_for_round(*, round_obj: Round) -> QuerySet[Message]:
    return Message.objects.filter(round=round_obj)


def get_rounds_for_debate_ordered(*, debate: Debate) -> QuerySet[Round]:
    return Round.objects.filter(debate=debate).order_by("order")


def get_messages_for_debate_round_ordered(*, round_obj: Round) -> QuerySet[Message]:
    return Message.objects.filter(round=round_obj).order_by("created_at")


# ── Match queue (read) ──────────────────────────────────────────────────

def get_active_queue_entry(*, user: User) -> MatchQueue | None:
    return MatchQueue.objects.filter(user=user, status=MatchQueueStatus.PENDING).first()


def get_pending_match_for_topic(
    *, topic_id: int, exclude_user: User, pro_or_con: ProOrCon
) -> MatchQueue | None:
    return (
        MatchQueue.objects.select_for_update()
        .filter(topic_id=topic_id, status=MatchQueueStatus.PENDING)
        .exclude(user=exclude_user, pro_or_con=pro_or_con)
        .first()
    )


def get_latest_queue_entry(*, user: User) -> MatchQueue | None:
    return (
        MatchQueue.objects.filter(
            user=user, status__in=[MatchQueueStatus.PENDING, MatchQueueStatus.MATCHED]
        )
        .select_related("topic", "debate")
        .order_by("-joined_at")
        .first()
    )


# ── Match queue (write) ────────────────────────────────────────────────

def get_topic_by_id(*, topic_id: int) -> Topic | None:
    return Topic.objects.filter(id=topic_id, is_active=True).first()


def get_topic_by_id_or_category_id(
    *, topic_id: Optional[int], category_id: Optional[int]
) -> Optional[Topic]:
    if topic_id:
        return get_topic_by_id(topic_id=topic_id)
    if category_id is None:
        return None
    return Topic.objects.filter(category_id=category_id, is_active=True).order_by("?").first()


def create_match_queue_entry(
    *, user: User, topic: Topic, pro_or_con: ProOrCon, status: MatchQueueStatus
) -> MatchQueue:
    return MatchQueue.objects.create(
        user=user,
        topic=topic,
        pro_or_con=pro_or_con,
        status=status,
    )


def set_match_queue_entry_status(*, entry: MatchQueue, status: MatchQueueStatus) -> None:
    entry.status = status
    entry.save(update_fields=["status"])


def create_debate_for_queue_match(
    *,
    topic: Topic,
    user: User,
    opponent_entry: MatchQueue,
    user_pro: User,
    user_con: User,
    pro_or_con_for_joiner: ProOrCon,
    matched_at: datetime,
) -> MatchQueue:
    """Creates Debate, opening round, updates opponent entry, and joiner's match-queue row."""
    debate = Debate.objects.create(
        topic=topic,
        user_pro=user_pro,
        user_con=user_con,
        status=DebateStatus.ONGOING,
    )
    Round.objects.create(
        debate=debate,
        round_type=RoundType.OPENING,
        order=1,
        started_at=matched_at,
    )
    opponent_entry.status = MatchQueueStatus.MATCHED
    opponent_entry.matched = True
    opponent_entry.matched_at = matched_at
    opponent_entry.debate = debate
    opponent_entry.save(update_fields=["status", "matched", "matched_at", "debate"])
    return MatchQueue.objects.create(
        user=user,
        topic=topic,
        pro_or_con=pro_or_con_for_joiner,
        status=MatchQueueStatus.MATCHED,
        matched=True,
        matched_at=matched_at,
        debate=debate,
    )


# ── Messages & rounds (write) ───────────────────────────────────────────

def create_message_in_round(
    *, debate: Debate, round_obj: Round, user: User, content: str
) -> Message:
    return Message.objects.create(
        debate=debate,
        round=round_obj,
        user=user,
        content=content,
    )


def mark_round_ended(*, round_obj: Round, ended_at: datetime) -> None:
    round_obj.ended_at = ended_at
    round_obj.save(update_fields=["ended_at"])


def create_next_round(
    *, debate: Debate, round_type: RoundType, order: int, started_at: datetime
) -> Round:
    return Round.objects.create(
        debate=debate,
        round_type=round_type,
        order=order,
        started_at=started_at,
    )


# ── Judgements (write) ────────────────────────────────────────────────

def apply_judgement_outcome(*, debate: Debate, data: dict) -> Judgement:
    from django.utils import timezone

    Judgement.objects.filter(debate=debate).delete()
    winner_user = debate.user_pro if data["winner"] == "pro" else debate.user_con
    judgement = Judgement.objects.create(
        debate=debate,
        winner=winner_user,
        argument_score_pro=data["pro"]["argument_score"],
        rebuttal_score_pro=data["pro"]["rebuttal_score"],
        clarity_score_pro=data["pro"]["clarity_score"],
        persuasion_score_pro=data["pro"]["persuasion_score"],
        argument_score_con=data["con"]["argument_score"],
        rebuttal_score_con=data["con"]["rebuttal_score"],
        clarity_score_con=data["con"]["clarity_score"],
        persuasion_score_con=data["con"]["persuasion_score"],
        reasoning=data["reasoning"],
        strongest_moment=data["strongest_moment"],
        coaching_tip_pro=data["coaching_tip_pro"],
        coaching_tip_con=data["coaching_tip_con"],
    )
    debate.status = DebateStatus.COMPLETED
    debate.winner = winner_user
    debate.completed_at = timezone.now()
    debate.save(update_fields=["status", "winner", "completed_at"])
    return judgement


def set_debate_status(*, debate: Debate, status: DebateStatus) -> None:
    debate.status = status
    debate.save(update_fields=["status"])


def update_debate_status(*, debate_id: int, status: DebateStatus) -> None:
    Debate.objects.filter(id=debate_id).update(status=status)


def update_match_queue_status(
    *, user_id: int, status: MatchQueueStatus, debate_id: int
) -> None:
    MatchQueue.objects.filter(user_id=user_id, status=status, debate_id=debate_id).update(
        status=status
    )

def get_debates_by_status(*, status: DebateStatus) -> QuerySet[Debate]:
    return (
        Debate.objects.select_related("topic", "user_pro", "user_con", "winner")
        .filter(status=status)
        .order_by("-started_at")
    )

def get_messages_for_debate_and_user(*, debate_id: int, user_id: int) -> QuerySet[Message]:
    return (
        Message.objects
        .filter(debate_id=debate_id, user_id=user_id)
        .select_related('user', 'round')
        .order_by('created_at')
    )


def get_or_create_debate_viewer(*, user: User, debate_id: int, status: DebateViewerStatus) -> DebateViewer:
    return DebateViewer.objects.get_or_create(
        user=user,
        debate_id=debate_id,
        status=status,
    )