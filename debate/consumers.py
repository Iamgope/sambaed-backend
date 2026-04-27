import json
import logging
from typing import Callable, Dict

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer
from django.contrib.auth.models import AnonymousUser

from base.decorators import websocket_catch_service_exception
from debate.constants import DebateStatus, MatchQueueStatus
from debate.selectors import update_debate_status, update_match_queue_status
from debate.serializers import MessageSerializer, RoundSerializer
from debate.services import _join_queue_outcome, get_pro_or_con, submit_message, leave_queue

logger = logging.getLogger(__name__)
DEBATE_GROUP = "debate_{debate_id}"

class DebateConsumer(AsyncWebsocketConsumer):
    """
    WebSocket consumer for a live debate session.

    Connect:  ws://<host>/ws/debate/

    Each connection is in a per-user group ``user_{user_id}`` (for DMs e.g. match
    offers) and, after a match, the shared group ``debate_{debate_id}`` with the
    opponent. You cannot "add the opponent’s channel" by id; each browser adds its
    own connection to the same named group. Fan-out to both players::

        await channel_layer.group_send(
            f"debate_{debate_id}",
            {"type": "debate.event", "client_type": "round.advanced", "data": {...}},
        )

    Client → Server events:
        {"type": "message", "data": {"content": "..."}}
        {"type": "join_queue", "data": {"topic_id": <int>}}

    Server → Client events:
        {"type": "queue.matched", "data": {"debate": {...}}}   # match found
        {"type": "queue.waiting", "data": {"queue_id", "topic"}}  # wait for opponent
        {"type": "message.new",     "message":  {...}}
        {"type": "round.advanced",  "round":    {...}}
        {"type": "debate.judging"}
        {"type": "debate.completed","judgement": {...}}
        {"type": "error",           "message":  "..."}
    """

    # ── Connection lifecycle ──────────────────────────────────────────────────

    async def connect(self):
        self.user = self.scope.get('user')

        if not self.user or isinstance(self.user, AnonymousUser):
            await self.close(code=4001)
            return

        self.user_group_name = f'user_{self.user.id}'

        await self.channel_layer.group_add(self.user_group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        await self.handle_leave_queue({})
        if getattr(self, 'debate_group_name', None):
            await self.channel_layer.group_discard(
                self.debate_group_name, self.channel_name
            )
        if hasattr(self, 'user_group_name'):
            await self.channel_layer.group_discard(self.user_group_name, self.channel_name)

    async def _send_error(self, message: str):
        await self.send(text_data=json.dumps({'type': 'error', 'message': message}))

    async def _add_to_debate_group(self, debate_id: int) -> None:
        """Subscribes this connection to the shared group for that debate (both users)."""
        self.debate_id = debate_id
        self.debate_group_name = DEBATE_GROUP.format(debate_id=debate_id)
        await self.channel_layer.group_add(self.debate_group_name, self.channel_name)

    # ── Incoming messages ─────────────────────────────────────────────────────
    def event_mapping(self) -> Dict[str, Callable]:
        return {
            "message": self.handle_message,
            "join_queue": self.handle_join_queue,
            "leave_queue": self.handle_leave_queue,
        }

    async def receive(self, text_data=None, bytes_data=None):
        if not text_data:
            await self._send_error("Expected text data")
            return
        try:
            payload = json.loads(text_data)
        except json.JSONDecodeError:
            await self._send_error("Invalid JSON")
            return

        event_type = payload.get('type')
        event_data = payload.get('data') or {}
        try:
            handler = self.event_mapping()[event_type]
        except KeyError:
            await self._send_error(f"Unknown event type: {event_type!r}")
            return

        await handler(event_data)

    async def handle_message(self, event_data: dict):
        content = event_data.get('content', '')
        if not content:
            await self._send_error("Content is required")
            return
        await self.handle_message_submit(content)

    @websocket_catch_service_exception(default_message="Could not submit the message")
    async def handle_message_submit(self, content: str):
        debate_id = self.debate_id
        if not debate_id or not self.debate_group_name:
            await self._send_error("No active debate for this connection")
            return
        message, next_round = await database_sync_to_async(submit_message)(
            user=self.user, debate_id=debate_id, content=content
        )
        await self.channel_layer.group_send(
            self.debate_group_name,
            {
                'type': 'message.new',
                'message': MessageSerializer(message).data,
            },
        )
        if next_round:
            # TODO: send after a delay to allow the opponent to read this message first
            await self.channel_layer.group_send(
                self.debate_group_name,
                {
                    'type': 'round.advanced',
                    'round': RoundSerializer(next_round).data,
                },
            )


    @websocket_catch_service_exception(default_message="Could not join the queue")
    async def handle_join_queue(self, event_data: dict):
        topic_id = int(event_data.get('topic_id'))
        pro_or_con = event_data.get('pro_or_con')
        category_id = event_data.get('category_id')
        if not topic_id and not category_id:
            await self._send_error("Topic ID or  Category ID is required")
            return
        
        pro_or_con = await database_sync_to_async(get_pro_or_con)(user=self.user, pro_or_con=pro_or_con)
        outcome = await database_sync_to_async(_join_queue_outcome)(
            user=self.user, topic_id=topic_id, pro_or_con=pro_or_con, category_id=category_id
        )
        await self.process_join_queue_outcome(outcome)

    async def process_join_queue_outcome(self, outcome: Dict):
        if outcome['outcome'] == 'matched':
            data = {'debate': outcome['debate']}
            self.opponent_id = outcome['opponent_id']
            await self._add_to_debate_group(outcome['debate']['id'])

            await self.send(
                text_data=json.dumps({'type': 'queue.matched', 'data': data})
            )
            # Opponent is not in debate_* yet, so they still get this over user_*
            await self.channel_layer.group_send(
                f"user_{outcome['opponent_id']}",
                {
                    'type': 'queue.matched',
                    'data': data,
                },
            )
        else:
            await self.send(
                text_data=json.dumps({
                    'type': 'queue.waiting',
                    'data': {
                        'queue_id': outcome['queue_id'],
                        'topic': outcome['topic'],
                    },
                })
            )

    async def handle_leave_queue(self, event_data: dict):
        await database_sync_to_async(leave_queue)(
            user=self.user
        )
        if self.debate_id:
            await self.process_and_update_status_on_leave()
            await self.channel_layer.group_send(
                self.debate_group_name,
                {
                    'type': 'queue.left',
                    'data': {
                        "debate_id": self.debate_id, 
                        "left_by": self.user.id, 
                        "opponent_id": self.opponent_id,
                    }
                }
            )
            await self.channel_layer.group_discard(self.user_group_name, self.channel_name)
    
    async def process_and_update_status_on_leave(self):
        logger.info(f"User {self.user.id} left the queue")
        await database_sync_to_async(update_debate_status)(
            debate_id=self.debate_id, status=DebateStatus.ABANDONED
        )
        await database_sync_to_async(update_match_queue_status)(
            user_id=self.opponent_id, status=MatchQueueStatus.PENDING, debate_id=self.debate_id
        )
        await database_sync_to_async(update_match_queue_status)(
            user_id=self.user.id, status=MatchQueueStatus.ABANDONED, debate_id=self.debate_id
        )

    async def queue_left(self, event):
        # TODO: what to do with opponent? once the debate is abandoned
        await self.channel_layer.group_discard(
            self.debate_group_name, self.channel_name
        )
        self.debate_id = None
        self.debate_group_name = None
        self.opponent_id = None

    async def queue_matched(self, event):
        """The waitee: join the same ``debate_{id}`` group, then tell the client."""
        payload = event.get('data') or {}
        debate = payload.get('debate') or {}
        debate_id = debate.get('id')
        if debate_id:
            await self._add_to_debate_group(debate_id)
            pro = (debate.get('user_pro') or {}).get('id')
            con = (debate.get('user_con') or {}).get('id')
            if pro and con and self.user.id in (pro, con):
                self.opponent_id = con if self.user.id == pro else pro

        await self.send(
            text_data=json.dumps({'type': 'queue.matched', 'data': payload})
        )

    async def message_new(self, event):
        """In-debate broadcast from ``group_send`` (type ``message.new``)."""
        await self.send(
            text_data=json.dumps(
                {'type': 'message.new', 'message': event.get('message', {})}
            )
        )
