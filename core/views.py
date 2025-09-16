from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth import get_user_model
from django.db.models import Count, Q, Sum
from django.db import models
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
    """Main dashboard view - routes to appropriate role-based dashboard"""
    # Check if user needs to complete profile (only renters need detailed profile)
    if not getattr(request.user, 'profile_completed', False) and request.user.is_renter:
        return redirect('profiles:setup')

    user = request.user

    # Route to appropriate dashboard based on user type
    if user.is_admin:
        return admin_dashboard(request)
    elif user.is_landlord:
        return landlord_dashboard(request)
    else:  # Default to renter dashboard
        return renter_dashboard(request)


@login_required
def renter_dashboard(request):
    """Dashboard for renters"""
    user = request.user

    # Get user's groups
    user_groups = GroupMembership.objects.filter(
        user=request.user,
        status='active'
    ).select_related('group')[:5]

    # Get recent properties with available rooms (only from landlords)
    recent_properties = Property.objects.filter(
        is_active=True,
        rooms_available__gt=0,
        added_by__user_type='landlord'  # Only show properties from landlords
    ).exclude(
        added_by__user_type='admin'  # Hide admin properties
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
    ).exclude(
        participants__user_type='admin'  # Hide conversations with admin
    ).select_related('property_listing').prefetch_related('participants')[:5]

    # Get roommate recommendations (only other renters)
    roommate_recommendations = UserRecommendation.objects.filter(
        target_user=request.user,
        is_dismissed=False,
        recommended_user__user_type='renter'  # Only recommend other renters
    ).exclude(
        recommended_user__user_type='admin'  # Hide admin users
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
            is_active=True,
            added_by__user_type='landlord'
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
        'dashboard_type': 'renter',
    }

    return render(request, 'core/renter_dashboard.html', context)


@login_required
def landlord_dashboard(request):
    """Dashboard for landlords"""
    user = request.user

    if not user.is_landlord:
        return redirect('core:dashboard')

    # Get user's properties
    user_properties = Property.objects.filter(added_by=user)

    # Get recent inquiries for user's properties
    recent_inquiries = Conversation.objects.filter(
        property_listing__added_by=user,
        conversation_type='property_inquiry',
        is_active=True
    ).exclude(
        participants__user_type='admin'  # Hide admin conversations
    ).order_by('-created_at')[:5]

    # Get recent conversations
    recent_conversations = Conversation.objects.filter(
        participants=request.user,
        is_active=True
    ).exclude(
        participants__user_type='admin'  # Hide conversations with admin
    ).select_related('property_listing').prefetch_related('participants')[:5]

    # Statistics
    total_properties = user_properties.count()
    available_rooms = user_properties.aggregate(
        total_rooms=Sum('rooms_available')
    )['total_rooms'] or 0

    total_inquiries = Conversation.objects.filter(
        property_listing__added_by=user,
        conversation_type='property_inquiry'
    ).count()

    # Get unread message count
    unread_count = 0
    for conversation in recent_conversations:
        unread_count += conversation.unread_count_for_user(request.user)

    context = {
        'user_properties': user_properties[:5],  # Latest 5 properties
        'recent_inquiries': recent_inquiries,
        'recent_conversations': recent_conversations,
        'total_properties': total_properties,
        'available_rooms': available_rooms,
        'total_inquiries': total_inquiries,
        'unread_count': unread_count,
        'dashboard_type': 'landlord',
    }

    return render(request, 'core/landlord_dashboard.html', context)


@login_required
def admin_dashboard(request):
    """Dashboard for administrators"""
    user = request.user

    if not user.is_admin:
        return redirect('core:dashboard')

    # Admin statistics
    total_users = User.objects.filter(is_active=True).count()
    total_renters = User.objects.filter(user_type='renter', is_active=True).count()
    total_landlords = User.objects.filter(user_type='landlord', is_active=True).count()
    total_properties = Property.objects.count()
    total_groups = RoommateGroup.objects.filter(is_active=True).count()

    # Recent activity
    recent_users = User.objects.filter(is_active=True).order_by('-date_joined')[:10]
    recent_properties = Property.objects.order_by('-created_at')[:10]
    recent_conversations = Conversation.objects.order_by('-created_at')[:10]
    recent_groups = RoommateGroup.objects.filter(is_active=True).order_by('-created_at')[:10]

    # Weekly statistics
    week_ago = timezone.now() - timedelta(days=7)
    weekly_stats = {
        'new_users': User.objects.filter(date_joined__gte=week_ago).count(),
        'new_properties': Property.objects.filter(created_at__gte=week_ago).count(),
        'new_conversations': Conversation.objects.filter(created_at__gte=week_ago).count(),
        'new_groups': RoommateGroup.objects.filter(created_at__gte=week_ago).count(),
    }

    context = {
        'total_users': total_users,
        'total_renters': total_renters,
        'total_landlords': total_landlords,
        'total_properties': total_properties,
        'total_groups': total_groups,
        'recent_users': recent_users,
        'recent_properties': recent_properties,
        'recent_conversations': recent_conversations,
        'recent_groups': recent_groups,
        'weekly_stats': weekly_stats,
        'dashboard_type': 'admin',
    }

    return render(request, 'core/admin_dashboard.html', context)


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