from functools import partial
from typing import Dict, List
import random
import logging
from typing import Optional

from django.utils import timezone
from django.db import transaction
from django.contrib.auth.models import User
from django.conf import settings

from base.events import send_queue_matched_event
from base.exception import ServiceException
from debate.constants import DebateStatus, DebateViewerStatus, MatchQueueStatus, ProOrCon, RoundType
from debate.models import Category, Debate, DebateViewer, Judgement, Message, MatchQueue, Round, Topic
from debate import selectors
from debate.serializers import CategorySerializer, DebateListSerializer, TopicSerializer, serialize_messages_of_debate
from debate.tasks import start_judgement_of_debate_and_share_result
from users.constants import ApplicationConfigName
from users.selectors import get_application_config_by_name

logger = logging.getLogger(__name__)

BOT_USERNAME = getattr(settings, "DEBATE_BOT_USERNAME", "vaad_bot")
BOT_QUEUE_WAIT_SECONDS = getattr(settings, "BOT_QUEUE_WAIT_SECONDS", 60)

JUDGE_MODEL_DEFAULT = "claude-haiku-4-5-20251001"
JUDGE_MODEL_ESCALATION = "claude-sonnet-4-6"

ROUND_SEQUENCE = [
    (RoundType.OPENING, 1),
    (RoundType.REBUTTAL, 2),
    (RoundType.CLOSING, 3),
]


# ── Queue / Matchmaking ──────────────────────────────────────────────────────


@transaction.atomic
def join_queue(
    *,
    user: User,
    topic_id: Optional[int],
    category_id: Optional[int],
    pro_or_con: ProOrCon,
) -> MatchQueue:
    topic = selectors.get_topic_by_id_or_category_id(topic_id=topic_id, category_id=category_id)
    if not topic:
        raise ServiceException(message="Topic not found or inactive")

    if selectors.get_active_queue_entry(user=user):
        raise ServiceException(message="You are already in the queue")

    opponent_entry = selectors.get_pending_match_for_topic(
        topic_id=topic.id, exclude_user=user, pro_or_con=pro_or_con
    )
    if opponent_entry:
        return _create_match(
            user=user, opponent_entry=opponent_entry, topic=topic, pro_or_con=pro_or_con
        )

    entry = selectors.create_match_queue_entry(
        user=user, topic=topic, pro_or_con=pro_or_con, status=MatchQueueStatus.PENDING
    )
    # Schedule bot fallback — if no human joins within the wait window, match with bot
    from debate.tasks import assign_bot_if_no_match
    assign_bot_if_no_match.apply_async(args=[entry.id], countdown=BOT_QUEUE_WAIT_SECONDS)
    return entry

@transaction.atomic
def _create_match(
    *, user: User, opponent_entry: MatchQueue, topic: Topic, pro_or_con: ProOrCon
) -> MatchQueue:
    user_pro, user_con = (
        (user, opponent_entry.user)
        if pro_or_con == ProOrCon.PRO
        else (opponent_entry.user, user)
    )
    return selectors.create_debate_for_queue_match(
        topic=topic,
        user=user,
        opponent_entry=opponent_entry,
        user_pro=user_pro,
        user_con=user_con,
        pro_or_con_for_joiner=pro_or_con,
        matched_at=timezone.now(),
    )


def leave_queue(*, user: User) -> None:
    entry = selectors.get_active_queue_entry(user=user)
    if not entry:
        raise ServiceException(message="You are not in the queue")
    selectors.set_match_queue_entry_status(entry=entry, status=MatchQueueStatus.CANCELLED)


# ── Messages / Round progression ────────────────────────────────────────────


def submit_message(*, user: User, debate_id: int, content: str) -> Message:
    debate = selectors.get_debate_by_id(debate_id=debate_id)
    if not debate:
        raise ServiceException(message="Debate not found")

    if debate.status != DebateStatus.ONGOING:
        raise ServiceException(message="This debate is not active")

    if user not in (debate.user_pro, debate.user_con):
        raise ServiceException(message="You are not a participant in this debate")

    current_round = selectors.get_current_round(debate=debate)
    if not current_round:
        raise ServiceException(message="No active round found")

    if not _is_user_turn(
        debate=debate, current_round=current_round, user=user
    ):
        raise ServiceException(message="It is not your turn to submit")

    return selectors.create_message_in_round(
        debate=debate, round_obj=current_round, user=user, content=content
    )


