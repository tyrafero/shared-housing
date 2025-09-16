from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth import get_user_model
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.contrib import messages
from django.db.models import Q
from django.core.paginator import Paginator

from .models import CompatibilityScore, UserRecommendation, UserInteraction
from .services import CompatibilityCalculator, MatchingService
from messaging.services import MessagingService

User = get_user_model()


@login_required
def matching_dashboard(request):
    """Main matching dashboard"""

    # Check if user has completed profile (only renters need roommate matching)
    if not getattr(request.user, 'profile_completed', False) and request.user.is_renter:
        return redirect('profiles:setup')

    matching_service = MatchingService()

    # Get user's recommendations
    recommendations = matching_service.get_user_recommendations(
        request.user,
        limit=8
    )

    # Get recent compatibility scores
    recent_scores = CompatibilityScore.objects.filter(
        Q(user1=request.user) | Q(user2=request.user)
    ).select_related('user1', 'user2').order_by('-calculated_at')[:5]

    # Get interaction stats
    total_interactions = UserInteraction.objects.filter(
        source_user=request.user
    ).count()

    context = {
        'recommendations': recommendations,
        'recent_scores': recent_scores,
        'total_interactions': total_interactions,
    }

    return render(request, 'matching/dashboard.html', context)


@login_required
def find_roommates(request):
    """Search and filter potential roommates"""

    if not getattr(request.user, 'profile_completed', False) and request.user.is_renter:
        return redirect('profiles:setup')

    # Base queryset - all users except current user with completed profiles
    # Exclude admin users from regular user searches
    users = User.objects.filter(
        profile_completed=True,
        is_active=True,
        user_type__in=['renter', 'landlord']  # Only show renters and landlords
    ).exclude(
        id=request.user.id
    ).exclude(
        user_type='admin'  # Hide admin users
    ).select_related('profile')

    # Search by name/email
    search_query = request.GET.get('search', '').strip()
    if search_query:
        users = users.filter(
            Q(first_name__icontains=search_query) |
            Q(last_name__icontains=search_query) |
            Q(email__icontains=search_query)
        )

    # Filter by age
    min_age = request.GET.get('min_age')
    max_age = request.GET.get('max_age')
    if min_age or max_age:
        # Age filtering would require profile model with birth_date
        pass

    # Filter by location
    location = request.GET.get('location')
    if location:
        # This would filter by user profile location preferences
        pass

    # Filter by budget
    min_budget = request.GET.get('min_budget')
    max_budget = request.GET.get('max_budget')
    if min_budget or max_budget:
        # Budget filtering via profile
        pass

    # Calculate compatibility scores for displayed users
    matching_service = MatchingService()
    users_with_scores = []

    for user in users[:20]:  # Limit to avoid performance issues
        score = matching_service.calculate_user_compatibility(
            request.user,
            user
        )
        users_with_scores.append({
            'user': user,
            'compatibility_score': score
        })

    # Sort by compatibility
    if request.GET.get('sort') == 'compatibility':
        users_with_scores.sort(
            key=lambda x: x['compatibility_score'].overall_score if x['compatibility_score'] else 0,
            reverse=True
        )

    paginator = Paginator(users_with_scores, 12)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'page_obj': page_obj,
        'search_query': search_query,
        'location': location,
        'min_budget': min_budget,
        'max_budget': max_budget,
        'total_count': len(users_with_scores),
    }

    return render(request, 'matching/find_roommates.html', context)


@login_required
def my_matches(request):
    """View user's matches and recommendations"""

    if not getattr(request.user, 'profile_completed', False) and request.user.is_renter:
        return redirect('profiles:setup')

    # Get user's active recommendations
    recommendations = UserRecommendation.objects.filter(
        target_user=request.user,
        is_dismissed=False
    ).select_related(
        'recommended_user',
        'compatibility_score'
    ).order_by('-created_at')

    paginator = Paginator(recommendations, 12)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'page_obj': page_obj,
        'total_count': recommendations.count(),
    }

    return render(request, 'matching/my_matches.html', context)


@login_required
def compatibility_detail(request, user_id):
    """View detailed compatibility breakdown with another user"""

    other_user = get_object_or_404(
        User,
        id=user_id,
        is_active=True,
        profile_completed=True
    )

    if other_user == request.user:
        return redirect('matching:find_roommates')

    matching_service = MatchingService()
    compatibility_score = matching_service.calculate_user_compatibility(
        request.user,
        other_user
    )

    context = {
        'other_user': other_user,
        'compatibility_score': compatibility_score,
    }

    return render(request, 'matching/compatibility_detail.html', context)


