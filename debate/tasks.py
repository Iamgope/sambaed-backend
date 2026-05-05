from celery import shared_task
from channels.layers import get_channel_layer

import debate
from debate.serializers import JudgementSerializer
from debate.services import dispute_judgement
from users.selectors import get_user_by_id


@shared_task
def send_advance_round_event(group_name: str, data: dict) -> None:
    channel_layer = get_channel_layer()
    channel_layer.group_send(
        group_name,
        {
            "type": "round.advance",
            "data": data,
        },
    )


@shared_task
def start_judgement_of_debate_and_share_result(debate_id: int, user_id: int, group_name: str):
    user = get_user_by_id(user_id=user_id)
    judgemnet = dispute_judgement(user=user, debate_id=debate_id)
    channel_layer = get_channel_layer()
    channel_layer.group_send(
        group_name,
        {
            "type": "judgement",
            "data":JudgementSerializer(judgemnet).data,
        }
    )
