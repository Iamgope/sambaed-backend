from celery import shared_task
from channels.layers import get_channel_layer


@shared_task
def debug_ping() -> str:
    """Smoke-test task; replace or remove when real tasks are added."""
    return "pong"


@shared_task
def send_advance_round_event(group_name: str, data: dict) -> None:
    channel_layer = get_channel_layer()
    channel_layer.group_send(
        group_name,
        {
            'type': 'round.advanced',
            'round': data,
        },
    )
