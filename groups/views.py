from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth import get_user_model
from django.http import JsonResponse, Http404
from django.views.decorators.http import require_http_methods, require_POST
from django.contrib import messages
from django.db.models import Q, Count
from django.core.paginator import Paginator
from django.utils import timezone
from datetime import timedelta
import json

from .models import (
    RoommateGroup, GroupMembership, GroupInvitation,
    PropertyApplication, ApplicationVote, GroupActivity
)
from .forms import (
    CreateGroupForm, EditGroupForm, JoinGroupForm,
    InviteMembersForm, PropertyApplicationForm, VoteForm
)
from properties.models import Property
from messaging.services import MessagingService

User = get_user_model()


@login_required
def group_list(request):
    """List all available groups"""
    groups = RoommateGroup.objects.filter(
        is_active=True,
        status__in=['forming', 'active', 'house_hunting']
    ).annotate(
        member_count=Count('memberships', filter=Q(memberships__status='active'))
    ).order_by('-created_at')

    # Filter by search query
    search_query = request.GET.get('search')
    if search_query:
        groups = groups.filter(
            Q(name__icontains=search_query) |
            Q(description__icontains=search_query)
        )

    # Filter by status
    status_filter = request.GET.get('status')
    if status_filter:
        groups = groups.filter(status=status_filter)

    # Filter by location
    location_filter = request.GET.get('location')
    if location_filter:
        groups = groups.filter(preferred_locations__icontains=location_filter)

    paginator = Paginator(groups, 12)
    page = request.GET.get('page')
    groups = paginator.get_page(page)

    context = {
        'groups': groups,
        'search_query': search_query,
        'status_filter': status_filter,
        'location_filter': location_filter,
    }

    return render(request, 'groups/group_list.html', context)


@login_required
def my_groups(request):
    """List user's groups"""
    memberships = GroupMembership.objects.filter(
        user=request.user,
        status='active'
    ).select_related('group').order_by('-joined_at')

    context = {
        'memberships': memberships,
    }

    return render(request, 'groups/my_groups.html', context)


@login_required
def create_group(request):
    """Create a new group"""
    if request.method == 'POST':
        form = CreateGroupForm(request.POST)
        if form.is_valid():
            group = form.save()

            # Create admin membership for creator
            GroupMembership.objects.create(
                group=group,
                user=request.user,
                role='admin',
                status='active',
                can_invite_members=True,
                can_manage_applications=True,
                can_edit_group=True
            )

            # Log activity
            GroupActivity.objects.create(
                group=group,
                user=request.user,
                activity_type='member_joined',
                description=f"{request.user.get_short_name()} created the group"
            )

            messages.success(request, 'Group created successfully!')
            return redirect('groups:group_detail', group_id=group.id)
    else:
        form = CreateGroupForm()

    return render(request, 'groups/create_group.html', {'form': form})


@login_required
def group_detail(request, group_id):
    """View group details"""
    group = get_object_or_404(RoommateGroup, id=group_id, is_active=True)

    # Get user's membership if exists
    user_membership = None
    try:
        user_membership = GroupMembership.objects.get(
            group=group,
            user=request.user,
            status='active'
        )
    except GroupMembership.DoesNotExist:
        pass

    # Check if user can join
    can_join, join_message = group.can_user_join(request.user)

    # Get active members
    members = group.get_active_members()

    # Get recent applications if user is member
    applications = []
    if user_membership:
        applications = PropertyApplication.objects.filter(
            group=group
        ).select_related('property_listing').order_by('-created_at')[:5]

    # Get recent activities
    activities = GroupActivity.objects.filter(
        group=group
    ).select_related('user').order_by('-created_at')[:10]

    context = {
        'group': group,
        'user_membership': user_membership,
        'can_join': can_join,
        'join_message': join_message,
        'members': members,
        'applications': applications,
        'activities': activities,
    }

    return render(request, 'groups/group_detail.html', context)


