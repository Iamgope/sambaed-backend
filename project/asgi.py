import os

from django.urls import path

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'project.settings')

# Django app registry must be ready before importing consumers / routing.
from django.core.asgi import get_asgi_application
django_asgi_app = get_asgi_application()

from channels.routing import ProtocolTypeRouter, URLRouter
from debate.consumers import DebateConsumer
from base.middleware import JWTAuthMiddleware

application = ProtocolTypeRouter({
    'http': django_asgi_app,
    'websocket': JWTAuthMiddleware(
        URLRouter([
            path('ws/debate/', DebateConsumer.as_asgi()),
        ])
    ),
})
