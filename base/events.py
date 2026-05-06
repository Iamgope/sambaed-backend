from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync

from debate.models import Debate, MatchQueue
from debate.serializers import DebateListSerializer



def send_queue_matched_event(*, match_entry: MatchQueue, debate: Debate):
    # Notify the waiting user over their personal WebSocket group
    channel_layer = get_channel_layer()
    async_to_sync(channel_layer.group_send)(
        f"user_{match_entry.user_id}",
        {
            "type": "queue.matched",
            "data": {"debate": DebateListSerializer(debate).data},
        },
    )