@login_required
@require_POST
def join_group_request(request, group_id):
    """Request to join a group"""
    group = get_object_or_404(RoommateGroup, id=group_id, is_active=True)

    can_join, message = group.can_user_join(request.user)

    if not can_join:
        messages.error(request, message)
        return redirect('groups:group_detail', group_id=group_id)

    join_reason = request.POST.get('join_reason', '')

    # Create membership request
    GroupMembership.objects.create(
        group=group,
        user=request.user,
        status='pending',
        join_reason=join_reason
    )

    # Log activity
    GroupActivity.objects.create(
        group=group,
        user=request.user,
        activity_type='member_joined',
        description=f"{request.user.get_short_name()} requested to join"
    )

    messages.success(request, 'Join request sent! Group admins will review your request.')
    return redirect('groups:group_detail', group_id=group_id)


@login_required
def edit_group(request, group_id):
    """Edit group details"""
    group = get_object_or_404(RoommateGroup, id=group_id)

    # Check permissions
    try:
        membership = GroupMembership.objects.get(
            group=group,
            user=request.user,
            status='active'
        )
        if not membership.can_edit_group and not membership.is_admin:
            messages.error(request, 'You do not have permission to edit this group.')
            return redirect('groups:group_detail', group_id=group_id)
    except GroupMembership.DoesNotExist:
        messages.error(request, 'You are not a member of this group.')
        return redirect('groups:group_detail', group_id=group_id)

    if request.method == 'POST':
        form = EditGroupForm(request.POST, instance=group)
        if form.is_valid():
            form.save()

            # Log activity
            GroupActivity.objects.create(
                group=group,
                user=request.user,
                activity_type='group_updated',
                description=f"{request.user.get_short_name()} updated group details"
            )

            messages.success(request, 'Group updated successfully!')
            return redirect('groups:group_detail', group_id=group_id)
    else:
        form = EditGroupForm(instance=group)

    return render(request, 'groups/edit_group.html', {'form': form, 'group': group})


@login_required
@require_POST
def leave_group(request, group_id):
    """Leave a group"""
    group = get_object_or_404(RoommateGroup, id=group_id)

    try:
        membership = GroupMembership.objects.get(
            group=group,
            user=request.user,
            status='active'
        )

        # Check if user is the only admin
        if membership.is_admin:
            admin_count = GroupMembership.objects.filter(
                group=group,
                role='admin',
                status='active'
            ).count()

            if admin_count == 1:
                # Transfer admin to another member or prevent leaving
                other_members = GroupMembership.objects.filter(
                    group=group,
                    status='active'
                ).exclude(user=request.user)

                if other_members.exists():
                    # Promote most senior member to admin
                    new_admin = other_members.order_by('joined_at').first()
                    new_admin.role = 'admin'
                    new_admin.can_edit_group = True
                    new_admin.can_invite_members = True
                    new_admin.can_manage_applications = True
                    new_admin.save()

                    messages.info(request, f'{new_admin.user.get_short_name()} has been promoted to admin.')
                else:
                    # Last member - deactivate group
                    group.is_active = False
                    group.status = 'disbanded'
                    group.save()

        membership.leave_group()

        # Log activity
        GroupActivity.objects.create(
            group=group,
            user=request.user,
            activity_type='member_left',
            description=f"{request.user.get_short_name()} left the group"
        )

        messages.success(request, 'You have left the group.')
        return redirect('groups:my_groups')

    except GroupMembership.DoesNotExist:
        messages.error(request, 'You are not a member of this group.')
        return redirect('groups:group_detail', group_id=group_id)


@login_required
def manage_membership_requests(request, group_id):
    """Manage pending membership requests"""
    group = get_object_or_404(RoommateGroup, id=group_id)

    # Check permissions
    try:
        membership = GroupMembership.objects.get(
            group=group,
            user=request.user,
            status='active'
        )
        if not membership.can_manage_applications and not membership.is_admin:
            messages.error(request, 'You do not have permission to manage membership requests.')
            return redirect('groups:group_detail', group_id=group_id)
    except GroupMembership.DoesNotExist:
        messages.error(request, 'You are not a member of this group.')
        return redirect('groups:group_detail', group_id=group_id)

    # Get pending requests
    pending_requests = GroupMembership.objects.filter(
        group=group,
        status='pending'
    ).select_related('user__profile').order_by('-joined_at')

    context = {
        'group': group,
        'pending_requests': pending_requests,
    }

    return render(request, 'groups/manage_requests.html', context)


