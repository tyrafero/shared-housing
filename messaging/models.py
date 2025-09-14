from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.urls import reverse
import uuid

User = get_user_model()


class Conversation(models.Model):
    """A conversation between users"""

    CONVERSATION_TYPES = [
        ('direct', 'Direct Message'),
        ('group', 'Group Chat'),
        ('property_inquiry', 'Property Inquiry'),
        ('roommate_matching', 'Roommate Matching'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    conversation_type = models.CharField(max_length=20, choices=CONVERSATION_TYPES, default='direct')

    # Participants
    participants = models.ManyToManyField(
        User,
        related_name='conversations',
        through='ConversationParticipant'
    )

    # Conversation metadata
    title = models.CharField(
        max_length=200,
        blank=True,
        help_text="Optional title for group conversations"
    )
    description = models.TextField(blank=True)

    # Related objects
    property_listing = models.ForeignKey(
        'properties.Property',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='conversations',
        help_text="Property this conversation is about (if applicable)"
    )

    # Status
    is_active = models.BooleanField(default=True)
    is_archived = models.BooleanField(default=False)

    # Timestamps
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    last_message_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'messaging_conversation'
        ordering = ['-last_message_at', '-created_at']
        indexes = [
            models.Index(fields=['conversation_type', 'is_active']),
            models.Index(fields=['last_message_at']),
            models.Index(fields=['created_at']),
        ]

    def __str__(self):
        if self.title:
            return self.title

        if self.conversation_type == 'direct':
            participants = list(self.participants.all()[:2])
            if len(participants) == 2:
                return f"{participants[0].get_short_name()} & {participants[1].get_short_name()}"

        return f"{self.get_conversation_type_display()} - {self.created_at.strftime('%Y-%m-%d')}"

    def get_absolute_url(self):
        return reverse('messaging:conversation_detail', kwargs={'conversation_id': self.id})

    @property
    def participant_count(self):
        return self.participants.count()

    def unread_count_for_user(self, user):
        """Get unread message count for a specific user"""
        participant = self.participants.filter(id=user.id).first()
        if not participant:
            return 0

        try:
            participant_obj = ConversationParticipant.objects.get(
                conversation=self,
                user=user
            )
        except ConversationParticipant.DoesNotExist:
            return 0

        if not participant_obj.last_read_at:
            return self.messages.count()

        return self.messages.filter(
            created_at__gt=participant_obj.last_read_at
        ).count()

    def mark_as_read(self, user):
        """Mark conversation as read for a user"""
        participant, created = ConversationParticipant.objects.get_or_create(
            conversation=self,
            user=user,
            defaults={'last_read_at': timezone.now()}
        )
        if not created:
            participant.last_read_at = timezone.now()
            participant.save(update_fields=['last_read_at'])

    @classmethod
    def get_or_create_direct_conversation(cls, user1, user2):
        """Get or create a direct conversation between two users"""
        # Find existing conversation between these users
        conversation = cls.objects.filter(
            conversation_type='direct',
            participants=user1
        ).filter(
            participants=user2
        ).annotate(
            participant_count=models.Count('participants')
        ).filter(
            participant_count=2
        ).first()

        if conversation:
            return conversation, False

        # Create new conversation
        conversation = cls.objects.create(
            conversation_type='direct'
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

        return conversation, True


class ConversationParticipant(models.Model):
    """Participant in a conversation with specific permissions and metadata"""

    PARTICIPANT_ROLES = [
        ('admin', 'Administrator'),
        ('moderator', 'Moderator'),
        ('participant', 'Participant'),
    ]

    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    role = models.CharField(max_length=20, choices=PARTICIPANT_ROLES, default='participant')

    # Participation metadata
    joined_at = models.DateTimeField(default=timezone.now)
    left_at = models.DateTimeField(null=True, blank=True)
    last_read_at = models.DateTimeField(null=True, blank=True)

    # Permissions
    can_add_participants = models.BooleanField(default=False)
    can_remove_participants = models.BooleanField(default=False)
    can_edit_conversation = models.BooleanField(default=False)

    # Status
    is_active = models.BooleanField(default=True)
    is_muted = models.BooleanField(default=False)
    is_pinned = models.BooleanField(default=False)

    class Meta:
        db_table = 'messaging_conversationparticipant'
        unique_together = ['conversation', 'user']
        indexes = [
            models.Index(fields=['user', 'is_active']),
            models.Index(fields=['conversation', 'joined_at']),
        ]

    def __str__(self):
        return f"{self.user.get_short_name()} in {self.conversation}"

    @property
    def is_admin(self):
        return self.role == 'admin'

    def leave_conversation(self):
        """Mark participant as having left the conversation"""
        self.is_active = False
        self.left_at = timezone.now()
        self.save(update_fields=['is_active', 'left_at'])


class Message(models.Model):
    """Individual message in a conversation"""

    MESSAGE_TYPES = [
        ('text', 'Text Message'),
        ('image', 'Image'),
        ('file', 'File'),
        ('system', 'System Message'),
        ('property_share', 'Property Share'),
        ('profile_share', 'Profile Share'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    conversation = models.ForeignKey(
        Conversation,
        on_delete=models.CASCADE,
        related_name='messages'
    )
    sender = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='sent_messages'
    )

    # Message content
    message_type = models.CharField(max_length=20, choices=MESSAGE_TYPES, default='text')
    content = models.TextField(help_text="Message content or system message text")

    # File attachments
    attachment = models.FileField(
        upload_to='messaging/attachments/%Y/%m/',
        null=True, blank=True
    )
    attachment_name = models.CharField(max_length=255, blank=True)
    attachment_size = models.PositiveIntegerField(null=True, blank=True)

    # Related objects (for sharing)
    shared_property = models.ForeignKey(
        'properties.Property',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        help_text="Property being shared in this message"
    )
    shared_profile = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='profile_shares',
        help_text="User profile being shared in this message"
    )

    # Message metadata
    reply_to = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='replies'
    )

    # Status
    is_edited = models.BooleanField(default=False)
    is_deleted = models.BooleanField(default=False)
    deleted_at = models.DateTimeField(null=True, blank=True)

    # Timestamps
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'messaging_message'
        ordering = ['created_at']
        indexes = [
            models.Index(fields=['conversation', 'created_at']),
            models.Index(fields=['sender', 'created_at']),
            models.Index(fields=['message_type']),
            models.Index(fields=['created_at']),
        ]

    def __str__(self):
        sender_name = self.sender.get_short_name() if self.sender else 'System'
        content_preview = self.content[:50] + '...' if len(self.content) > 50 else self.content
        return f"{sender_name}: {content_preview}"

    def save(self, *args, **kwargs):
        is_new = self._state.adding
        super().save(*args, **kwargs)

        # Update conversation's last_message_at
        if is_new and not self.is_deleted:
            self.conversation.last_message_at = self.created_at
            self.conversation.save(update_fields=['last_message_at'])

    def soft_delete(self):
        """Soft delete the message"""
        self.is_deleted = True
        self.deleted_at = timezone.now()
        self.save(update_fields=['is_deleted', 'deleted_at'])

    @property
    def is_system_message(self):
        return self.message_type == 'system'

    @property
    def has_attachment(self):
        return bool(self.attachment)

    @property
    def attachment_type(self):
        if not self.attachment:
            return None

        ext = self.attachment.name.split('.')[-1].lower()

        if ext in ['jpg', 'jpeg', 'png', 'gif', 'webp']:
            return 'image'
        elif ext in ['pdf']:
            return 'pdf'
        elif ext in ['doc', 'docx']:
            return 'document'
        else:
            return 'file'


class MessageReaction(models.Model):
    """Reactions to messages (like, love, etc.)"""

    REACTION_TYPES = [
        ('like', '👍'),
        ('love', '❤️'),
        ('laugh', '😂'),
        ('wow', '😮'),
        ('sad', '😢'),
        ('angry', '😠'),
    ]

    message = models.ForeignKey(
        Message,
        on_delete=models.CASCADE,
        related_name='reactions'
    )
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='message_reactions'
    )
    reaction_type = models.CharField(max_length=10, choices=REACTION_TYPES)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = 'messaging_messagereaction'
        unique_together = ['message', 'user', 'reaction_type']
        indexes = [
            models.Index(fields=['message', 'reaction_type']),
            models.Index(fields=['user', 'created_at']),
        ]

    def __str__(self):
        return f"{self.user.get_short_name()} {self.get_reaction_type_display()} on message"


class MessageReadReceipt(models.Model):
    """Track when users read messages"""

    message = models.ForeignKey(
        Message,
        on_delete=models.CASCADE,
        related_name='read_receipts'
    )
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='message_reads'
    )
    read_at = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = 'messaging_messagereadreceipt'
        unique_together = ['message', 'user']
        indexes = [
            models.Index(fields=['message', 'read_at']),
            models.Index(fields=['user', 'read_at']),
        ]

    def __str__(self):
        return f"{self.user.get_short_name()} read message at {self.read_at}"


