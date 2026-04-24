import json
import random
import logging

from django.utils import timezone
from django.db import transaction
from django.contrib.auth.models import User

from base.exception import ServiceException
from debate.constants import DebateStatus, MatchQueueStatus, ProOrCon, RoundType
from debate.models import Debate, Round, Message, Judgement, MatchQueue, Topic
from debate.selectors import get_active_queue_entry, get_debate_by_id, get_pending_match_for_topic, get_current_round
from debate.serializers import DebateListSerializer, TopicSerializer

logger = logging.getLogger(__name__)

JUDGE_MODEL_DEFAULT = 'claude-haiku-4-5-20251001'
JUDGE_MODEL_ESCALATION = 'claude-sonnet-4-6'

ROUND_SEQUENCE = [
    (RoundType.OPENING, 1),
    (RoundType.REBUTTAL, 2),
    (RoundType.CLOSING, 3),
]

JUDGE_PROMPT = """\
You are a strict but fair debate judge. Evaluate this 1v1 structured debate objectively.

{transcript}

Score each debater 1-10 on four dimensions:
- Argument Strength (30%): coherence and support for their position
- Rebuttal/Engagement (30%): addressing the opponent's points
- Persuasiveness (25%): moving the needle on the topic
- Clarity (15%): ease of following the argument

Respond ONLY with valid JSON, no extra text:
{{
  "winner": "pro" or "con",
  "pro": {{
    "argument_score": <1-10>,
    "rebuttal_score": <1-10>,
    "clarity_score": <1-10>,
    "persuasion_score": <1-10>
  }},
  "con": {{
    "argument_score": <1-10>,
    "rebuttal_score": <1-10>,
    "clarity_score": <1-10>,
    "persuasion_score": <1-10>
  }},
  "reasoning": "<2-3 sentence verdict rationale>",
  "strongest_moment": "<exact quote of the single best argument from the debate>",
  "coaching_tip_pro": "<one specific actionable improvement tip for the pro debater>",
  "coaching_tip_con": "<one specific actionable improvement tip for the con debater>"
}}"""


# ── Queue / Matchmaking ──────────────────────────────────────────────────────

def join_queue(*, user: User, topic_id: int, pro_or_con: str) -> MatchQueue:
    try:
        topic = Topic.objects.get(id=topic_id, is_active=True)
    except Topic.DoesNotExist:
        raise ServiceException(message="Topic not found or inactive")

    if get_active_queue_entry(user=user):
        raise ServiceException(message="You are already in the queue")

    with transaction.atomic():
        opponent_entry = get_pending_match_for_topic(topic_id=topic_id, exclude_user=user, pro_or_con=pro_or_con)
        if opponent_entry:
            return _create_match(user=user, opponent_entry=opponent_entry, topic=topic, pro_or_con=pro_or_con)

        return MatchQueue.objects.create(
            user=user,
            topic=topic,
            status=MatchQueueStatus.PENDING,
            pro_or_con=pro_or_con,
        )

@transaction.atomic
def _create_match(*, user: User, opponent_entry: MatchQueue, topic: Topic, pro_or_con: str) -> MatchQueue:
    user_pro, user_con = (user, opponent_entry.user) if pro_or_con == ProOrCon.PRO else (opponent_entry.user, user)

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
        started_at=timezone.now(),
    )

    now = timezone.now()
    opponent_entry.status = MatchQueueStatus.MATCHED
    opponent_entry.matched = True
    opponent_entry.matched_at = now
    opponent_entry.debate = debate
    opponent_entry.save(update_fields=['status', 'matched', 'matched_at', 'debate'])

    return MatchQueue.objects.create(
        user=user,
        topic=topic,
        status=MatchQueueStatus.MATCHED,
        matched=True,
        matched_at=now,
        debate=debate,
    )


def leave_queue(*, user: User) -> None:
    entry = get_active_queue_entry(user=user)
    if not entry:
        raise ServiceException(message="You are not in the queue")
    entry.status = MatchQueueStatus.CANCELLED
    entry.save(update_fields=['status'])


# ── Messages / Round progression ────────────────────────────────────────────

def submit_message(*, user: User, debate_id: int, content: str) -> Message:
    debate = get_debate_by_id(debate_id=debate_id)
    if not debate:
        raise ServiceException(message="Debate not found")

    if debate.status != DebateStatus.ONGOING:
        raise ServiceException(message="This debate is not active")

    if user not in (debate.user_pro, debate.user_con):
        raise ServiceException(message="You are not a participant in this debate")

    current_round = get_current_round(debate=debate)
    if not current_round:
        raise ServiceException(message="No active round found")

    if not _is_user_turn(debate=debate, current_round=current_round, user=user):
        raise ServiceException(message="It is not your turn to submit")

    message = Message.objects.create(
        debate=debate,
        round=current_round,
        user=user,
        content=content,
    )

    next_round = _maybe_advance_round(debate=debate, current_round=current_round)
    return message, next_round