def end_turn(*, user: User, debate_id: int) -> Optional[Round]:
    debate = selectors.get_debate_by_id(debate_id=debate_id)
    if not debate:
        raise ServiceException(message="Debate not found")

    if debate.status != DebateStatus.ONGOING:
        raise ServiceException(message="This debate is not active")

    if user not in (debate.user_pro, debate.user_con):
        raise ServiceException(message="You are not a participant in this debate")

    current_round = selectors.get_current_round(debate=debate)
    if not current_round:
        raise ServiceException(message="No active round found")

    if not _is_user_turn(debate=debate, current_round=current_round, user=user):
        raise ServiceException(message="It is not your turn")

    if not selectors.user_has_message_in_round(round_obj=current_round, user=user):
        raise ServiceException(
            message="You must send at least one message before ending your turn"
        )

    return _advance_after_turn(debate=debate, current_round=current_round, ender=user)


def _is_user_turn(
    *, debate: Debate, current_round: Round, user: User
) -> bool:
    return current_round.current_speaker_id == user.id


def _speaker_order(*, debate: Debate, round_type: RoundType) -> list[User]:
    if round_type == RoundType.CLOSING:
        return [debate.user_con, debate.user_pro]
    return [debate.user_pro, debate.user_con]


def _next_speaker_in_round(*, debate: Debate, current_round: Round) -> Optional[User]:
    order = _speaker_order(debate=debate, round_type=current_round.round_type)
    try:
        idx = next(
            i for i, u in enumerate(order) if u.id == current_round.current_speaker_id
        )
    except StopIteration:
        return None
    return order[idx + 1] if idx + 1 < len(order) else None


def _advance_after_turn(
    *, debate: Debate, current_round: Round, ender: User
) -> Optional[Round]:
    now = timezone.now()
    next_speaker = _next_speaker_in_round(debate=debate, current_round=current_round)
    if next_speaker:
        selectors.set_round_current_speaker(
            round_obj=current_round, speaker=next_speaker, turn_started_at=now
        )
        return None

    selectors.set_round_current_speaker(
        round_obj=current_round, speaker=None, turn_started_at=None
    )
    selectors.mark_round_ended(round_obj=current_round, ended_at=now)

    next_blocks = [
        (rt, order) for rt, order in ROUND_SEQUENCE if order > current_round.order
    ]
    if not next_blocks:
        start_judgement_of_debate_and_share_result.apply_async(
            args=[debate.id, ender.id], countdown=20
        )
        return None
    next_type, next_order = next_blocks[0]
    first_speaker = _speaker_order(debate=debate, round_type=next_type)[0]
    return selectors.create_next_round(
        debate=debate,
        round_type=next_type,
        order=next_order,
        started_at=now,
        current_speaker=first_speaker,
    )


# ── AI Judging ───────────────────────────────────────────────────────────────


def _build_transcript(debate: Debate) -> str:
    lines = [
        f"Topic: {debate.topic.title}",
        f"Pro side: {debate.user_pro.username}",
        f"Con side: {debate.user_con.username}",
        "",
    ]
    for r in selectors.get_rounds_for_debate_ordered(debate=debate):
        lines.append(f"[Round {r.order} — {r.round_type}]")
        for msg in selectors.get_messages_for_debate_round_ordered(round_obj=r):
            side = "Pro" if msg.user == debate.user_pro else "Con"
            lines.append(f"{side}: {msg.content}")
        lines.append("")
    return "\n".join(lines)


def _call_judge(*, debate: Debate) -> dict:
    from debate.utils.claude_client import judge_client

    transcript = _build_transcript(debate=debate)
    config = get_debate_judge_config()
    return judge_client.judge(transcript=transcript, judge_config=config)


def dispute_judgement(*, user: User, debate_id: int) -> Judgement:
    debate = selectors.get_debate_by_id(debate_id=debate_id)
    if not debate:
        raise ServiceException(message="Debate not found")

    if user not in (debate.user_pro, debate.user_con):
        raise ServiceException(message="You are not a participant in this debate")

    if debate.status != DebateStatus.COMPLETED:
        raise ServiceException(message="Can only dispute a completed debate")

    selectors.set_debate_status(debate=debate, status=DebateStatus.DISPUTED)
    try:
        data = _call_judge(debate=debate)
        return selectors.apply_judgement_outcome(debate=debate, data=data)
    except Exception as e:
        logger.error("Dispute judging failed for debate %s: %s", debate.id, e, exc_info=True)
        selectors.set_debate_status(debate=debate, status=DebateStatus.COMPLETED)
        raise ServiceException(
            message="Dispute judging failed, please try again"
        ) from e