@login_required
@require_POST
def approve_member(request, group_id, user_id):
    """Approve a membership request"""
    group = get_object_or_404(RoommateGroup, id=group_id)
    user_to_approve = get_object_or_404(User, id=user_id)

    # Check permissions
    try:
        membership = GroupMembership.objects.get(
            group=group,
            user=request.user,
            status='active'
        )
        if not membership.can_manage_applications and not membership.is_admin:
            return JsonResponse({'error': 'Permission denied'}, status=403)
    except GroupMembership.DoesNotExist:
        return JsonResponse({'error': 'Not authorized'}, status=403)

    try:
        pending_membership = GroupMembership.objects.get(
            group=group,
            user=user_to_approve,
            status='pending'
        )

        if pending_membership.approve_membership():
            # Log activity
            GroupActivity.objects.create(
                group=group,
                user=request.user,
                activity_type='member_joined',
                description=f"{user_to_approve.get_short_name()} was approved by {request.user.get_short_name()}"
            )

            messages.success(request, f'{user_to_approve.get_short_name()} has been approved.')
        else:
            messages.error(request, 'Failed to approve member.')

    except GroupMembership.DoesNotExist:
        messages.error(request, 'Membership request not found.')

    return redirect('groups:manage_membership_requests', group_id=group_id)


@login_required
@require_POST
def reject_member(request, group_id, user_id):
    """Reject a membership request"""
    group = get_object_or_404(RoommateGroup, id=group_id)
    user_to_reject = get_object_or_404(User, id=user_id)

    # Check permissions
    try:
        membership = GroupMembership.objects.get(
            group=group,
            user=request.user,
            status='active'
        )
        if not membership.can_manage_applications and not membership.is_admin:
            return JsonResponse({'error': 'Permission denied'}, status=403)
    except GroupMembership.DoesNotExist:
        return JsonResponse({'error': 'Not authorized'}, status=403)

    try:
        pending_membership = GroupMembership.objects.get(
            group=group,
            user=user_to_reject,
            status='pending'
        )

        pending_membership.remove_from_group()
        messages.success(request, f'{user_to_reject.get_short_name()} request has been rejected.')

    except GroupMembership.DoesNotExist:
        messages.error(request, 'Membership request not found.')

    return redirect('groups:manage_membership_requests', group_id=group_id)


@login_required
def my_invitations(request):
    """View user's pending invitations"""
    invitations = GroupInvitation.objects.filter(
        invitee=request.user,
        status='pending'
    ).select_related('group', 'inviter').order_by('-created_at')

    context = {
        'invitations': invitations,
    }

    return render(request, 'groups/my_invitations.html', context)


@login_required
@require_POST
def accept_invitation(request, invitation_id):
    """Accept a group invitation"""
    invitation = get_object_or_404(
        GroupInvitation,
        id=invitation_id,
        invitee=request.user
    )

    success, message = invitation.accept()

    if success:
        messages.success(request, message)
        return redirect('groups:group_detail', group_id=invitation.group.id)
    else:
        messages.error(request, message)
        return redirect('groups:my_invitations')


@login_required
@require_POST
def decline_invitation(request, invitation_id):
    """Decline a group invitation"""
    invitation = get_object_or_404(
        GroupInvitation,
        id=invitation_id,
        invitee=request.user
    )

    if invitation.decline():
        messages.success(request, 'Invitation declined.')
    else:
        messages.error(request, 'Could not decline invitation.')

    return redirect('groups:my_invitations')


@login_required
def group_applications(request, group_id):
    """View group's property applications"""
    group = get_object_or_404(RoommateGroup, id=group_id)

    # Check membership
    try:
        GroupMembership.objects.get(
            group=group,
            user=request.user,
            status='active'
        )
    except GroupMembership.DoesNotExist:
        messages.error(request, 'You are not a member of this group.')
        return redirect('groups:group_detail', group_id=group_id)

    applications = PropertyApplication.objects.filter(
        group=group
    ).select_related('property_listing').prefetch_related('votes').order_by('-created_at')

    context = {
        'group': group,
        'applications': applications,
    }

    return render(request, 'groups/group_applications.html', context)


