from django.contrib import admin
from django.utils.html import format_html
from django.utils import timezone
from django.db.models import Count, Q
from .models import (
    Conversation, ConversationParticipant, Message, MessageReaction,
    MessageReadReceipt, ConversationInvite
)


class ConversationParticipantInline(admin.TabularInline):
    model = ConversationParticipant
    extra = 0
    fields = ('user', 'role', 'joined_at', 'last_read_at', 'is_active', 'is_muted', 'is_pinned')
    readonly_fields = ('joined_at',)


class MessageInline(admin.TabularInline):
    model = Message
    extra = 0
    fields = ('sender', 'message_type', 'content', 'created_at', 'is_deleted')
    readonly_fields = ('created_at',)
    ordering = ['-created_at']

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('sender')[:10]  # Show latest 10


@admin.register(Conversation)
class ConversationAdmin(admin.ModelAdmin):
    list_display = (
        'conversation_display', 'conversation_type', 'participant_count',
        'message_count', 'last_message_at', 'is_active', 'created_at'
    )
    list_filter = (
        'conversation_type', 'is_active', 'is_archived',
        'created_at', 'last_message_at'
    )
    search_fields = ('title', 'description', 'participants__email', 'participants__first_name')
    readonly_fields = ('id', 'created_at', 'updated_at', 'last_message_at', 'participant_count', 'message_count')
    date_hierarchy = 'created_at'

    fieldsets = (
        ('Basic Information', {
            'fields': ('id', 'conversation_type', 'title', 'description')
        }),
        ('Related Objects', {
            'fields': ('property_listing',),
            'classes': ('collapse',)
        }),
        ('Status', {
            'fields': ('is_active', 'is_archived')
        }),
        ('Statistics', {
            'fields': ('participant_count', 'message_count', 'last_message_at'),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )

    inlines = [ConversationParticipantInline, MessageInline]

    def conversation_display(self, obj):
        return str(obj)
    conversation_display.short_description = 'Conversation'

    def participant_count(self, obj):
        return obj.participants.count()
    participant_count.short_description = 'Participants'

    def message_count(self, obj):
        return obj.messages.count()
    message_count.short_description = 'Messages'

    def get_queryset(self, request):
        return super().get_queryset(request).prefetch_related('participants').select_related('property_listing')


@admin.register(ConversationParticipant)
class ConversationParticipantAdmin(admin.ModelAdmin):
    list_display = (
        'user', 'conversation_display', 'role', 'joined_at',
        'last_read_at', 'status_badges', 'permissions_summary'
    )
    list_filter = (
        'role', 'is_active', 'is_muted', 'is_pinned',
        'joined_at', 'conversation__conversation_type'
    )
    search_fields = (
        'user__email', 'user__first_name', 'user__last_name',
        'conversation__title'
    )
    readonly_fields = ('joined_at', 'left_at')
    date_hierarchy = 'joined_at'

    fieldsets = (
        ('Participant Info', {
            'fields': ('conversation', 'user', 'role')
        }),
        ('Permissions', {
            'fields': ('can_add_participants', 'can_remove_participants', 'can_edit_conversation')
        }),
        ('Status & Preferences', {
            'fields': ('is_active', 'is_muted', 'is_pinned')
        }),
        ('Timestamps', {
            'fields': ('joined_at', 'left_at', 'last_read_at')
        })
    )

    def conversation_display(self, obj):
        return str(obj.conversation)
    conversation_display.short_description = 'Conversation'

    def status_badges(self, obj):
        badges = []
        if not obj.is_active:
            badges.append('<span class="badge badge-secondary">Inactive</span>')
        if obj.is_muted:
            badges.append('<span class="badge badge-warning">Muted</span>')
        if obj.is_pinned:
            badges.append('<span class="badge badge-info">Pinned</span>')
        if obj.is_admin:
            badges.append('<span class="badge badge-success">Admin</span>')
        return format_html(' '.join(badges)) if badges else '-'
    status_badges.short_description = 'Status'

    def permissions_summary(self, obj):
        perms = []
        if obj.can_add_participants:
            perms.append('Add')
        if obj.can_remove_participants:
            perms.append('Remove')
        if obj.can_edit_conversation:
            perms.append('Edit')
        return ', '.join(perms) if perms else 'None'
    permissions_summary.short_description = 'Permissions'

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user', 'conversation')


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = (
        'sender', 'conversation_display', 'message_type',
        'content_preview', 'reactions_count', 'created_at',
        'status_badges'
    )
    list_filter = (
        'message_type', 'is_edited', 'is_deleted',
        'created_at', 'conversation__conversation_type'
    )
    search_fields = (
        'content', 'sender__email', 'sender__first_name',
        'conversation__title'
    )
    readonly_fields = (
        'id', 'created_at', 'updated_at', 'reactions_count',
        'replies_count', 'attachment_type'
    )
    date_hierarchy = 'created_at'

    fieldsets = (
        ('Message Info', {
            'fields': ('id', 'conversation', 'sender', 'message_type')
        }),
        ('Content', {
            'fields': ('content', 'reply_to')
        }),
        ('Attachments', {
            'fields': ('attachment', 'attachment_name', 'attachment_size', 'attachment_type'),
            'classes': ('collapse',)
        }),
        ('Shared Objects', {
            'fields': ('shared_property', 'shared_profile'),
            'classes': ('collapse',)
        }),
        ('Status', {
            'fields': ('is_edited', 'is_deleted', 'deleted_at')
        }),
        ('Statistics', {
            'fields': ('reactions_count', 'replies_count'),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at')
        })
    )

    def conversation_display(self, obj):
        return str(obj.conversation)
    conversation_display.short_description = 'Conversation'

    def content_preview(self, obj):
        if obj.is_deleted:
            return format_html('<em class="text-muted">Deleted message</em>')

        preview = obj.content[:100] + '...' if len(obj.content) > 100 else obj.content

        if obj.message_type == 'text':
            return preview
        else:
            return format_html('<strong>{}</strong>: {}', obj.get_message_type_display(), preview)
    content_preview.short_description = 'Content'

    def reactions_count(self, obj):
        return obj.reactions.count()
    reactions_count.short_description = 'Reactions'

    def replies_count(self, obj):
        return obj.replies.count()
    replies_count.short_description = 'Replies'

    def status_badges(self, obj):
        badges = []
        if obj.is_system_message:
            badges.append('<span class="badge badge-info">System</span>')
        if obj.is_edited:
            badges.append('<span class="badge badge-warning">Edited</span>')
        if obj.is_deleted:
            badges.append('<span class="badge badge-danger">Deleted</span>')
        if obj.has_attachment:
            badges.append('<span class="badge badge-success">Attachment</span>')
        return format_html(' '.join(badges)) if badges else '-'
    status_badges.short_description = 'Status'

    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            'sender', 'conversation', 'reply_to', 'shared_property', 'shared_profile'
        ).prefetch_related('reactions')


@admin.register(MessageReaction)
class MessageReactionAdmin(admin.ModelAdmin):
    list_display = (
        'user', 'message_preview', 'reaction_emoji',
        'reaction_type', 'created_at'
    )
    list_filter = ('reaction_type', 'created_at')
    search_fields = (
        'user__email', 'user__first_name',
        'message__content'
    )
    readonly_fields = ('created_at',)
    date_hierarchy = 'created_at'

    def message_preview(self, obj):
        content = obj.message.content[:50] + '...' if len(obj.message.content) > 50 else obj.message.content
        return f"{obj.message.sender.get_short_name() if obj.message.sender else 'System'}: {content}"
    message_preview.short_description = 'Message'

    def reaction_emoji(self, obj):
        return dict(obj.REACTION_TYPES)[obj.reaction_type]
    reaction_emoji.short_description = 'Emoji'

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user', 'message__sender')


@admin.register(MessageReadReceipt)
class MessageReadReceiptAdmin(admin.ModelAdmin):
    list_display = ('user', 'message_preview', 'read_at')
    list_filter = ('read_at',)
    search_fields = (
        'user__email', 'user__first_name',
        'message__content'
    )
    readonly_fields = ('read_at',)
    date_hierarchy = 'read_at'

    def message_preview(self, obj):
        content = obj.message.content[:50] + '...' if len(obj.message.content) > 50 else obj.message.content
        return f"{obj.message.sender.get_short_name() if obj.message.sender else 'System'}: {content}"
    message_preview.short_description = 'Message'

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user', 'message__sender')


@admin.register(ConversationInvite)
class ConversationInviteAdmin(admin.ModelAdmin):
    list_display = (
        'invitee', 'conversation_display', 'inviter',
        'status', 'created_at', 'expires_at', 'status_info'
    )
    list_filter = ('status', 'created_at', 'expires_at')
    search_fields = (
        'invitee__email', 'invitee__first_name',
        'inviter__email', 'inviter__first_name',
        'conversation__title'
    )
    readonly_fields = ('id', 'created_at', 'responded_at', 'is_expired', 'is_pending')
    date_hierarchy = 'created_at'

    fieldsets = (
        ('Invitation Details', {
            'fields': ('id', 'conversation', 'inviter', 'invitee')
        }),
        ('Message', {
            'fields': ('message',)
        }),
        ('Status', {
            'fields': ('status', 'is_pending', 'is_expired')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'responded_at', 'expires_at')
        })
    )

    def conversation_display(self, obj):
        return str(obj.conversation)
    conversation_display.short_description = 'Conversation'

    def status_info(self, obj):
        if obj.is_expired:
            return format_html('<span class="badge badge-danger">Expired</span>')
        elif obj.status == 'pending':
            return format_html('<span class="badge badge-warning">Pending</span>')
        elif obj.status == 'accepted':
            return format_html('<span class="badge badge-success">Accepted</span>')
        elif obj.status == 'declined':
            return format_html('<span class="badge badge-secondary">Declined</span>')
        return obj.get_status_display()
    status_info.short_description = 'Status Info'

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('inviter', 'invitee', 'conversation')