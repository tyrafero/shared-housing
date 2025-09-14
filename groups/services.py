from typing import List, Optional, Dict
from datetime import timedelta
from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone
from django.db.models import Q, Count

from .models import (
    RoommateGroup, GroupMembership, GroupInvitation,
    PropertyApplication, ApplicationVote, GroupActivity
)
from messaging.services import MessagingService

User = get_user_model()


class GroupService:
    """Service for managing group functionality"""

    def __init__(self):
        self.messaging_service = MessagingService()

    def create_group(self, creator: User, group_data: Dict) -> RoommateGroup:
        """Create a new roommate group with creator as admin"""

        with transaction.atomic():
            # Create the group
            group = RoommateGroup.objects.create(
                name=group_data['name'],
                description=group_data.get('description', ''),
                max_members=group_data.get('max_members', 4),
                min_members=group_data.get('min_members', 2),
                target_budget_min=group_data.get('target_budget_min'),
                target_budget_max=group_data.get('target_budget_max'),
                preferred_locations=group_data.get('preferred_locations', []),
                required_bedrooms=group_data.get('required_bedrooms'),
                required_bathrooms=group_data.get('required_bathrooms'),
                move_in_date=group_data.get('move_in_date'),
                lease_length_months=group_data.get('lease_length_months'),
                pet_friendly=group_data.get('pet_friendly'),
                smoking_allowed=group_data.get('smoking_allowed'),
                furnished_preference=group_data.get('furnished_preference', 'no_preference'),
                is_private=group_data.get('is_private', False)
            )

            # Create admin membership for creator
            GroupMembership.objects.create(
                group=group,
                user=creator,
                role='admin',
                status='active',
                can_invite_members=True,
                can_manage_applications=True,
                can_edit_group=True
            )

            # Log activity
            self.log_activity(
                group=group,
                user=creator,
                activity_type='member_joined',
                description=f"{creator.get_short_name()} created the group"
            )

            return group

    def join_group(self, user: User, group: RoommateGroup,
                  join_reason: str = '') -> tuple[bool, str]:
        """Request to join a group or join directly if public"""

        # Check eligibility
        can_join, message = group.can_user_join(user)
        if not can_join:
            return False, message

        with transaction.atomic():
            # Create membership request
            status = 'pending' if not group.is_private else 'pending'

            # For public groups with auto-approval (future feature)
            # For now, all joins are pending approval

            membership = GroupMembership.objects.create(
                group=group,
                user=user,
                status=status,
                join_reason=join_reason
            )

            # Log activity
            self.log_activity(
                group=group,
                user=user,
                activity_type='member_joined',
                description=f"{user.get_short_name()} requested to join"
            )

            return True, "Join request submitted successfully"

    def approve_member(self, group: RoommateGroup, user_to_approve: User,
                      approved_by: User) -> tuple[bool, str]:
        """Approve a pending membership"""

        try:
            membership = GroupMembership.objects.get(
                group=group,
                user=user_to_approve,
                status='pending'
            )

            if membership.approve_membership():
                # Log activity
                self.log_activity(
                    group=group,
                    user=approved_by,
                    activity_type='member_joined',
                    description=f"{user_to_approve.get_short_name()} was approved by {approved_by.get_short_name()}"
                )

                # Send welcome notification
                self.messaging_service.send_notification(
                    user=user_to_approve,
                    notification_type='group_membership_approved',
                    data={
                        'group_id': str(group.id),
                        'group_name': group.name,
                        'approved_by': approved_by.get_short_name()
                    }
                )

                return True, f"{user_to_approve.get_short_name()} approved successfully"
            else:
                return False, "Failed to approve member"

        except GroupMembership.DoesNotExist:
            return False, "Membership request not found"

    def invite_user(self, group: RoommateGroup, inviter: User,
                   invitee_email: str, message: str = '') -> tuple[bool, str]:
        """Send invitation to join group"""

        try:
            invitee = User.objects.get(email=invitee_email, is_active=True)
        except User.DoesNotExist:
            return False, "User not found"

        # Check if user is already invited or member
        if GroupInvitation.objects.filter(
            group=group,
            invitee=invitee,
            status='pending'
        ).exists():
            return False, "User already has a pending invitation"

        if GroupMembership.objects.filter(
            group=group,
            user=invitee,
            status__in=['active', 'pending']
        ).exists():
            return False, "User is already a member or has pending request"

        # Create invitation
        invitation = GroupInvitation.objects.create(
            group=group,
            inviter=inviter,
            invitee=invitee,
            message=message,
            expires_at=timezone.now() + timedelta(days=7)  # 7-day expiry
        )

        # Log activity
        self.log_activity(
            group=group,
            user=inviter,
            activity_type='invitation_sent',
            description=f"Invited {invitee.get_short_name()}"
        )

        # Send notification
        self.messaging_service.send_notification(
            user=invitee,
            notification_type='group_invitation',
            data={
                'invitation_id': str(invitation.id),
                'group_name': group.name,
                'inviter_name': inviter.get_short_name(),
                'message': message
            }
        )

        return True, f"Invitation sent to {invitee.get_short_name()}"

    def create_property_application(self, group: RoommateGroup, property_listing,
                                  applicant: User, application_data: Dict) -> PropertyApplication:
        """Create a property application for the group"""

        with transaction.atomic():
            application = PropertyApplication.objects.create(
                group=group,
                property_listing=property_listing,
                application_message=application_data['application_message'],
                proposed_move_in_date=application_data['proposed_move_in_date'],
                proposed_lease_length=application_data['proposed_lease_length'],
                votes_required=group.current_member_count
            )

            # Auto-vote for the applicant
            ApplicationVote.objects.create(
                application=application,
                member=applicant,
                vote='yes',
                comment='Application created'
            )

            # Log activity
            self.log_activity(
                group=group,
                user=applicant,
                activity_type='application_created',
                description=f"Applied for {property_listing.title}",
                metadata={'property_id': property_listing.id}
            )

            # Notify other members
            active_members = group.get_active_members().exclude(id=applicant.id)
            for member in active_members:
                self.messaging_service.send_notification(
                    user=member,
                    notification_type='new_property_application',
                    data={
                        'group_name': group.name,
                        'property_title': property_listing.title,
                        'applicant_name': applicant.get_short_name(),
                        'application_id': str(application.id)
                    }
                )

            return application

    def vote_on_application(self, application: PropertyApplication, voter: User,
                          vote_value: str, comment: str = '') -> tuple[bool, str]:
        """Vote on a property application"""

        if vote_value not in ['yes', 'no', 'abstain']:
            return False, "Invalid vote value"

        with transaction.atomic():
            # Update or create vote
            vote, created = ApplicationVote.objects.update_or_create(
                application=application,
                member=voter,
                defaults={
                    'vote': vote_value,
                    'comment': comment
                }
            )

            # Log activity
            self.log_activity(
                group=application.group,
                user=voter,
                activity_type='application_voted',
                description=f"Voted {vote_value} on {application.property_listing.title}",
                metadata={'application_id': str(application.id), 'vote': vote_value}
            )

            return True, "Vote recorded successfully"

    def submit_application(self, application: PropertyApplication,
                         submitted_by: User) -> tuple[bool, str]:
        """Submit application to property owner"""

        if not application.can_be_submitted:
            return False, "Application doesn't have enough votes"

        if application.submit_application():
            # Log activity
            self.log_activity(
                group=application.group,
                user=submitted_by,
                activity_type='application_submitted',
                description=f"Submitted application for {application.property_listing.title}",
                metadata={'application_id': str(application.id)}
            )

            # Notify group members
            active_members = application.group.get_active_members()
            for member in active_members:
                self.messaging_service.send_notification(
                    user=member,
                    notification_type='application_submitted',
                    data={
                        'group_name': application.group.name,
                        'property_title': application.property_listing.title,
                        'submitted_by': submitted_by.get_short_name(),
                        'application_id': str(application.id)
                    }
                )

            return True, "Application submitted successfully"
        else:
            return False, "Failed to submit application"

    def leave_group(self, group: RoommateGroup, user: User) -> tuple[bool, str]:
        """Remove user from group with proper admin handling"""

        try:
            membership = GroupMembership.objects.get(
                group=group,
                user=user,
                status='active'
            )

            with transaction.atomic():
                # Check if user is the only admin
                if membership.is_admin:
                    admin_count = GroupMembership.objects.filter(
                        group=group,
                        role='admin',
                        status='active'
                    ).count()

                    if admin_count == 1:
                        # Transfer admin to another member
                        other_members = GroupMembership.objects.filter(
                            group=group,
                            status='active'
                        ).exclude(user=user)

                        if other_members.exists():
                            # Promote most senior member to admin
                            new_admin = other_members.order_by('joined_at').first()
                            new_admin.role = 'admin'
                            new_admin.can_edit_group = True
                            new_admin.can_invite_members = True
                            new_admin.can_manage_applications = True
                            new_admin.save()

                            self.log_activity(
                                group=group,
                                user=user,
                                activity_type='member_left',
                                description=f"{new_admin.user.get_short_name()} promoted to admin"
                            )
                        else:
                            # Last member - deactivate group
                            group.is_active = False
                            group.status = 'disbanded'
                            group.save()

                            self.log_activity(
                                group=group,
                                user=user,
                                activity_type='member_left',
                                description="Group disbanded - last member left"
                            )

                membership.leave_group()

                # Log activity
                self.log_activity(
                    group=group,
                    user=user,
                    activity_type='member_left',
                    description=f"{user.get_short_name()} left the group"
                )

                return True, "Successfully left the group"

        except GroupMembership.DoesNotExist:
            return False, "You are not a member of this group"

    def get_group_recommendations(self, user: User, limit: int = 10) -> List[RoommateGroup]:
        """Get group recommendations for a user based on their profile"""

        try:
            user_profile = user.profile
        except:
            # No profile - return active groups
            return RoommateGroup.objects.filter(
                is_active=True,
                status='forming'
            ).exclude(
                memberships__user=user
            )[:limit]

        # Basic filtering based on user preferences
        groups = RoommateGroup.objects.filter(
            is_active=True,
            status__in=['forming', 'active']
        ).exclude(
            memberships__user=user  # Exclude groups user is already in
        )

        # Filter by budget if available
        if hasattr(user_profile, 'budget_min') and user_profile.budget_min:
            groups = groups.filter(
                Q(target_budget_min__lte=user_profile.budget_max) |
                Q(target_budget_min__isnull=True)
            )

        if hasattr(user_profile, 'budget_max') and user_profile.budget_max:
            groups = groups.filter(
                Q(target_budget_max__gte=user_profile.budget_min) |
                Q(target_budget_max__isnull=True)
            )

        # Filter by location preferences if available
        if hasattr(user_profile, 'preferred_locations') and user_profile.preferred_locations:
            location_q = Q()
            for location in user_profile.preferred_locations:
                location_q |= Q(preferred_locations__icontains=location)
            groups = groups.filter(location_q)

        return groups.annotate(
            member_count=Count('memberships', filter=Q(memberships__status='active'))
        ).order_by('-created_at')[:limit]

    def log_activity(self, group: RoommateGroup, user: User, activity_type: str,
                    description: str, metadata: Dict = None):
        """Log group activity"""

        GroupActivity.objects.create(
            group=group,
            user=user,
            activity_type=activity_type,
            description=description,
            metadata=metadata or {}
        )

    def get_user_groups(self, user: User) -> List[GroupMembership]:
        """Get all groups user belongs to"""

        return GroupMembership.objects.filter(
            user=user,
            status='active'
        ).select_related('group').order_by('-joined_at')

    def get_pending_invitations(self, user: User) -> List[GroupInvitation]:
        """Get pending invitations for user"""

        return GroupInvitation.objects.filter(
            invitee=user,
            status='pending'
        ).select_related('group', 'inviter').order_by('-created_at')

    def cleanup_expired_invitations(self):
        """Cleanup expired invitations (to be run as a periodic task)"""

        expired_invitations = GroupInvitation.objects.filter(
            status='pending',
            expires_at__lt=timezone.now()
        )

        count = expired_invitations.update(status='expired')
        return count