@login_required
def apply_for_property(request, group_id, property_id):
    """Apply for a property as a group"""
    group = get_object_or_404(RoommateGroup, id=group_id)
    property_listing = get_object_or_404(Property, id=property_id)

    # Check membership
    try:
        membership = GroupMembership.objects.get(
            group=group,
            user=request.user,
            status='active'
        )
    except GroupMembership.DoesNotExist:
        messages.error(request, 'You are not a member of this group.')
        return redirect('groups:group_detail', group_id=group_id)

    # Check if application already exists
    if PropertyApplication.objects.filter(group=group, property_listing=property_listing).exists():
        messages.error(request, 'Group has already applied for this property.')
        return redirect('properties:detail', pk=property_id)

    if request.method == 'POST':
        form = PropertyApplicationForm(request.POST)
        if form.is_valid():
            application = form.save(commit=False)
            application.group = group
            application.property_listing = property_listing
            application.votes_required = group.current_member_count
            application.save()

            # Auto-vote for the applicant
            ApplicationVote.objects.create(
                application=application,
                member=request.user,
                vote='yes',
                comment='Application created'
            )

            # Log activity
            GroupActivity.objects.create(
                group=group,
                user=request.user,
                activity_type='application_created',
                description=f"Applied for {property_listing.title}"
            )

            messages.success(request, 'Application created! Other members need to vote.')
            return redirect('groups:application_detail', application_id=application.id)
    else:
        form = PropertyApplicationForm()

    context = {
        'form': form,
        'group': group,
        'property': property_listing,
    }

    return render(request, 'groups/apply_for_property.html', context)


@login_required
def application_detail(request, application_id):
    """View application details and votes"""
    application = get_object_or_404(
        PropertyApplication.objects.select_related('group', 'property_listing'),
        id=application_id
    )

    # Check membership
    try:
        membership = GroupMembership.objects.get(
            group=application.group,
            user=request.user,
            status='active'
        )
    except GroupMembership.DoesNotExist:
        messages.error(request, 'You are not a member of this group.')
        return redirect('groups:group_detail', group_id=application.group.id)

    # Get votes
    votes = ApplicationVote.objects.filter(
        application=application
    ).select_related('member')

    # Check if user has voted
    user_vote = votes.filter(member=request.user).first()

    context = {
        'application': application,
        'votes': votes,
        'user_vote': user_vote,
        'membership': membership,
    }

    return render(request, 'groups/application_detail.html', context)


@login_required
@require_POST
def vote_on_application(request, application_id):
    """Vote on a property application"""
    application = get_object_or_404(PropertyApplication, id=application_id)

    # Check membership
    try:
        GroupMembership.objects.get(
            group=application.group,
            user=request.user,
            status='active'
        )
    except GroupMembership.DoesNotExist:
        return JsonResponse({'error': 'Not authorized'}, status=403)

    try:
        data = json.loads(request.body)
        vote_value = data.get('vote')
        comment = data.get('comment', '')

        if vote_value not in ['yes', 'no', 'abstain']:
            return JsonResponse({'error': 'Invalid vote value'}, status=400)

        # Update or create vote
        vote, created = ApplicationVote.objects.update_or_create(
            application=application,
            member=request.user,
            defaults={
                'vote': vote_value,
                'comment': comment
            }
        )

        # Log activity
        GroupActivity.objects.create(
            group=application.group,
            user=request.user,
            activity_type='application_voted',
            description=f"Voted {vote_value} on {application.property_listing.title}"
        )

        return JsonResponse({
            'success': True,
            'votes_received': application.votes_received,
            'can_submit': application.can_be_submitted
        })

    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)


