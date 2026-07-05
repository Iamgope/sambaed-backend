from django.urls import path
from debate.consumers import DebateConsumer

websocket_urlpatterns = [
    path("ws/debate/", DebateConsumer.as_asgi()),
]
