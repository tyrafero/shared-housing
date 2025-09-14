from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from .models import (
    RoommateGroup, GroupMembership, GroupInvitation,
    PropertyApplication, ApplicationVote, GroupActivity
)


@admin.register(RoommateGroup)
class RoommateGroupAdmin(admin.ModelAdmin):
    list_display = [
        'name', 'status', 'current_member_count', 'max_members',
        'available_spots', 'is_private', 'created_at'
    ]
    list_filter = ['status', 'is_private', 'is_active', 'created_at']
    search_fields = ['name', 'description', 'preferred_locations']
    readonly_fields = ['id', 'current_member_count', 'available_spots', 'created_at', 'updated_at']

    fieldsets = (
        ('Basic Information', {
            'fields': ('id', 'name', 'description', 'status', 'is_private', 'is_active')
        }),
        ('Group Size', {
            'fields': ('max_members', 'min_members', 'current_member_count', 'available_spots')
        }),
        ('Budget & Preferences', {
            'fields': (
                'target_budget_min', 'target_budget_max',
                'preferred_locations', 'required_bedrooms', 'required_bathrooms'
            ),
            'classes': ['collapse']
        }),
        ('Housing Details', {
            'fields': (
                'move_in_date', 'lease_length_months',
                'pet_friendly', 'smoking_allowed', 'furnished_preference'
            ),
            'classes': ['collapse']
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ['collapse']
        })
    )

    def current_member_count(self, obj):
        return obj.current_member_count
    current_member_count.short_description = 'Members'

    def available_spots(self, obj):
        spots = obj.available_spots
        if spots == 0:
            return format_html('<span style="color: red;">Full</span>')
        return spots
    available_spots.short_description = 'Available Spots'


class GroupMembershipInline(admin.TabularInline):
    model = GroupMembership
    extra = 0
    readonly_fields = ['joined_at', 'approved_at', 'left_at']
    fields = [
        'user', 'role', 'status', 'can_invite_members',
        'can_manage_applications', 'can_edit_group'
    ]


@admin.register(GroupMembership)
class GroupMembershipAdmin(admin.ModelAdmin):
    list_display = [
        'user', 'group', 'role', 'status',
        'joined_at', 'approved_at'
    ]
    list_filter = ['role', 'status', 'joined_at']
    search_fields = [
        'user__email', 'user__first_name', 'user__last_name',
        'group__name'
    ]
    readonly_fields = ['joined_at', 'approved_at', 'left_at']

    fieldsets = (
        ('Membership Details', {
            'fields': ('group', 'user', 'role', 'status', 'join_reason')
        }),
        ('Permissions', {
            'fields': (
                'can_invite_members', 'can_manage_applications',
                'can_edit_group'
            )
        }),
        ('Timestamps', {
            'fields': ('joined_at', 'approved_at', 'left_at')
        })
    )


@admin.register(GroupInvitation)
class GroupInvitationAdmin(admin.ModelAdmin):
    list_display = [
        'group', 'invitee', 'inviter', 'status',
        'created_at', 'expires_at', 'is_expired'
    ]
    list_filter = ['status', 'created_at', 'expires_at']
    search_fields = [
        'group__name', 'inviter__email', 'invitee__email'
    ]
    readonly_fields = ['id', 'is_expired', 'created_at', 'responded_at']

    def is_expired(self, obj):
        if obj.is_expired:
            return format_html('<span style="color: red;">Yes</span>')
        return format_html('<span style="color: green;">No</span>')
    is_expired.short_description = 'Expired'


class ApplicationVoteInline(admin.TabularInline):
    model = ApplicationVote
    extra = 0
    readonly_fields = ['created_at', 'updated_at']


@admin.register(PropertyApplication)
class PropertyApplicationAdmin(admin.ModelAdmin):
    list_display = [
        'group', 'property_listing', 'status',
        'votes_received', 'votes_required',
        'remaining_votes_needed', 'created_at'
    ]
    list_filter = ['status', 'created_at', 'submitted_at']
    search_fields = [
        'group__name', 'property_listing__title',
        'application_message'
    ]
    readonly_fields = [
        'id', 'remaining_votes_needed', 'can_be_submitted',
        'created_at', 'updated_at', 'submitted_at'
    ]
    inlines = [ApplicationVoteInline]

    fieldsets = (
        ('Application Details', {
            'fields': (
                'id', 'group', 'property_listing', 'status',
                'application_message'
            )
        }),
        ('Proposal', {
            'fields': (
                'proposed_move_in_date', 'proposed_lease_length'
            )
        }),
        ('Voting', {
            'fields': (
                'votes_required', 'votes_received',
                'remaining_votes_needed', 'can_be_submitted'
            )
        }),
        ('Response', {
            'fields': ('response_message', 'response_date'),
            'classes': ['collapse']
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at', 'submitted_at'),
            'classes': ['collapse']
        })
    )

    def remaining_votes_needed(self, obj):
        remaining = obj.remaining_votes_needed
        if remaining == 0:
            return format_html('<span style="color: green;">Ready to submit</span>')
        return remaining
    remaining_votes_needed.short_description = 'Votes Needed'

    def can_be_submitted(self, obj):
        if obj.can_be_submitted:
            return format_html('<span style="color: green;">Yes</span>')
        return format_html('<span style="color: red;">No</span>')
    can_be_submitted.short_description = 'Can Submit'


@admin.register(ApplicationVote)
class ApplicationVoteAdmin(admin.ModelAdmin):
    list_display = [
        'member', 'application', 'vote', 'created_at'
    ]
    list_filter = ['vote', 'created_at']
    search_fields = [
        'member__email', 'member__first_name', 'member__last_name',
        'application__group__name'
    ]
    readonly_fields = ['created_at', 'updated_at']


@admin.register(GroupActivity)
class GroupActivityAdmin(admin.ModelAdmin):
    list_display = [
        'group', 'activity_type', 'user', 'created_at'
    ]
    list_filter = ['activity_type', 'created_at']
    search_fields = [
        'group__name', 'user__email', 'description'
    ]
    readonly_fields = ['created_at']

    fieldsets = (
        ('Activity Details', {
            'fields': ('group', 'user', 'activity_type', 'description')
        }),
        ('Metadata', {
            'fields': ('metadata',),
            'classes': ['collapse']
        }),
        ('Timestamp', {
            'fields': ('created_at',)
        })
    )


# Add inline to RoommateGroupAdmin for better management
RoommateGroupAdmin.inlines = [GroupMembershipInline]
