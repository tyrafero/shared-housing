from django.urls import re_path, path
from . import consumers

websocket_urlpatterns = [
    # Chat WebSocket for specific conversation
    re_path(
        r'ws/chat/(?P<conversation_id>[0-9a-f-]+)/$',
        consumers.ChatConsumer.as_asgi()
    ),

    # Notifications WebSocket for user
    path(
        'ws/notifications/',
        consumers.NotificationConsumer.as_asgi()
    ),
]