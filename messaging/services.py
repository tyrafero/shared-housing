from typing import List, Optional, Dict
from datetime import datetime, timedelta
from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone
from django.db.models import Q, Count, Max, Subquery, OuterRef
from django.db import models
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync

from .models import (
    Conversation, ConversationParticipant, Message,
    MessageReaction, ConversationInvite
)
from roommate_matching.services import MatchingService

User = get_user_model()


class MessagingService:
    """Service for managing messaging functionality"""

    def __init__(self):
        try:
            self.channel_layer = get_channel_layer()
        except Exception:
            # Redis not available, disable real-time features
            self.channel_layer = None

    def get_user_conversations(self, user: User, limit: int = 20) -> List[Conversation]:
        """Get conversations for a user, ordered by latest message"""
        return Conversation.objects.filter(
            participants=user,
            is_active=True
        ).select_related(
            'property_listing'
        ).prefetch_related(
            'participants',
            'messages__sender'
        ).annotate(
            unread_count=Count(
                'messages',
                filter=Q(
                    messages__created_at__gt=models.Subquery(
                        ConversationParticipant.objects.filter(
                            conversation=models.OuterRef('pk'),
                            user=user
                        ).values('last_read_at')[:1]
                    )
                )
            )
        ).order_by('-last_message_at')[:limit]

    def start_conversation(self, initiator: User, participants: List[User],
                          conversation_type: str = 'direct',
                          title: str = '', property_listing=None) -> Conversation:
        """Start a new conversation"""

        with transaction.atomic():
            # Create conversation
            conversation = Conversation.objects.create(
                conversation_type=conversation_type,
                title=title,
                property_listing=property_listing
            )

            # Add initiator as admin
            ConversationParticipant.objects.create(
                conversation=conversation,
                user=initiator,
                role='admin',
                can_add_participants=True,
                can_remove_participants=True,
                can_edit_conversation=True
            )

            # Add other participants
            for user in participants:
                if user != initiator:
                    ConversationParticipant.objects.create(
                        conversation=conversation,
                        user=user,
                        role='participant'
                    )

            # Send system message
            if conversation_type == 'group':
                participants_names = ', '.join([p.get_short_name() for p in participants])
                system_message = f"{initiator.get_short_name()} created the group with {participants_names}"
            elif property_listing:
                system_message = f"{initiator.get_short_name()} started a conversation about {property_listing.title}"
            else:
                system_message = f"Conversation started"

            self.send_system_message(conversation, system_message)

            return conversation

    def get_or_create_direct_conversation(self, user1: User, user2: User) -> tuple[Conversation, bool]:
        """Get or create a direct conversation between two users"""
        return Conversation.get_or_create_direct_conversation(user1, user2)

    def send_message(self, conversation: Conversation, sender: User,
                    content: str, message_type: str = 'text',
                    reply_to: Optional[Message] = None) -> Optional[Message]:
        """Send a message in a conversation"""

        # Check if user is participant
        if not conversation.participants.filter(id=sender.id).exists():
            return None

        # Create message
        message = Message.objects.create(
            conversation=conversation,
            sender=sender,
            content=content,
            message_type=message_type,
            reply_to=reply_to
        )

        # Send real-time notification
        self.send_realtime_message(message)

        # Record interaction for matching algorithm
        if conversation.conversation_type == 'roommate_matching':
            matching_service = MatchingService()
            # Get other participants
            other_participants = conversation.participants.exclude(id=sender.id)
            for participant in other_participants:
                matching_service.record_user_interaction(
                    source_user=sender,
                    target_user=participant,
                    interaction_type='send_message',
                    was_recommended=True,  # Could be determined from context
                    metadata={'conversation_id': str(conversation.id)}
                )

        return message

    def send_system_message(self, conversation: Conversation, content: str) -> Message:
        """Send a system message"""
        message = Message.objects.create(
            conversation=conversation,
            sender=None,  # System messages have no sender
            content=content,
            message_type='system'
        )

        self.send_realtime_message(message)
        return message

    def send_realtime_message(self, message: Message):
        """Send message via WebSocket"""
        if not self.channel_layer:
            return

        room_group_name = f'chat_{message.conversation.id}'

        # Serialize message data
        message_data = {
            'id': str(message.id),
            'content': message.content,
            'sender': {
                'id': message.sender.id if message.sender else None,
                'name': message.sender.get_short_name() if message.sender else 'System',
                'email': message.sender.email if message.sender else None
            },
            'message_type': message.message_type,
            'reply_to': str(message.reply_to.id) if message.reply_to else None,
            'created_at': message.created_at.isoformat(),
            'is_edited': message.is_edited,
            'has_attachment': message.has_attachment
        }

        # Send real-time notification if Redis is available
        if self.channel_layer:
            async_to_sync(self.channel_layer.group_send)(
                room_group_name,
                {
                    'type': 'chat_message',
                    'message': message_data
                }
            )

    def get_conversation_messages(self, conversation: Conversation,
                                limit: int = 50, offset: int = 0) -> List[Message]:
        """Get messages for a conversation"""
        return Message.objects.filter(
            conversation=conversation,
            is_deleted=False
        ).select_related(
            'sender', 'reply_to__sender'
        ).prefetch_related(
            'reactions__user'
        ).order_by('-created_at')[offset:offset + limit]

    def mark_conversation_read(self, conversation: Conversation, user: User):
        """Mark conversation as read for user"""
        conversation.mark_as_read(user)

    def add_participants(self, conversation: Conversation, participants: List[User],
                        added_by: User) -> bool:
        """Add participants to conversation"""

        # Check permissions
        try:
            participant = ConversationParticipant.objects.get(
                conversation=conversation,
                user=added_by
            )
            if not participant.can_add_participants and not participant.is_admin:
                return False
        except ConversationParticipant.DoesNotExist:
            return False

        with transaction.atomic():
            added_users = []

            for user in participants:
                # Don't add if already participant
                if conversation.participants.filter(id=user.id).exists():
                    continue

                ConversationParticipant.objects.create(
                    conversation=conversation,
                    user=user,
                    role='participant'
                )
                added_users.append(user)

            # Send system message
            if added_users:
                names = ', '.join([u.get_short_name() for u in added_users])
                system_message = f"{added_by.get_short_name()} added {names} to the conversation"
                self.send_system_message(conversation, system_message)

        return len(added_users) > 0

    def remove_participant(self, conversation: Conversation, user_to_remove: User,
                          removed_by: User) -> bool:
        """Remove participant from conversation"""

        # Check permissions
        try:
            remover = ConversationParticipant.objects.get(
                conversation=conversation,
                user=removed_by
            )
            if not remover.can_remove_participants and not remover.is_admin:
                return False
        except ConversationParticipant.DoesNotExist:
            return False

        # Users can always remove themselves
        if user_to_remove == removed_by:
            try:
                participant = ConversationParticipant.objects.get(
                    conversation=conversation,
                    user=user_to_remove
                )
                participant.leave_conversation()

                # Send system message
                system_message = f"{user_to_remove.get_short_name()} left the conversation"
                self.send_system_message(conversation, system_message)
                return True

            except ConversationParticipant.DoesNotExist:
                return False

        # Remove other participant
        try:
            participant = ConversationParticipant.objects.get(
                conversation=conversation,
                user=user_to_remove
            )
            participant.leave_conversation()

            # Send system message
            system_message = f"{removed_by.get_short_name()} removed {user_to_remove.get_short_name()}"
            self.send_system_message(conversation, system_message)
            return True

        except ConversationParticipant.DoesNotExist:
            return False

    def create_property_inquiry(self, property_listing, inquirer: User,
                               message_content: str) -> Conversation:
        """Create a conversation for property inquiry"""

        # Get property owner/agent
        property_owner = property_listing.added_by
        if not property_owner:
            # If no owner, this would typically involve an agent or system
            raise ValueError("Property has no owner to contact")

        # Create conversation
        conversation = Conversation.objects.create(
            conversation_type='property_inquiry',
            title=f"Inquiry about {property_listing.title}",
            property_listing=property_listing
        )

        # Add participants
        ConversationParticipant.objects.create(
            conversation=conversation,
            user=inquirer,
            role='participant'
        )

        ConversationParticipant.objects.create(
            conversation=conversation,
            user=property_owner,
            role='admin',
            can_add_participants=True
        )

        # Send initial message
        self.send_message(
            conversation=conversation,
            sender=inquirer,
            content=message_content
        )

        return conversation

    def create_roommate_conversation(self, user1: User, user2: User,
                                   compatibility_score=None) -> Conversation:
        """Create a conversation for roommate matching"""

        conversation = Conversation.objects.create(
            conversation_type='roommate_matching',
            title=f"Roommate Match: {user1.get_short_name()} & {user2.get_short_name()}"
        )

        # Add participants
        ConversationParticipant.objects.create(
            conversation=conversation,
            user=user1,
            role='participant'
        )

        ConversationParticipant.objects.create(
            conversation=conversation,
            user=user2,
            role='participant'
        )

        # Send system message with compatibility info
        if compatibility_score:
            system_message = (
                f"You've been matched as potential roommates! "
                f"Compatibility score: {compatibility_score.overall_score:.0f}% "
                f"({compatibility_score.compatibility_level})"
            )
        else:
            system_message = "You've been matched as potential roommates!"

        self.send_system_message(conversation, system_message)

        return conversation

    def search_messages(self, user: User, query: str, conversation_id: str = None) -> List[Message]:
        """Search messages for a user"""

        base_query = Message.objects.filter(
            conversation__participants=user,
            is_deleted=False,
            content__icontains=query
        )

        if conversation_id:
            base_query = base_query.filter(conversation_id=conversation_id)

        return base_query.select_related(
            'sender', 'conversation'
        ).order_by('-created_at')[:50]

    def get_unread_count(self, user: User) -> int:
        """Get total unread messages count for user"""

        # This is a simplified version - in practice you'd want to optimize this query
        total_unread = 0

        conversations = Conversation.objects.filter(
            participants=user,
            is_active=True
        )

        for conversation in conversations:
            total_unread += conversation.unread_count_for_user(user)

        return total_unread

    def send_notification(self, user: User, notification_type: str, data: Dict):
        """Send real-time notification to user"""
        if not self.channel_layer:
            return

        notification_group_name = f'notifications_{user.id}'

        notification_data = {
            'type': notification_type,
            'data': data,
            'timestamp': timezone.now().isoformat()
        }

        # Send real-time notification if Redis is available
        if self.channel_layer:
            async_to_sync(self.channel_layer.group_send)(
                notification_group_name,
                {
                    'type': 'send_notification',
                    'notification': notification_data
                }
            )

    def invite_to_conversation(self, conversation: Conversation, inviter: User,
                             invitee: User, message: str = '') -> ConversationInvite:
        """Send invitation to join conversation"""

        # Check if inviter has permission
        try:
            inviter_participant = ConversationParticipant.objects.get(
                conversation=conversation,
                user=inviter
            )
            if not inviter_participant.can_add_participants and not inviter_participant.is_admin:
                raise PermissionError("User doesn't have permission to invite")
        except ConversationParticipant.DoesNotExist:
            raise PermissionError("User is not a participant in this conversation")

        # Create invitation
        invite = ConversationInvite.objects.create(
            conversation=conversation,
            inviter=inviter,
            invitee=invitee,
            message=message,
            expires_at=timezone.now() + timedelta(days=7)  # 7-day expiry
        )

        # Send notification to invitee
        self.send_notification(
            user=invitee,
            notification_type='conversation_invite',
            data={
                'invite_id': str(invite.id),
                'conversation_id': str(conversation.id),
                'conversation_title': str(conversation),
                'inviter_name': inviter.get_short_name(),
                'message': message
            }
        )

        return invite