@login_required
def connect_with_user(request, user_id):
    """Connect with a user (start conversation)"""

    other_user = get_object_or_404(User, id=user_id, is_active=True)

    if other_user == request.user:
        return redirect('matching:find_roommates')

    # Handle GET request - show confirmation page
    if request.method == 'GET':
        # Get compatibility score for display
        matching_service = MatchingService()
        compatibility_score = matching_service.calculate_user_compatibility(
            request.user,
            other_user
        )

        context = {
            'other_user': other_user,
            'compatibility_score': compatibility_score,
        }
        return render(request, 'matching/connect_confirm.html', context)

    # Handle POST request - actually connect

    # Record interaction
    matching_service = MatchingService()
    matching_service.record_user_interaction(
        source_user=request.user,
        target_user=other_user,
        interaction_type='connect',
        was_recommended=True,
        metadata={'via': 'matching_system'}
    )

    # Create or get conversation
    messaging_service = MessagingService()
    conversation, created = messaging_service.get_or_create_direct_conversation(
        request.user,
        other_user
    )

    if created:
        # Get compatibility score for welcome message
        compatibility_score = matching_service.calculate_user_compatibility(
            request.user,
            other_user
        )

        if compatibility_score:
            welcome_msg = (
                f"You've connected with {other_user.get_short_name()}! "
                f"Compatibility score: {compatibility_score.overall_score:.0f}% "
                f"({compatibility_score.compatibility_level})"
            )
        else:
            welcome_msg = f"You've connected with {other_user.get_short_name()}!"

        messaging_service.send_system_message(conversation, welcome_msg)

    return redirect('messaging:conversation_detail', conversation_id=conversation.id)


@login_required
@require_POST
def dismiss_recommendation(request, recommendation_id):
    """Dismiss a recommendation"""

    recommendation = get_object_or_404(
        UserRecommendation,
        id=recommendation_id,
        target_user=request.user
    )

    recommendation.is_dismissed = True
    recommendation.save()

    # Record interaction
    matching_service = MatchingService()
    matching_service.record_user_interaction(
        source_user=request.user,
        target_user=recommendation.recommended_user,
        interaction_type='dismiss',
        was_recommended=True
    )

    return redirect('matching:my_matches')


@login_required
def get_user_recommendations(request):
    """Get fresh recommendations for user"""

    if not getattr(request.user, 'profile_completed', False):
        return JsonResponse({'error': 'Profile not completed'}, status=400)

    matching_service = MatchingService()
    recommendations = matching_service.get_user_recommendations(
        request.user,
        limit=int(request.GET.get('limit', 10))
    )

    recommendations_data = []
    for rec in recommendations:
        user = rec.recommended_user
        score = rec.compatibility_score

        recommendations_data.append({
            'id': rec.id,
            'user': {
                'id': user.id,
                'name': user.get_short_name(),
                'email': user.email,
            },
            'compatibility_score': {
                'overall_score': score.overall_score if score else 0,
                'compatibility_level': score.compatibility_level if score else 'Unknown',
            },
            'created_at': rec.created_at.isoformat(),
        })

    return JsonResponse({
        'recommendations': recommendations_data,
        'total_count': len(recommendations_data)
    })


# API endpoints

@login_required
def api_calculate_compatibility(request, user_id):
    """API endpoint to calculate compatibility with another user"""

    other_user = get_object_or_404(User, id=user_id, is_active=True)

    if other_user == request.user:
        return JsonResponse({'error': 'Cannot calculate compatibility with yourself'}, status=400)

    matching_service = MatchingService()
    compatibility_score = matching_service.calculate_user_compatibility(
        request.user,
        other_user
    )

    if compatibility_score:
        return JsonResponse({
            'overall_score': compatibility_score.overall_score,
            'compatibility_level': compatibility_score.compatibility_level,
            'lifestyle_score': compatibility_score.lifestyle_score,
            'preferences_score': compatibility_score.preferences_score,
            'personality_score': compatibility_score.personality_score,
            'budget_score': compatibility_score.budget_score,
            'location_score': compatibility_score.location_score,
        })
    else:
        return JsonResponse({'error': 'Could not calculate compatibility'}, status=500)


@login_required
def api_user_search(request):
    """API endpoint for user search with autocomplete"""

    query = request.GET.get('q', '').strip()
    if len(query) < 2:
        return JsonResponse({'users': []})

    users = User.objects.filter(
        Q(first_name__icontains=query) | Q(last_name__icontains=query),
        profile_completed=True,
        is_active=True,
        user_type__in=['renter', 'landlord']  # Only show renters and landlords
    ).exclude(
        id=request.user.id
    ).exclude(
        user_type='admin'  # Hide admin users
    )[:10]

    users_data = []
    for user in users:
        users_data.append({
            'id': user.id,
            'name': user.get_short_name(),
            'email': user.email,
        })

    return JsonResponse({'users': users_data})
