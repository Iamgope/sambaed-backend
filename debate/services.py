from collections import defaultdict
from typing import Dict
import json
import random
import logging
from typing import Optional

from django.utils import timezone
from django.db import transaction
from django.contrib.auth.models import User

from base.exception import ServiceException
from debate.constants import DebateStatus, MatchQueueStatus, ProOrCon, RoundType
from debate.models import Debate, Judgement, Message, MatchQueue, Round, Topic
from debate import selectors
from debate.serializers import DebateListSerializer, TopicSerializer

logger = logging.getLogger(__name__)

JUDGE_MODEL_DEFAULT = "claude-haiku-4-5-20251001"
JUDGE_MODEL_ESCALATION = "claude-sonnet-4-6"

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
    return selectors.create_match_queue_entry(
        user=user, topic=topic, pro_or_con=pro_or_con, status=MatchQueueStatus.PENDING
    )

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


def submit_message(
    *, user: User, debate_id: int, content: str
) -> tuple[Message, Optional[Round]]:
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

    message = selectors.create_message_in_round(
        debate=debate, round_obj=current_round, user=user, content=content
    )
    next_round = _maybe_advance_round(
        debate=debate, current_round=current_round
    )
    return message, next_round


def _is_user_turn(
    *, debate: Debate, current_round: Round, user: User
) -> bool:
    rmsgs = selectors.get_messages_for_round(round_obj=current_round)

    if rmsgs.filter(user=user).exists():
        return False

    if current_round.round_type == RoundType.OPENING:
        return True

    if current_round.round_type == RoundType.REBUTTAL:
        if user == debate.user_pro:
            return True
        return rmsgs.filter(user=debate.user_pro).exists()

    if current_round.round_type == RoundType.CLOSING:
        if user == debate.user_con:
            return True
        return rmsgs.filter(user=debate.user_con).exists()

    return False


def _maybe_advance_round(
    *, debate: Debate, current_round: Round
) -> Optional[Round]:
    rmsgs = selectors.get_messages_for_round(round_obj=current_round)
    if not (
        rmsgs.filter(user=debate.user_pro).exists()
        and rmsgs.filter(user=debate.user_con).exists()
    ):
        return None

    now = timezone.now()
    selectors.mark_round_ended(round_obj=current_round, ended_at=now)

    next_blocks = [
        (rt, order) for rt, order in ROUND_SEQUENCE if order > current_round.order
    ]
    if not next_blocks:
        return None
    next_type, next_order = next_blocks[0]
    return selectors.create_next_round(
        debate=debate,
        round_type=next_type,
        order=next_order,
        started_at=now,
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
        data = _call_judge(debate=debate, model=JUDGE_MODEL_ESCALATION)
        return selectors.apply_judgement_outcome(debate=debate, data=data)
    except Exception as e:
        logger.error("Dispute judging failed for debate %s: %s", debate.id, e, exc_info=True)
        selectors.set_debate_status(debate=debate, status=DebateStatus.COMPLETED)
        raise ServiceException(
            message="Dispute judging failed, please try again"
        ) from e


# ── WebSocket helpers (call join_queue, serialize) ─────────────────────────


def _join_queue_outcome(
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
    result = defaultdict(defaultdict(list))
    for topic_data in data:
        category_name = topic_data['category']["name"]
        result[category_name]["topics"].append(topic_data)
        result[category_name]["description"] = topic_data['category']["description"]
        result[category_name]["background_image"] = topic_data["category"]["background_image"]
    return result
