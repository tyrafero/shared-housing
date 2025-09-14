import json
import uuid
from datetime import datetime, timedelta
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.contrib.auth import get_user_model
from django.utils import timezone
from .models import Conversation, Message, ConversationParticipant

User = get_user_model()


class ChatConsumer(AsyncWebsocketConsumer):
    """WebSocket consumer for real-time messaging"""

    async def connect(self):
        # Get conversation ID from URL route
        self.conversation_id = self.scope['url_route']['kwargs']['conversation_id']
        self.room_group_name = f'chat_{self.conversation_id}'

        # Get user from scope
        self.user = self.scope["user"]

        if self.user.is_anonymous:
            await self.close(code=4001)
            return

        # Check if user is participant in this conversation
        if not await self.is_participant():
            await self.close(code=4003)
            return

        # Join room group
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )

        await self.accept()

        # Mark user as online
        await self.update_user_status(True)

        # Send user joined notification to group
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'user_status',
                'user_id': self.user.id,
                'user_name': self.user.get_short_name(),
                'status': 'online'
            }
        )

    async def disconnect(self, close_code):
        if hasattr(self, 'room_group_name'):
            # Mark user as offline
            await self.update_user_status(False)

            # Send user left notification to group
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'user_status',
                    'user_id': self.user.id,
                    'user_name': self.user.get_short_name(),
                    'status': 'offline'
                }
            )

            # Leave room group
            await self.channel_layer.group_discard(
                self.room_group_name,
                self.channel_name
            )

    async def receive(self, text_data):
        """Receive message from WebSocket"""
        try:
            text_data_json = json.loads(text_data)
            message_type = text_data_json.get('type', 'message')

            if message_type == 'message':
                await self.handle_message(text_data_json)
            elif message_type == 'typing':
                await self.handle_typing(text_data_json)
            elif message_type == 'read_receipt':
                await self.handle_read_receipt(text_data_json)
            elif message_type == 'reaction':
                await self.handle_reaction(text_data_json)
            else:
                await self.send_error("Unknown message type")

        except json.JSONDecodeError:
            await self.send_error("Invalid JSON")
        except Exception as e:
            await self.send_error(f"Error processing message: {str(e)}")

    async def handle_message(self, data):
        """Handle sending a chat message"""
        content = data.get('content', '').strip()
        reply_to_id = data.get('reply_to')

        if not content:
            await self.send_error("Message content cannot be empty")
            return

        # Create message in database
        message = await self.create_message(content, reply_to_id)

        if message:
            # Send message to room group
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'chat_message',
                    'message': await self.serialize_message(message)
                }
            )

            # Mark conversation as read for sender
            await self.mark_conversation_read()

    async def handle_typing(self, data):
        """Handle typing indicators"""
        is_typing = data.get('is_typing', False)

        # Send typing indicator to room group (excluding sender)
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'typing_indicator',
                'user_id': self.user.id,
                'user_name': self.user.get_short_name(),
                'is_typing': is_typing,
                'exclude_sender': True
            }
        )

    async def handle_read_receipt(self, data):
        """Handle read receipts"""
        message_id = data.get('message_id')

        if message_id:
            success = await self.mark_message_read(message_id)
            if success:
                await self.channel_layer.group_send(
                    self.room_group_name,
                    {
                        'type': 'read_receipt',
                        'message_id': message_id,
                        'user_id': self.user.id,
                        'user_name': self.user.get_short_name()
                    }
                )

    async def handle_reaction(self, data):
        """Handle message reactions"""
        message_id = data.get('message_id')
        reaction_type = data.get('reaction_type')

        if message_id and reaction_type:
            reaction = await self.toggle_reaction(message_id, reaction_type)
            if reaction:
                await self.channel_layer.group_send(
                    self.room_group_name,
                    {
                        'type': 'message_reaction',
                        'message_id': message_id,
                        'user_id': self.user.id,
                        'reaction_type': reaction_type,
                        'action': reaction['action']  # 'added' or 'removed'
                    }
                )

    # Handlers for messages sent to the group
    async def chat_message(self, event):
        """Send chat message to WebSocket"""
        await self.send(text_data=json.dumps({
            'type': 'message',
            'message': event['message']
        }))

    async def user_status(self, event):
        """Send user status update to WebSocket"""
        # Don't send to the user who triggered the status change
        if event.get('user_id') != self.user.id:
            await self.send(text_data=json.dumps({
                'type': 'user_status',
                'user_id': event['user_id'],
                'user_name': event['user_name'],
                'status': event['status']
            }))

    async def typing_indicator(self, event):
        """Send typing indicator to WebSocket"""
        # Don't send to the user who is typing
        if event.get('exclude_sender') and event.get('user_id') == self.user.id:
            return

        await self.send(text_data=json.dumps({
            'type': 'typing',
            'user_id': event['user_id'],
            'user_name': event['user_name'],
            'is_typing': event['is_typing']
        }))

    async def read_receipt(self, event):
        """Send read receipt to WebSocket"""
        await self.send(text_data=json.dumps({
            'type': 'read_receipt',
            'message_id': event['message_id'],
            'user_id': event['user_id'],
            'user_name': event['user_name']
        }))

    async def message_reaction(self, event):
        """Send message reaction to WebSocket"""
        await self.send(text_data=json.dumps({
            'type': 'reaction',
            'message_id': event['message_id'],
            'user_id': event['user_id'],
            'reaction_type': event['reaction_type'],
            'action': event['action']
        }))

    async def send_error(self, message):
        """Send error message to WebSocket"""
        await self.send(text_data=json.dumps({
            'type': 'error',
            'message': message
        }))

    # Database operations
    @database_sync_to_async
    def is_participant(self):
        """Check if user is participant in conversation"""
        try:
            conversation = Conversation.objects.get(id=self.conversation_id)
            return conversation.participants.filter(id=self.user.id).exists()
        except Conversation.DoesNotExist:
            return False

    @database_sync_to_async
    def create_message(self, content, reply_to_id=None):
        """Create a new message in database"""
        try:
            conversation = Conversation.objects.get(id=self.conversation_id)

            reply_to = None
            if reply_to_id:
                try:
                    reply_to = Message.objects.get(
                        id=reply_to_id,
                        conversation=conversation
                    )
                except Message.DoesNotExist:
                    pass

            message = Message.objects.create(
                conversation=conversation,
                sender=self.user,
                content=content,
                reply_to=reply_to
            )
            return message

        except Conversation.DoesNotExist:
            return None

    @database_sync_to_async
    def serialize_message(self, message):
        """Convert message to JSON-serializable format"""
        return {
            'id': str(message.id),
            'content': message.content,
            'sender': {
                'id': message.sender.id,
                'name': message.sender.get_short_name(),
                'email': message.sender.email
            },
            'message_type': message.message_type,
            'reply_to': str(message.reply_to.id) if message.reply_to else None,
            'created_at': message.created_at.isoformat(),
            'is_edited': message.is_edited,
            'has_attachment': message.has_attachment
        }

    @database_sync_to_async
    def mark_conversation_read(self):
        """Mark conversation as read for current user"""
        try:
            conversation = Conversation.objects.get(id=self.conversation_id)
            conversation.mark_as_read(self.user)
        except Conversation.DoesNotExist:
            pass

    @database_sync_to_async
    def mark_message_read(self, message_id):
        """Mark specific message as read"""
        try:
            from .models import MessageReadReceipt
            message = Message.objects.get(
                id=message_id,
                conversation_id=self.conversation_id
            )

            # Don't create read receipt for own messages
            if message.sender == self.user:
                return False

            MessageReadReceipt.objects.get_or_create(
                message=message,
                user=self.user
            )
            return True

        except (Message.DoesNotExist, ValueError):
            return False

    @database_sync_to_async
    def toggle_reaction(self, message_id, reaction_type):
        """Toggle reaction on a message"""
        try:
            from .models import MessageReaction

            message = Message.objects.get(
                id=message_id,
                conversation_id=self.conversation_id
            )

            reaction, created = MessageReaction.objects.get_or_create(
                message=message,
                user=self.user,
                reaction_type=reaction_type
            )

            if created:
                return {'action': 'added', 'reaction': reaction}
            else:
                reaction.delete()
                return {'action': 'removed'}

        except (Message.DoesNotExist, ValueError):
            return None

    @database_sync_to_async
    def update_user_status(self, is_online):
        """Update user's online status"""
        # This could be extended to track user presence
        # For now, we just send the status to the group
        pass


