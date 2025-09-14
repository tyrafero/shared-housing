from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.urls import reverse
from django.core.validators import MinValueValidator, MaxValueValidator
import uuid

User = get_user_model()


class RoommateGroup(models.Model):
    """A group of potential roommates looking for housing together"""

    GROUP_STATUS = [
        ('forming', 'Forming'),
        ('active', 'Active'),
        ('house_hunting', 'House Hunting'),
        ('housed', 'Housed'),
        ('disbanded', 'Disbanded'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=200, help_text="Group name")
    description = models.TextField(blank=True, help_text="Group description and goals")

    # Group settings
    max_members = models.PositiveIntegerField(
        default=4,
        validators=[MinValueValidator(2), MaxValueValidator(10)],
        help_text="Maximum number of members"
    )
    min_members = models.PositiveIntegerField(
        default=2,
        validators=[MinValueValidator(2), MaxValueValidator(8)],
        help_text="Minimum number of members to be active"
    )

    # Group preferences
    target_budget_min = models.DecimalField(
        max_digits=8, decimal_places=2,
        null=True, blank=True,
        help_text="Minimum total weekly rent budget"
    )
    target_budget_max = models.DecimalField(
        max_digits=8, decimal_places=2,
        null=True, blank=True,
        help_text="Maximum total weekly rent budget"
    )

    preferred_locations = models.JSONField(
        default=list,
        help_text="Preferred suburbs/locations"
    )

    required_bedrooms = models.PositiveIntegerField(
        null=True, blank=True,
        validators=[MinValueValidator(1), MaxValueValidator(10)],
        help_text="Number of bedrooms needed"
    )

    required_bathrooms = models.PositiveIntegerField(
        null=True, blank=True,
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        help_text="Minimum number of bathrooms"
    )

    move_in_date = models.DateField(null=True, blank=True)
    lease_length_months = models.PositiveIntegerField(
        null=True, blank=True,
        validators=[MinValueValidator(1), MaxValueValidator(24)]
    )

    # Group requirements
    pet_friendly = models.BooleanField(null=True, blank=True)
    smoking_allowed = models.BooleanField(null=True, blank=True)
    furnished_preference = models.CharField(
        max_length=20,
        choices=[
            ('unfurnished', 'Unfurnished'),
            ('semi_furnished', 'Semi-furnished'),
            ('fully_furnished', 'Fully Furnished'),
            ('no_preference', 'No Preference'),
        ],
        default='no_preference'
    )

    # Status and metadata
    status = models.CharField(max_length=20, choices=GROUP_STATUS, default='forming')
    is_private = models.BooleanField(
        default=False,
        help_text="Private groups can only be joined by invitation"
    )
    is_active = models.BooleanField(default=True)

    # Timestamps
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'groups_roommategroup'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status', 'is_active']),
            models.Index(fields=['created_at']),
            models.Index(fields=['max_members']),
        ]

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse('groups:group_detail', kwargs={'group_id': self.id})

    @property
    def current_member_count(self):
        return self.memberships.filter(status='active').count()

    @property
    def is_full(self):
        return self.current_member_count >= self.max_members

    @property
    def needs_members(self):
        return self.current_member_count < self.min_members

    @property
    def available_spots(self):
        return max(0, self.max_members - self.current_member_count)

    @property
    def budget_per_person_min(self):
        if self.target_budget_min and self.current_member_count > 0:
            return self.target_budget_min / self.current_member_count
        return None

    @property
    def budget_per_person_max(self):
        if self.target_budget_max and self.current_member_count > 0:
            return self.target_budget_max / self.current_member_count
        return None

    def can_user_join(self, user):
        """Check if a user can join this group"""
        if self.is_full:
            return False, "Group is full"

        if GroupMembership.objects.filter(group=self, user=user, status__in=['active', 'pending']).exists():
            return False, "User is already a member or has pending request"

        if self.is_private:
            # Check if user has an invitation
            if not GroupInvitation.objects.filter(
                group=self,
                invitee=user,
                status='pending'
            ).exists():
                return False, "This is a private group and you need an invitation"

        return True, "Can join"

    def get_admin_members(self):
        """Get admin members of the group"""
        return User.objects.filter(
            group_memberships__group=self,
            group_memberships__role='admin',
            group_memberships__status='active'
        )

    def get_active_members(self):
        """Get active members of the group"""
        return User.objects.filter(
            group_memberships__group=self,
            group_memberships__status='active'
        ).select_related('profile')