def join_queue_outcome(
    *,
    user: User,
    topic_id: Optional[int],
    pro_or_con: ProOrCon,
    category_id: Optional[int],
) -> dict:
    entry = join_queue(
        user=user,
        topic_id=topic_id,
        pro_or_con=pro_or_con,
        category_id=category_id,
    )
    if entry.status == MatchQueueStatus.MATCHED and entry.debate_id:
        debate = selectors.get_debate_by_id(debate_id=entry.debate_id)
        if not debate:
            raise ServiceException(message="Debate not found")
        opponent_id = (
            debate.user_con_id
            if user.id == debate.user_pro_id
            else debate.user_pro_id
        )
        return {
            "outcome": "matched",
            "opponent_id": opponent_id,
            "debate": DebateListSerializer(debate).data,
        }
    return {
        "outcome": "waiting",
        "queue_id": entry.id,
        "topic": TopicSerializer(entry.topic).data,
    }


def get_pro_or_con(*, user: User, pro_or_con: Optional[str]) -> ProOrCon:
    if pro_or_con:
        return ProOrCon(pro_or_con)
    if random.random() < 0.5:
        return ProOrCon.PRO
    return ProOrCon.CON


def group_topics_by_category(*, topics: list[Topic]) -> Dict:
    data = TopicSerializer(topics, many=True).data
    result: Dict = {}
    for topic_data in data:
        category = topic_data["category"]
        category_name = category["name"]
        if category_name not in result:
            result[category_name] = {
                "description": category["description"],
                "background_image": category["background_image"],
                "topics": [],
            }
        result[category_name]["topics"].append(topic_data)
    return result


def create_debate_viewer(*, user: User, debate_id: int) -> DebateViewer:
    debate_viewer, is_created = selectors.get_or_create_debate_viewer(
        user=user, debate_id=debate_id, status=DebateViewerStatus.JOINED
    )
    if not is_created:
        raise ServiceException(message="You are already a viewer of this debate")
    return debate_viewer


def check_and_add_user_reaction(*, user: User, reaction: str, message_id: int, debate_id):
    if not selectors.is_user_debate_viewer(user_id=user.id, debate_id=debate_id):
        raise ServiceException("You are not the viewer for this debate")
    
    return selectors.add_viewer_reaction(user_id=user.id, reaction=reaction, message_id=message_id)


def get_debate_judge_config():
    config = get_application_config_by_name(name=ApplicationConfigName.DEBATE_JUDGE.value)
    return config.properties if config else {}


# ── Bot matchmaking & AI responses ──────────────────────────────────────────


def get_or_create_bot_user() -> User:
    user, created = User.objects.get_or_create(
        username=BOT_USERNAME,
        defaults={
            "first_name": "Alex",
            "email": f"{BOT_USERNAME}@vaadvivaad.internal",
            "is_active": True,
        },
    )
    if created:
        from users.models import UserProfile
        UserProfile.objects.create(user=user, is_bot=True)
    return user


def get_bot_user_in_debate(*, debate: Debate) -> Optional[User]:
    from users.models import UserProfile
    profile = (
        UserProfile.objects.filter(
            user__in=[debate.user_pro_id, debate.user_con_id], is_bot=True
        )
        .select_related("user")
        .first()
    )
    return profile.user if profile else None


def _build_bot_history(*, debate: Debate, bot_user: User) -> list[str]:
    lines = []
    for r in selectors.get_rounds_for_debate_ordered(debate=debate):
        for msg in selectors.get_messages_for_debate_round_ordered(round_obj=r):
            speaker = "You" if msg.user == bot_user else "Opponent"
            lines.append(f"[{r.round_type}] {speaker}: {msg.content}")
    return lines


@transaction.atomic
def _atomic_bot_submit(
    *, debate: Debate, bot_user: User, argument: str
) -> Optional[tuple[Message, Optional[Round]]]:
    """Lock the current round before writing to prevent concurrent bot submissions."""
    current_round = (
        Round.objects.select_for_update()
        .filter(debate=debate, ended_at__isnull=True)
        .order_by("order")
        .first()
    )
    if not current_round:
        return None
    if not _is_user_turn(debate=debate, current_round=current_round, user=bot_user):
        return None

    message = selectors.create_message_in_round(
        debate=debate, round_obj=current_round, user=bot_user, content=argument
    )
    next_round = _advance_after_turn(
        debate=debate, current_round=current_round, ender=bot_user
    )
    return message, next_round


