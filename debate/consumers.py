import json
import logging

from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.contrib.auth.models import AnonymousUser

from base.exception import ServiceException
from debate.constants import DebateStatus

logger = logging.getLogger(__name__)


class DebateConsumer(AsyncWebsocketConsumer):
    """
    WebSocket consumer for a live debate session.

    Connect:  ws://<host>/ws/debate/<debate_id>/?token=<jwt>

    Client → Server events:
        {"type": "message", "content": "..."}

    Server → Client events:
        {"type": "message.new",     "message":  {...}}
        {"type": "round.advanced",  "round":    {...}}
        {"type": "debate.judging"}
        {"type": "debate.completed","judgement": {...}}
        {"type": "error",           "message":  "..."}
    """

    # ── Connection lifecycle ──────────────────────────────────────────────────

    async def connect(self):
        self.debate_id = int(self.scope['url_route']['kwargs']['debate_id'])
        self.group_name = f'debate_{self.debate_id}'
        self.user = self.scope.get('user')

        if not self.user or isinstance(self.user, AnonymousUser):
            await self.close(code=4001)
            return

        debate = await self._get_debate()
        if debate is None:
            await self.close(code=4004)
            return

        if self.user.id not in (debate['user_pro_id'], debate['user_con_id']):
            await self.close(code=4003)
            return

        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        if hasattr(self, 'group_name'):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

    # ── Incoming messages ─────────────────────────────────────────────────────

    async def receive(self, text_data):
        try:
            data = json.loads(text_data)
        except json.JSONDecodeError:
            await self._send_error("Invalid JSON")
            return

        event_type = data.get('type')
        if event_type == 'message':
            await self._handle_submit(content=data.get('content', ''))
        else:
            await self._send_error(f"Unknown event type: {event_type!r}")

    async def _handle_submit(self, content: str):
        try:
            result = await self._submit_message(content=content)
        except ServiceException as e:
            await self._send_error(e.message)
            return
        except Exception as e:
            logger.error(f"Unexpected error in debate {self.debate_id}: {e}", exc_info=True)
            await self._send_error("Something went wrong")
            return

        # Always broadcast the new message to both participants
        await self.channel_layer.group_send(
            self.group_name,
            {'type': 'debate.message', 'message': result['message']},
        )

        if result.get('round_advanced'):
            await self.channel_layer.group_send(
                self.group_name,
                {'type': 'debate.round_advanced', 'round': result['new_round']},
            )

        if result.get('debate_judging'):
            await self.channel_layer.group_send(
                self.group_name,
                {'type': 'debate.judging'},
            )

        if result.get('debate_completed'):
            await self.channel_layer.group_send(
                self.group_name,
                {'type': 'debate.completed', 'judgement': result['judgement']},
            )

    # ── Channel layer event handlers (group → this socket) ───────────────────

    async def debate_message(self, event):
        await self.send(text_data=json.dumps({
            'type': 'message.new',
            'message': event['message'],
        }))

    async def debate_round_advanced(self, event):
        await self.send(text_data=json.dumps({
            'type': 'round.advanced',
            'round': event['round'],
        }))

    async def debate_judging(self, event):
        await self.send(text_data=json.dumps({'type': 'debate.judging'}))

    async def debate_completed(self, event):
        await self.send(text_data=json.dumps({
            'type': 'debate.completed',
            'judgement': event['judgement'],
        }))

    # ── Sync DB helpers (run in thread pool) ─────────────────────────────────

    @database_sync_to_async
    def _get_debate(self) -> dict | None:
        from debate.models import Debate
        try:
            d = Debate.objects.only('user_pro_id', 'user_con_id').get(id=self.debate_id)
            return {'user_pro_id': d.user_pro_id, 'user_con_id': d.user_con_id}
        except Debate.DoesNotExist:
            return None

    @database_sync_to_async
    def _submit_message(self, content: str) -> dict:
        from debate.models import Debate, Judgement
        from debate.services import submit_message
        from debate.selectors import get_current_round
        from debate.serializers import MessageSerializer, RoundSerializer, JudgementSerializer

        message = submit_message(user=self.user, debate_id=self.debate_id, content=content)
        result = {'message': MessageSerializer(message).data}

        debate = Debate.objects.select_related('user_pro', 'user_con').get(id=self.debate_id)
        current_round = get_current_round(debate=debate)

        # New round was created after this message closed the previous one
        if current_round and current_round.order > message.round.order:
            result['round_advanced'] = True
            result['new_round'] = RoundSerializer(current_round).data

        if debate.status == DebateStatus.JUDGING:
            result['debate_judging'] = True

        if debate.status == DebateStatus.COMPLETED:
            result['debate_completed'] = True
            try:
                judgement = Judgement.objects.select_related('winner').get(debate=debate)
                result['judgement'] = JudgementSerializer(judgement).data
            except Judgement.DoesNotExist:
                result['judgement'] = None

        return result

    async def _send_error(self, message: str):
        await self.send(text_data=json.dumps({'type': 'error', 'message': message}))