class GroupMembership(models.Model):
    """Membership of a user in a roommate group"""

    MEMBERSHIP_ROLES = [
        ('admin', 'Administrator'),
        ('member', 'Member'),
    ]

    MEMBERSHIP_STATUS = [
        ('pending', 'Pending Approval'),
        ('active', 'Active'),
        ('left', 'Left Group'),
        ('removed', 'Removed'),
    ]

    group = models.ForeignKey(
        RoommateGroup,
        on_delete=models.CASCADE,
        related_name='memberships'
    )
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='group_memberships'
    )

    role = models.CharField(max_length=20, choices=MEMBERSHIP_ROLES, default='member')
    status = models.CharField(max_length=20, choices=MEMBERSHIP_STATUS, default='pending')

    # Join information
    join_reason = models.TextField(blank=True, help_text="Why user wants to join")

    # Permissions
    can_invite_members = models.BooleanField(default=False)
    can_manage_applications = models.BooleanField(default=False)
    can_edit_group = models.BooleanField(default=False)

    # Timestamps
    joined_at = models.DateTimeField(default=timezone.now)
    approved_at = models.DateTimeField(null=True, blank=True)
    left_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'groups_groupmembership'
        unique_together = ['group', 'user']
        indexes = [
            models.Index(fields=['group', 'status']),
            models.Index(fields=['user', 'status']),
        ]

    def __str__(self):
        return f"{self.user.get_short_name()} in {self.group.name}"

    @property
    def is_admin(self):
        return self.role == 'admin'

    def approve_membership(self, approved_by=None):
        """Approve pending membership"""
        if self.status == 'pending':
            self.status = 'active'
            self.approved_at = timezone.now()
            self.save(update_fields=['status', 'approved_at'])
            return True
        return False

    def leave_group(self):
        """Mark membership as left"""
        if self.status == 'active':
            self.status = 'left'
            self.left_at = timezone.now()
            self.save(update_fields=['status', 'left_at'])
            return True
        return False

    def remove_from_group(self, removed_by=None):
        """Remove user from group"""
        if self.status in ['active', 'pending']:
            self.status = 'removed'
            self.left_at = timezone.now()
            self.save(update_fields=['status', 'left_at'])
            return True
        return False


class GroupInvitation(models.Model):
    """Invitation to join a roommate group"""

    INVITATION_STATUS = [
        ('pending', 'Pending'),
        ('accepted', 'Accepted'),
        ('declined', 'Declined'),
        ('expired', 'Expired'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    group = models.ForeignKey(
        RoommateGroup,
        on_delete=models.CASCADE,
        related_name='invitations'
    )
    inviter = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='sent_group_invitations'
    )
    invitee = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='received_group_invitations'
    )

    message = models.TextField(blank=True, help_text="Personal invitation message")
    status = models.CharField(max_length=20, choices=INVITATION_STATUS, default='pending')

    # Timestamps
    created_at = models.DateTimeField(default=timezone.now)
    responded_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(help_text="When this invitation expires")

    class Meta:
        db_table = 'groups_groupinvitation'
        unique_together = ['group', 'invitee']
        indexes = [
            models.Index(fields=['invitee', 'status']),
            models.Index(fields=['group', 'status']),
            models.Index(fields=['expires_at']),
        ]

    def __str__(self):
        return f"Invitation to {self.group.name} for {self.invitee.get_short_name()}"

    @property
    def is_expired(self):
        return timezone.now() > self.expires_at

    @property
    def is_pending(self):
        return self.status == 'pending' and not self.is_expired

    def accept(self):
        """Accept the invitation"""
        if self.status == 'pending' and not self.is_expired:
            # Check if group still has space
            if self.group.is_full:
                return False, "Group is now full"

            self.status = 'accepted'
            self.responded_at = timezone.now()
            self.save(update_fields=['status', 'responded_at'])

            # Create membership
            GroupMembership.objects.create(
                group=self.group,
                user=self.invitee,
                status='active',
                approved_at=timezone.now()
            )

            return True, "Invitation accepted"

        return False, "Invitation is not valid"

    def decline(self):
        """Decline the invitation"""
        if self.status == 'pending':
            self.status = 'declined'
            self.responded_at = timezone.now()
            self.save(update_fields=['status', 'responded_at'])
            return True
        return False