@login_required
@require_POST
def submit_application(request, application_id):
    """Submit application to property owner"""
    application = get_object_or_404(PropertyApplication, id=application_id)

    # Check permissions
    try:
        membership = GroupMembership.objects.get(
            group=application.group,
            user=request.user,
            status='active'
        )
        if not membership.can_manage_applications and not membership.is_admin:
            return JsonResponse({'error': 'Permission denied'}, status=403)
    except GroupMembership.DoesNotExist:
        return JsonResponse({'error': 'Not authorized'}, status=403)

    if application.submit_application():
        # Log activity
        GroupActivity.objects.create(
            group=application.group,
            user=request.user,
            activity_type='application_submitted',
            description=f"Submitted application for {application.property_listing.title}"
        )

        messages.success(request, 'Application submitted to property owner!')
        return JsonResponse({'success': True})
    else:
        return JsonResponse({'error': 'Cannot submit application'}, status=400)


@login_required
def group_activities(request, group_id):
    """View group activities"""
    group = get_object_or_404(RoommateGroup, id=group_id)

    # Check membership
    try:
        GroupMembership.objects.get(
            group=group,
            user=request.user,
            status='active'
        )
    except GroupMembership.DoesNotExist:
        messages.error(request, 'You are not a member of this group.')
        return redirect('groups:group_detail', group_id=group_id)

    activities = GroupActivity.objects.filter(
        group=group
    ).select_related('user').order_by('-created_at')

    paginator = Paginator(activities, 20)
    page = request.GET.get('page')
    activities = paginator.get_page(page)

    context = {
        'group': group,
        'activities': activities,
    }

    return render(request, 'groups/group_activities.html', context)


@login_required
def group_chat(request, group_id):
    """Redirect to group messaging"""
    group = get_object_or_404(RoommateGroup, id=group_id)

    # Check membership
    try:
        GroupMembership.objects.get(
            group=group,
            user=request.user,
            status='active'
        )
    except GroupMembership.DoesNotExist:
        messages.error(request, 'You are not a member of this group.')
        return redirect('groups:group_detail', group_id=group_id)

    # Create or get group conversation
    messaging_service = MessagingService()

    # Get all active members
    members = group.get_active_members()

    # Create group conversation if it doesn't exist
    conversation = messaging_service.start_conversation(
        initiator=request.user,
        participants=list(members),
        conversation_type='group',
        title=f"{group.name} Chat"
    )

    return redirect('messaging:conversation_detail', conversation_id=conversation.id)


@login_required
def search_groups(request):
    """AJAX endpoint for searching groups"""
    query = request.GET.get('q', '').strip()

    if len(query) < 2:
        return JsonResponse({'groups': []})

    groups = RoommateGroup.objects.filter(
        Q(name__icontains=query) | Q(description__icontains=query),
        is_active=True,
        status__in=['forming', 'active', 'house_hunting']
    ).annotate(
        member_count=Count('memberships', filter=Q(memberships__status='active'))
    )[:10]

    groups_data = []
    for group in groups:
        groups_data.append({
            'id': str(group.id),
            'name': group.name,
            'description': group.description[:100] + '...' if len(group.description) > 100 else group.description,
            'status': group.get_status_display(),
            'member_count': group.member_count,
            'max_members': group.max_members,
            'is_private': group.is_private
        })

    return JsonResponse({'groups': groups_data})


@login_required
def check_join_eligibility(request, group_id):
    """AJAX endpoint to check if user can join group"""
    group = get_object_or_404(RoommateGroup, id=group_id)

    can_join, message = group.can_user_join(request.user)

    return JsonResponse({
        'can_join': can_join,
        'message': message
    })


# Placeholder views for other functionality
@login_required
def manage_members(request, group_id):
    """Manage group members (placeholder)"""
    messages.info(request, 'Member management coming soon!')
    return redirect('groups:group_detail', group_id=group_id)


@login_required
def invite_members(request, group_id):
    """Invite new members (placeholder)"""
    messages.info(request, 'Member invitation coming soon!')
    return redirect('groups:group_detail', group_id=group_id)


@login_required
def remove_member(request, group_id, user_id):
    """Remove a member (placeholder)"""
    messages.info(request, 'Member removal coming soon!')
    return redirect('groups:group_detail', group_id=group_id)


@login_required
def promote_member(request, group_id, user_id):
    """Promote a member (placeholder)"""
    messages.info(request, 'Member promotion coming soon!')
    return redirect('groups:group_detail', group_id=group_id)
