from django.urls import path
from . import views

app_name = 'messaging'

urlpatterns = [
    # Main messaging views
    path('', views.conversations_list, name='conversations_list'),
    path('conversation/<uuid:conversation_id>/', views.conversation_detail, name='conversation_detail'),
    path('start/', views.start_conversation, name='start_conversation'),

    # Conversation actions
    path('conversation/<uuid:conversation_id>/send/', views.send_message, name='send_message'),
    path('conversation/<uuid:conversation_id>/leave/', views.leave_conversation, name='leave_conversation'),
    path('conversation/<uuid:conversation_id>/add-participants/', views.add_participants, name='add_participants'),

    # Special conversation types
    path('property-inquiry/<int:property_id>/', views.property_inquiry, name='property_inquiry'),
    path('roommate-chat/<int:user_id>/', views.start_roommate_chat, name='start_roommate_chat'),

    # API endpoints
    path('api/conversation/<uuid:conversation_id>/messages/', views.messages_api, name='messages_api'),
    path('api/search/messages/', views.search_messages, name='search_messages'),
    path('api/search/users/', views.user_search, name='user_search'),
]