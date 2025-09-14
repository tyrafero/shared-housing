from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth import get_user_model
from django.db.models import Count, Q
from django.utils import timezone
from datetime import timedelta

from properties.models import Property, PropertySavedSearch
from groups.models import RoommateGroup, GroupMembership
from messaging.models import Conversation
from roommate_matching.models import UserRecommendation, CompatibilityScore

User = get_user_model()


def home(request):
    """Landing page - redirect authenticated users to dashboard"""
    if request.user.is_authenticated:
        return redirect('core:dashboard')

    # Get some stats for landing page
    total_users = User.objects.filter(is_active=True).count()
    total_properties = Property.objects.filter(is_active=True).count()
    total_groups = RoommateGroup.objects.filter(is_active=True).count()

    context = {
        'total_users': total_users,
        'total_properties': total_properties,
        'total_groups': total_groups,
    }

    return render(request, 'core/home.html', context)


@login_required
def dashboard(request):
    """Main dashboard for authenticated users"""

    # Check if user needs to complete profile
    if not getattr(request.user, 'profile_completed', False):
        return redirect('profiles:setup')

    # Get user's groups
    user_groups = GroupMembership.objects.filter(
        user=request.user,
        status='active'
    ).select_related('group')[:5]

    # Get recent property matches/recommendations
    recent_properties = Property.objects.filter(
        is_active=True,
        rooms_available__gt=0
    ).order_by('-created_at')[:6]

    # Get user's saved properties
    saved_properties = []
    if hasattr(request.user, 'saved_properties'):
        saved_properties = request.user.saved_properties.filter(
            is_active=True
        )[:4]

    # Get recent conversations
    recent_conversations = Conversation.objects.filter(
        participants=request.user,
        is_active=True
    ).select_related('property_listing').prefetch_related('participants')[:5]

    # Get roommate recommendations
    roommate_recommendations = UserRecommendation.objects.filter(
        target_user=request.user,
        is_dismissed=False
    ).select_related('recommended_user', 'compatibility_score').order_by('-created_at')[:4]

    # Get group recommendations
    available_groups = RoommateGroup.objects.filter(
        is_active=True,
        status__in=['forming', 'active']
    ).exclude(
        memberships__user=request.user
    ).annotate(
        member_count=Count('memberships', filter=Q(memberships__status='active'))
    ).order_by('-created_at')[:4]

    # Get unread message count
    unread_count = 0
    for conversation in recent_conversations:
        unread_count += conversation.unread_count_for_user(request.user)

    # Activity summary
    recent_activity = {
        'new_properties': Property.objects.filter(
            created_at__gte=timezone.now() - timedelta(days=7),
            is_active=True
        ).count(),
        'new_groups': RoommateGroup.objects.filter(
            created_at__gte=timezone.now() - timedelta(days=7),
            is_active=True
        ).count(),
        'new_matches': roommate_recommendations.count(),
        'unread_messages': unread_count,
    }

    context = {
        'user_groups': user_groups,
        'recent_properties': recent_properties,
        'saved_properties': saved_properties,
        'recent_conversations': recent_conversations,
        'roommate_recommendations': roommate_recommendations,
        'available_groups': available_groups,
        'recent_activity': recent_activity,
        'unread_count': unread_count,
    }

    return render(request, 'core/dashboard.html', context)


def about(request):
    """About page"""
    return render(request, 'core/about.html')


def contact(request):
    """Contact page"""
    return render(request, 'core/contact.html')


def privacy(request):
    """Privacy policy page"""
    return render(request, 'core/privacy.html')


def terms(request):
    """Terms of service page"""
    return render(request, 'core/terms.html')