class PropertyApplication(models.Model):
    """Group application for a property"""

    APPLICATION_STATUS = [
        ('draft', 'Draft'),
        ('submitted', 'Submitted'),
        ('under_review', 'Under Review'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('withdrawn', 'Withdrawn'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    group = models.ForeignKey(
        RoommateGroup,
        on_delete=models.CASCADE,
        related_name='property_applications'
    )
    property_listing = models.ForeignKey(
        'properties.Property',
        on_delete=models.CASCADE,
        related_name='group_applications'
    )

    # Application details
    application_message = models.TextField(
        help_text="Message to property owner/agent"
    )
    proposed_move_in_date = models.DateField()
    proposed_lease_length = models.PositiveIntegerField(
        help_text="Proposed lease length in months"
    )

    # Status
    status = models.CharField(max_length=20, choices=APPLICATION_STATUS, default='draft')

    # Voting system for group applications
    votes_required = models.PositiveIntegerField(
        help_text="Number of member votes required to submit"
    )
    votes_received = models.PositiveIntegerField(default=0)

    # Response from property owner/agent
    response_message = models.TextField(blank=True)
    response_date = models.DateTimeField(null=True, blank=True)

    # Timestamps
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    submitted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'groups_propertyapplication'
        unique_together = ['group', 'property_listing']
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['group', 'status']),
            models.Index(fields=['property_listing', 'status']),
            models.Index(fields=['status', 'created_at']),
        ]

    def __str__(self):
        return f"{self.group.name} application for {self.property_listing.title}"

    @property
    def can_be_submitted(self):
        return self.votes_received >= self.votes_required and self.status == 'draft'

    @property
    def remaining_votes_needed(self):
        return max(0, self.votes_required - self.votes_received)

    def submit_application(self):
        """Submit the application if it has enough votes"""
        if self.can_be_submitted:
            self.status = 'submitted'
            self.submitted_at = timezone.now()
            self.save(update_fields=['status', 'submitted_at'])
            return True
        return False


class ApplicationVote(models.Model):
    """Member vote on a property application"""

    VOTE_CHOICES = [
        ('yes', 'Yes'),
        ('no', 'No'),
        ('abstain', 'Abstain'),
    ]

    application = models.ForeignKey(
        PropertyApplication,
        on_delete=models.CASCADE,
        related_name='votes'
    )
    member = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='application_votes'
    )

    vote = models.CharField(max_length=10, choices=VOTE_CHOICES)
    comment = models.TextField(blank=True, help_text="Optional comment with vote")

    # Timestamps
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'groups_applicationvote'
        unique_together = ['application', 'member']

    def __str__(self):
        return f"{self.member.get_short_name()}: {self.vote} on {self.application}"

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)

        # Update vote count on application
        if self.vote == 'yes':
            # Count total 'yes' votes for this application
            yes_votes = ApplicationVote.objects.filter(
                application=self.application,
                vote='yes'
            ).count()

            self.application.votes_received = yes_votes
            self.application.save(update_fields=['votes_received'])


class GroupActivity(models.Model):
    """Track activities within a group"""

    ACTIVITY_TYPES = [
        ('member_joined', 'Member Joined'),
        ('member_left', 'Member Left'),
        ('member_removed', 'Member Removed'),
        ('application_created', 'Application Created'),
        ('application_submitted', 'Application Submitted'),
        ('application_voted', 'Application Vote Cast'),
        ('group_updated', 'Group Updated'),
        ('invitation_sent', 'Invitation Sent'),
    ]

    group = models.ForeignKey(
        RoommateGroup,
        on_delete=models.CASCADE,
        related_name='activities'
    )
    user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        help_text="User who performed the activity"
    )
    activity_type = models.CharField(max_length=30, choices=ACTIVITY_TYPES)
    description = models.TextField(help_text="Description of the activity")

    # Additional data as JSON
    metadata = models.JSONField(default=dict)

    # Timestamps
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = 'groups_groupactivity'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['group', 'created_at']),
            models.Index(fields=['activity_type', 'created_at']),
        ]

    def __str__(self):
        return f"{self.group.name}: {self.get_activity_type_display()}"