class ConversationInvite(models.Model):
    """Invitations to join conversations"""

    INVITE_STATUS = [
        ('pending', 'Pending'),
        ('accepted', 'Accepted'),
        ('declined', 'Declined'),
        ('expired', 'Expired'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    conversation = models.ForeignKey(
        Conversation,
        on_delete=models.CASCADE,
        related_name='invites'
    )
    inviter = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='sent_conversation_invites'
    )
    invitee = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='received_conversation_invites'
    )

    message = models.TextField(blank=True, help_text="Optional invitation message")
    status = models.CharField(max_length=10, choices=INVITE_STATUS, default='pending')

    # Timestamps
    created_at = models.DateTimeField(default=timezone.now)
    responded_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(help_text="When this invite expires")

    class Meta:
        db_table = 'messaging_conversationinvite'
        unique_together = ['conversation', 'invitee']
        indexes = [
            models.Index(fields=['invitee', 'status']),
            models.Index(fields=['status', 'expires_at']),
            models.Index(fields=['created_at']),
        ]

    def __str__(self):
        return f"Invite to {self.conversation} for {self.invitee.get_short_name()}"

    def accept(self):
        """Accept the invitation"""
        if self.status == 'pending':
            self.status = 'accepted'
            self.responded_at = timezone.now()
            self.save(update_fields=['status', 'responded_at'])

            # Add user to conversation
            ConversationParticipant.objects.get_or_create(
                conversation=self.conversation,
                user=self.invitee,
                defaults={'role': 'participant'}
            )

            return True
        return False

    def decline(self):
        """Decline the invitation"""
        if self.status == 'pending':
            self.status = 'declined'
            self.responded_at = timezone.now()
            self.save(update_fields=['status', 'responded_at'])
            return True
        return False

    @property
    def is_expired(self):
        return timezone.now() > self.expires_at

    @property
    def is_pending(self):
        return self.status == 'pending' and not self.is_expired