from django.urls import path
from debate.consumers import DebateConsumer

websocket_urlpatterns = [
    path('ws/debate/<int:debate_id>/', DebateConsumer.as_asgi()),
]