class NotificationConsumer(AsyncWebsocketConsumer):
    """WebSocket consumer for real-time notifications"""

    async def connect(self):
        self.user = self.scope["user"]

        if self.user.is_anonymous:
            await self.close(code=4001)
            return

        # Join user's personal notification group
        self.notification_group_name = f'notifications_{self.user.id}'

        await self.channel_layer.group_add(
            self.notification_group_name,
            self.channel_name
        )

        await self.accept()

    async def disconnect(self, close_code):
        if hasattr(self, 'notification_group_name'):
            await self.channel_layer.group_discard(
                self.notification_group_name,
                self.channel_name
            )

    async def receive(self, text_data):
        """Handle incoming WebSocket messages"""
        try:
            text_data_json = json.loads(text_data)
            message_type = text_data_json.get('type')

            if message_type == 'mark_read':
                notification_id = text_data_json.get('notification_id')
                if notification_id:
                    await self.mark_notification_read(notification_id)

        except json.JSONDecodeError:
            pass

    # Handler for notification messages
    async def send_notification(self, event):
        """Send notification to WebSocket"""
        await self.send(text_data=json.dumps({
            'type': 'notification',
            'notification': event['notification']
        }))

    @database_sync_to_async
    def mark_notification_read(self, notification_id):
        """Mark notification as read"""
        # This would be implemented when we have a notifications model
        pass