def _is_user_turn(*, debate: Debate, current_round: Round, user: User) -> bool:
    round_messages = Message.objects.filter(round=current_round)

    if round_messages.filter(user=user).exists():
        return False  # already submitted this round

    if current_round.round_type == RoundType.OPENING:
        return True  # simultaneous — both can submit freely

    if current_round.round_type == RoundType.REBUTTAL:
        if user == debate.user_pro:
            return True  # pro goes first
        return round_messages.filter(user=debate.user_pro).exists()  # con waits for pro

    if current_round.round_type == RoundType.CLOSING:
        if user == debate.user_con:
            return True  # con goes first
        return round_messages.filter(user=debate.user_con).exists()  # pro waits for con

    return False


def _maybe_advance_round(*, debate: Debate, current_round: Round) -> None:
    round_messages = Message.objects.filter(round=current_round)
    both_submitted = (
        round_messages.filter(user=debate.user_pro).exists()
        and round_messages.filter(user=debate.user_con).exists()
    )
    if not both_submitted:
        return

    current_round.ended_at = timezone.now()
    current_round.save(update_fields=['ended_at'])

    next_rounds = [(rt, order) for rt, order in ROUND_SEQUENCE if order > current_round.order]
    if next_rounds:
        next_type, next_order = next_rounds[0]
        next_round = Round.objects.create(
            debate=debate,
            round_type=next_type,
            order=next_order,
            started_at=timezone.now(),
        )
        return next_round
    # else:
    #     _trigger_judging(debate=debate)


# ── AI Judging ───────────────────────────────────────────────────────────────

def _build_transcript(debate: Debate) -> str:
    lines = [
        f"Topic: {debate.topic.title}",
        f"Pro side: {debate.user_pro.username}",
        f"Con side: {debate.user_con.username}",
        "",
    ]
    for r in Round.objects.filter(debate=debate).order_by('order'):
        lines.append(f"[Round {r.order} — {r.round_type}]")
        for msg in Message.objects.filter(round=r).order_by('created_at'):
            side = "Pro" if msg.user == debate.user_pro else "Con"
            lines.append(f"{side}: {msg.content}")
        lines.append("")
    return "\n".join(lines)


def _call_judge(*, debate: Debate, model: str) -> dict:
    import anthropic
    from django.conf import settings

    client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
    transcript = _build_transcript(debate=debate)

    response = client.messages.create(
        model=model,
        max_tokens=1024,
        messages=[{"role": "user", "content": JUDGE_PROMPT.format(transcript=transcript)}],
    )
    return json.loads(response.content[0].text.strip())


def _save_judgement(*, debate: Debate, data: dict) -> Judgement:
    winner_user = debate.user_pro if data["winner"] == "pro" else debate.user_con

    Judgement.objects.filter(debate=debate).delete()

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
    debate.save(update_fields=['status', 'winner', 'completed_at'])

    return judgement


def _trigger_judging(*, debate: Debate) -> None:
    debate.status = DebateStatus.JUDGING
    debate.save(update_fields=['status'])

    # try:
    #     data = _call_judge(debate=debate, model=JUDGE_MODEL_DEFAULT)
    #     _save_judgement(debate=debate, data=data)
    # except Exception as e:
    #     logger.error(f"Judging failed for debate {debate.id}: {e}", exc_info=True)
    #     debate.status = DebateStatus.ONGOING
    #     debate.save(update_fields=['status'])
    #     raise ServiceException(message="Judging failed, please try again")


def dispute_judgement(*, user: User, debate_id: int) -> Judgement:
    try:
        debate = Debate.objects.select_related('user_pro', 'user_con').get(id=debate_id)
    except Debate.DoesNotExist:
        raise ServiceException(message="Debate not found")

    if user not in (debate.user_pro, debate.user_con):
        raise ServiceException(message="You are not a participant in this debate")

    if debate.status != DebateStatus.COMPLETED:
        raise ServiceException(message="Can only dispute a completed debate")

    debate.status = DebateStatus.DISPUTED
    debate.save(update_fields=['status'])

    try:
        data = _call_judge(debate=debate, model=JUDGE_MODEL_ESCALATION)
        return _save_judgement(debate=debate, data=data)
    except Exception as e:
        logger.error(f"Dispute judging failed for debate {debate.id}: {e}", exc_info=True)
        debate.status = DebateStatus.COMPLETED
        debate.save(update_fields=['status'])
        raise ServiceException(message="Dispute judging failed, please try again")


def _join_queue_outcome(user: User, topic_id: int, pro_or_con: str) -> dict:
    entry = join_queue(user=user, topic_id=topic_id, pro_or_con=pro_or_con)
    if entry.status == MatchQueueStatus.MATCHED and entry.debate_id:
        debate = (
            Debate.objects.select_related('topic', 'user_pro', 'user_con', 'winner')
            .get(id=entry.debate_id)
        )
        opponent_id = (
            debate.user_con_id
            if user.id == debate.user_pro_id
            else debate.user_pro_id
        )
        return {
            'outcome': 'matched',
            'opponent_id': opponent_id,
            'debate': DebateListSerializer(debate).data,
        }
    return {
        'outcome': 'waiting',
        'queue_id': entry.id,
        'topic': TopicSerializer(entry.topic).data,
    }