def generate_and_submit_bot_message(
    *, debate_id: int
) -> Optional[tuple[Message, Optional[Round]]]:
    from debate.utils.bot_client import bot_client

    debate = selectors.get_debate_by_id(debate_id=debate_id)
    if not debate or debate.status != DebateStatus.ONGOING:
        return None

    bot_user = get_bot_user_in_debate(debate=debate)
    if not bot_user:
        return None

    # Pre-check outside the transaction — avoids calling Claude when it's not bot's turn
    current_round = selectors.get_current_round(debate=debate)
    if not current_round:
        return None
    if not _is_user_turn(debate=debate, current_round=current_round, user=bot_user):
        return None

    side = "PRO" if bot_user == debate.user_pro else "CON"
    history = _build_bot_history(debate=debate, bot_user=bot_user)

    argument = bot_client.generate(
        topic=debate.topic.title,
        description=debate.topic.description,
        side=side,
        round_type=current_round.round_type,
        history=history,
    )

    # Atomic check-and-insert with row lock prevents double-submission race
    return _atomic_bot_submit(debate=debate, bot_user=bot_user, argument=argument)


def schedule_bot_response_if_needed(*, debate_id: int) -> None:
    from debate.tasks import bot_respond

    debate = selectors.get_debate_by_id(debate_id=debate_id)
    if not debate or debate.status != DebateStatus.ONGOING:
        return

    bot_user = get_bot_user_in_debate(debate=debate)
    if not bot_user:
        return

    current_round = selectors.get_current_round(debate=debate)
    if not current_round:
        return

    if _is_user_turn(debate=debate, current_round=current_round, user=bot_user):
        bot_respond.apply_async(args=[debate_id], countdown=random.randint(10, 20))


@transaction.atomic
def match_with_bot(*, queue_id: int) -> None:
    entry = (
        MatchQueue.objects.select_for_update()
        .filter(id=queue_id, status=MatchQueueStatus.PENDING)
        .first()
    )
    if not entry:
        return  # Already matched or cancelled by the time the task fires

    bot_user = get_or_create_bot_user()
    bot_side = ProOrCon.CON if entry.pro_or_con == ProOrCon.PRO else ProOrCon.PRO
    user_pro = entry.user if entry.pro_or_con == ProOrCon.PRO else bot_user
    user_con = entry.user if entry.pro_or_con == ProOrCon.CON else bot_user
    now = timezone.now()

    debate = Debate.objects.create(
        topic=entry.topic,
        user_pro=user_pro,
        user_con=user_con,
        status=DebateStatus.ONGOING,
    )
    Round.objects.create(
        debate=debate,
        round_type=RoundType.OPENING,
        order=1,
        started_at=now,
        current_speaker=user_pro,
        turn_started_at=now,
    )
    entry.status = MatchQueueStatus.MATCHED
    entry.matched = True
    entry.matched_at = now
    entry.debate = debate
    entry.save(update_fields=["status", "matched", "matched_at", "debate"])

    MatchQueue.objects.create(
        user=bot_user,
        topic=entry.topic,
        pro_or_con=bot_side,
        status=MatchQueueStatus.MATCHED,
        matched=True,
        matched_at=now,
        debate=debate,
    )
    transaction.on_commit(partial(send_queue_matched_event, entry, debate))
    # Bot sends its OPENING argument first so the user has something to respond to immediately
    from debate.tasks import bot_respond
    transaction.on_commit(lambda:bot_respond.apply_async(args=[debate.id], countdown=random.randint(8, 15)))
    # bot_respond.apply_async(args=[debate.id], countdown=random.randint(8, 15))



def get_debate_ground_rules():
    config = get_application_config_by_name(name=ApplicationConfigName.DEBATE_GROUND_RULES.value)
    properties = config.properties if config else {}
    rules = properties.get("rules", [])
    return rules


def serialize_category_and_debate_rules(*, categories: List[Category]):
    categories_data = CategorySerializer(categories, many=True).data
    debate_rules = get_debate_ground_rules()
    return categories_data, debate_rules


def get_user_debate_and_message(*, user: User, debate_id: int):
    debate = selectors.get_debate_by_user_and_id(user=user, debate_id=debate_id)
    if not debate:
        raise ServiceException("This debate does not exist")
    messages = selectors.get_messages_by_debate_id(debate_id=debate_id)
    messages_data = serialize_messages_of_debate(messages=messages)
    return messages_data
