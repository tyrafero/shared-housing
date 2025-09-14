from typing import List, Dict, Tuple, Optional
import logging
import time
from datetime import datetime, timedelta
from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Q, F
from django.utils import timezone
from profiles.models import UserProfile
from .models import (
    CompatibilityScore, UserRecommendation, MatchingCriteria,
    MatchingActivity, UserInteraction
)

User = get_user_model()
logger = logging.getLogger(__name__)


class CompatibilityCalculator:
    """Core compatibility scoring algorithm"""

    def __init__(self):
        self.weights = {
            'budget': 0.25,
            'location': 0.20,
            'lifestyle': 0.20,
            'schedule': 0.15,
            'habits': 0.20
        }

    def calculate_compatibility(self, user1: User, user2: User) -> Dict:
        """Calculate overall compatibility score between two users"""
        start_time = time.time()

        try:
            profile1 = user1.profile
            profile2 = user2.profile
        except UserProfile.DoesNotExist:
            return {'overall_score': 0, 'error': 'Missing profile data'}

        # Get matching criteria or use defaults
        criteria1 = getattr(user1, 'matching_criteria', None)
        criteria2 = getattr(user2, 'matching_criteria', None)

        # Calculate individual component scores
        budget_score = self._calculate_budget_compatibility(profile1, profile2)
        location_score = self._calculate_location_compatibility(profile1, profile2)
        lifestyle_score = self._calculate_lifestyle_compatibility(profile1, profile2)
        schedule_score = self._calculate_schedule_compatibility(profile1, profile2)
        habits_score = self._calculate_habits_compatibility(profile1, profile2)

        # Apply user-specific weights if available
        weights = self._get_personalized_weights(criteria1, criteria2)

        # Calculate weighted overall score
        overall_score = (
            budget_score * weights['budget'] +
            location_score * weights['location'] +
            lifestyle_score * weights['lifestyle'] +
            schedule_score * weights['schedule'] +
            habits_score * weights['habits']
        )

        # Apply deal breaker penalties
        deal_breaker_penalty = self._calculate_deal_breaker_penalty(
            profile1, profile2, criteria1, criteria2
        )
        overall_score = max(0, overall_score - deal_breaker_penalty)

        # Build detailed breakdown
        breakdown = {
            'budget': {
                'score': budget_score,
                'weight': weights['budget'],
                'weighted_score': budget_score * weights['budget']
            },
            'location': {
                'score': location_score,
                'weight': weights['location'],
                'weighted_score': location_score * weights['location']
            },
            'lifestyle': {
                'score': lifestyle_score,
                'weight': weights['lifestyle'],
                'weighted_score': lifestyle_score * weights['lifestyle']
            },
            'schedule': {
                'score': schedule_score,
                'weight': weights['schedule'],
                'weighted_score': schedule_score * weights['schedule']
            },
            'habits': {
                'score': habits_score,
                'weight': weights['habits'],
                'weighted_score': habits_score * weights['habits']
            },
            'deal_breaker_penalty': deal_breaker_penalty,
            'calculation_time': time.time() - start_time
        }

        return {
            'overall_score': min(100, max(0, overall_score)),
            'budget_score': budget_score,
            'location_score': location_score,
            'lifestyle_score': lifestyle_score,
            'schedule_score': schedule_score,
            'habits_score': habits_score,
            'breakdown': breakdown
        }

    def _calculate_budget_compatibility(self, profile1: UserProfile, profile2: UserProfile) -> float:
        """Calculate budget compatibility score"""
        if not all([profile1.min_budget, profile1.max_budget, profile2.min_budget, profile2.max_budget]):
            return 50.0  # Neutral score for missing data

        # Calculate budget range overlap
        user1_range = (profile1.min_budget, profile1.max_budget)
        user2_range = (profile2.min_budget, profile2.max_budget)

        # Find overlap
        overlap_start = max(user1_range[0], user2_range[0])
        overlap_end = min(user1_range[1], user2_range[1])

        if overlap_start > overlap_end:
            return 0.0  # No overlap

        # Calculate overlap percentage
        user1_range_size = user1_range[1] - user1_range[0]
        user2_range_size = user2_range[1] - user2_range[0]
        overlap_size = overlap_end - overlap_start

        avg_range_size = (user1_range_size + user2_range_size) / 2
        overlap_ratio = overlap_size / avg_range_size if avg_range_size > 0 else 0

        return min(100, overlap_ratio * 100)

    def _calculate_location_compatibility(self, profile1: UserProfile, profile2: UserProfile) -> float:
        """Calculate location compatibility score"""
        locations1 = profile1.preferred_locations or []
        locations2 = profile2.preferred_locations or []

        if not locations1 or not locations2:
            return 60.0  # Neutral score for missing data

        # Convert to lowercase for comparison
        locations1_lower = [loc.lower() for loc in locations1]
        locations2_lower = [loc.lower() for loc in locations2]

        # Find common locations
        common_locations = set(locations1_lower) & set(locations2_lower)

        if common_locations:
            # Score based on number of common locations
            overlap_ratio = len(common_locations) / max(len(locations1), len(locations2))
            return min(100, overlap_ratio * 100 + 50)  # Bonus for any overlap

        return 30.0  # Low score for no overlap

    def _calculate_lifestyle_compatibility(self, profile1: UserProfile, profile2: UserProfile) -> float:
        """Calculate lifestyle compatibility score"""
        scores = []

        # Social level compatibility
        if profile1.social_level and profile2.social_level:
            social_diff = abs(profile1.social_level - profile2.social_level)
            social_score = max(0, 100 - (social_diff * 15))  # 15 points per level difference
            scores.append(social_score)

        # Smoking compatibility
        if profile1.smoker and profile2.smoker:
            if profile1.smoker == profile2.smoker:
                scores.append(100)
            elif 'no' in [profile1.smoker, profile2.smoker] and 'yes' in [profile1.smoker, profile2.smoker]:
                scores.append(20)  # Major incompatibility
            else:
                scores.append(70)  # Moderate compatibility

        # Drinking compatibility
        if profile1.drinking and profile2.drinking:
            drinking_compatibility = {
                ('no', 'no'): 100,
                ('no', 'social'): 80,
                ('no', 'regular'): 40,
                ('social', 'social'): 100,
                ('social', 'regular'): 85,
                ('regular', 'regular'): 100,
            }
            key = tuple(sorted([profile1.drinking, profile2.drinking]))
            scores.append(drinking_compatibility.get(key, 70))

        # Pet compatibility
        if profile1.pets and profile2.pets:
            pet_compatibility = {
                ('no', 'no'): 100,
                ('no', 'yes'): 30,
                ('yes', 'yes'): 90,
            }
            key = tuple(sorted([profile1.pets, profile2.pets]))
            scores.append(pet_compatibility.get(key, 70))

        return sum(scores) / len(scores) if scores else 50.0

    def _calculate_schedule_compatibility(self, profile1: UserProfile, profile2: UserProfile) -> float:
        """Calculate schedule compatibility score"""
        if not profile1.schedule_type or not profile2.schedule_type:
            return 50.0

        schedule_compatibility = {
            ('early_bird', 'early_bird'): 100,
            ('early_bird', 'regular'): 80,
            ('early_bird', 'night_owl'): 40,
            ('regular', 'regular'): 100,
            ('regular', 'night_owl'): 75,
            ('night_owl', 'night_owl'): 100,
        }

        key = tuple(sorted([profile1.schedule_type, profile2.schedule_type]))
        base_score = schedule_compatibility.get(key, 70)

        # Bonus for work from home compatibility
        if profile1.works_from_home == profile2.works_from_home:
            base_score = min(100, base_score + 10)

        return base_score

    def _calculate_habits_compatibility(self, profile1: UserProfile, profile2: UserProfile) -> float:
        """Calculate habits and cleanliness compatibility score"""
        if not profile1.cleanliness_level or not profile2.cleanliness_level:
            return 50.0

        # Cleanliness level compatibility (1-10 scale)
        cleanliness_diff = abs(profile1.cleanliness_level - profile2.cleanliness_level)
        cleanliness_score = max(0, 100 - (cleanliness_diff * 12))  # 12 points per level

        # Noise tolerance compatibility
        noise_score = 50.0
        if profile1.noise_tolerance and profile2.noise_tolerance:
            noise_diff = abs(profile1.noise_tolerance - profile2.noise_tolerance)
            noise_score = max(0, 100 - (noise_diff * 12))

        return (cleanliness_score + noise_score) / 2

    def _get_personalized_weights(self, criteria1: Optional[MatchingCriteria],
                                criteria2: Optional[MatchingCriteria]) -> Dict[str, float]:
        """Get personalized weights based on user criteria"""
        default_weights = self.weights.copy()

        if not criteria1 and not criteria2:
            return default_weights

        # Average the importance scores from both users
        importance_scores = {}
        for component in ['budget', 'location', 'lifestyle', 'schedule', 'habits']:
            score1 = getattr(criteria1, f'{component}_importance', 3) if criteria1 else 3
            score2 = getattr(criteria2, f'{component}_importance', 3) if criteria2 else 3
            importance_scores[component] = (score1 + score2) / 2

        # Normalize to weights that sum to 1
        total_importance = sum(importance_scores.values())
        if total_importance > 0:
            return {k: v / total_importance for k, v in importance_scores.items()}

        return default_weights

    def _calculate_deal_breaker_penalty(self, profile1: UserProfile, profile2: UserProfile,
                                      criteria1: Optional[MatchingCriteria],
                                      criteria2: Optional[MatchingCriteria]) -> float:
        """Calculate penalty for deal breakers"""
        penalty = 0.0

        if not criteria1 and not criteria2:
            return penalty

        # Check deal breakers for user1
        if criteria1 and criteria1.deal_breakers:
            for breaker in criteria1.deal_breakers:
                if self._is_deal_breaker_violated(breaker, profile2):
                    penalty += 50  # Heavy penalty for deal breakers

        # Check deal breakers for user2
        if criteria2 and criteria2.deal_breakers:
            for breaker in criteria2.deal_breakers:
                if self._is_deal_breaker_violated(breaker, profile1):
                    penalty += 50

        # Age preferences
        if criteria1 and criteria1.strict_age_preference and profile1.preferred_age_min and profile1.preferred_age_max:
            age2 = self._calculate_age(profile2.date_of_birth) if profile2.date_of_birth else None
            if age2 and not (profile1.preferred_age_min <= age2 <= profile1.preferred_age_max):
                penalty += 30

        if criteria2 and criteria2.strict_age_preference and profile2.preferred_age_min and profile2.preferred_age_max:
            age1 = self._calculate_age(profile1.date_of_birth) if profile1.date_of_birth else None
            if age1 and not (profile2.preferred_age_min <= age1 <= profile2.preferred_age_max):
                penalty += 30

        # Gender preferences
        if criteria1 and criteria1.strict_gender_preference and profile1.preferred_gender:
            if profile1.preferred_gender != 'any' and profile1.preferred_gender != profile2.gender:
                penalty += 40

        if criteria2 and criteria2.strict_gender_preference and profile2.preferred_gender:
            if profile2.preferred_gender != 'any' and profile2.preferred_gender != profile1.gender:
                penalty += 40

        return min(100, penalty)  # Cap at 100 points penalty

    def _is_deal_breaker_violated(self, deal_breaker: str, profile: UserProfile) -> bool:
        """Check if a deal breaker is violated"""
        deal_breaker_lower = deal_breaker.lower()

        if 'smoking' in deal_breaker_lower and profile.smoker == 'yes':
            return True
        if 'pets' in deal_breaker_lower and profile.pets == 'yes':
            return True
        if 'partying' in deal_breaker_lower and profile.social_level and profile.social_level >= 8:
            return True
        if 'messy' in deal_breaker_lower and profile.cleanliness_level and profile.cleanliness_level <= 3:
            return True

        return False

    def _calculate_age(self, date_of_birth) -> Optional[int]:
        """Calculate age from date of birth"""
        if not date_of_birth:
            return None
        today = timezone.now().date()
        return today.year - date_of_birth.year - ((today.month, today.day) < (date_of_birth.month, date_of_birth.day))


class MatchingService:
    """Service for managing the matching process"""

    def __init__(self):
        self.calculator = CompatibilityCalculator()

    def calculate_user_compatibility(self, user1: User, user2: User) -> CompatibilityScore:
        """Calculate and store compatibility score between two users"""
        start_time = time.time()

        # Ensure consistent ordering (lower ID first)
        if user1.id > user2.id:
            user1, user2 = user2, user1

        try:
            with transaction.atomic():
                # Calculate compatibility
                result = self.calculator.calculate_compatibility(user1, user2)

                # Create or update compatibility score
                compatibility_score, created = CompatibilityScore.objects.update_or_create(
                    user1=user1,
                    user2=user2,
                    defaults={
                        'overall_score': result['overall_score'],
                        'budget_score': result['budget_score'],
                        'location_score': result['location_score'],
                        'lifestyle_score': result['lifestyle_score'],
                        'schedule_score': result['schedule_score'],
                        'habits_score': result['habits_score'],
                        'score_breakdown': result['breakdown'],
                        'calculated_at': timezone.now(),
                        'is_active': True
                    }
                )

                # Log activity
                MatchingActivity.objects.create(
                    activity_type='score_calculation',
                    user=user1,
                    details={
                        'user1_id': user1.id,
                        'user2_id': user2.id,
                        'overall_score': result['overall_score'],
                        'created': created
                    },
                    execution_time_ms=int((time.time() - start_time) * 1000),
                    scores_calculated=1,
                    success=True
                )

                return compatibility_score

        except Exception as e:
            logger.error(f"Error calculating compatibility for users {user1.id} and {user2.id}: {str(e)}")

            # Log error
            MatchingActivity.objects.create(
                activity_type='score_calculation',
                user=user1,
                details={
                    'user1_id': user1.id,
                    'user2_id': user2.id,
                    'error': str(e)
                },
                execution_time_ms=int((time.time() - start_time) * 1000),
                success=False,
                error_message=str(e)
            )
            raise

    def generate_recommendations(self, target_user: User, limit: int = 10) -> List[UserRecommendation]:
        """Generate personalized recommendations for a user"""
        start_time = time.time()

        try:
            # Get all potential matches (users with complete profiles)
            potential_matches = User.objects.filter(
                profile_completed=True,
                is_active=True
            ).exclude(
                id=target_user.id
            ).select_related('profile')

            recommendations_created = 0
            compatibility_scores = []

            with transaction.atomic():
                # Calculate compatibility with all potential matches
                for potential_match in potential_matches:
                    try:
                        compatibility_score = self.calculate_user_compatibility(target_user, potential_match)
                        compatibility_scores.append(compatibility_score)
                    except Exception as e:
                        logger.warning(f"Failed to calculate compatibility between {target_user.id} and {potential_match.id}: {str(e)}")
                        continue

                # Sort by compatibility score and take top matches
                top_matches = sorted(
                    compatibility_scores,
                    key=lambda x: x.overall_score,
                    reverse=True
                )[:limit]

                # Generate recommendations
                recommendations = []
                for compatibility_score in top_matches:
                    # Determine which user is the recommended one
                    if compatibility_score.user1 == target_user:
                        recommended_user = compatibility_score.user2
                    else:
                        recommended_user = compatibility_score.user1

                    # Generate recommendation reason
                    reason = self._generate_recommendation_reason(compatibility_score)
                    highlighted_matches = self._generate_highlighted_matches(compatibility_score)

                    # Create recommendation
                    recommendation, created = UserRecommendation.objects.update_or_create(
                        target_user=target_user,
                        recommended_user=recommended_user,
                        defaults={
                            'compatibility_score': compatibility_score,
                            'reason': reason,
                            'highlighted_matches': highlighted_matches,
                            'is_dismissed': False
                        }
                    )

                    if created:
                        recommendations_created += 1

                    recommendations.append(recommendation)

                # Log activity
                MatchingActivity.objects.create(
                    activity_type='recommendation_generation',
                    user=target_user,
                    details={
                        'target_user_id': target_user.id,
                        'recommendations_limit': limit,
                        'potential_matches_count': potential_matches.count(),
                        'successful_calculations': len(compatibility_scores)
                    },
                    execution_time_ms=int((time.time() - start_time) * 1000),
                    recommendations_generated=recommendations_created,
                    success=True
                )

                return recommendations

        except Exception as e:
            logger.error(f"Error generating recommendations for user {target_user.id}: {str(e)}")

            # Log error
            MatchingActivity.objects.create(
                activity_type='recommendation_generation',
                user=target_user,
                details={
                    'target_user_id': target_user.id,
                    'error': str(e)
                },
                execution_time_ms=int((time.time() - start_time) * 1000),
                success=False,
                error_message=str(e)
            )

            return []

    def _generate_recommendation_reason(self, compatibility_score: CompatibilityScore) -> str:
        """Generate a human-readable reason for the recommendation"""
        breakdown = compatibility_score.score_breakdown

        # Find the highest scoring components
        component_scores = {
            'budget': breakdown.get('budget', {}).get('score', 0),
            'location': breakdown.get('location', {}).get('score', 0),
            'lifestyle': breakdown.get('lifestyle', {}).get('score', 0),
            'schedule': breakdown.get('schedule', {}).get('score', 0),
            'habits': breakdown.get('habits', {}).get('score', 0)
        }

        # Sort by score
        sorted_components = sorted(component_scores.items(), key=lambda x: x[1], reverse=True)

        reasons = []

        # Add reasons based on top scoring components
        for component, score in sorted_components[:3]:
            if score >= 80:
                component_reasons = {
                    'budget': "You have very compatible budget ranges",
                    'location': "You both prefer similar locations",
                    'lifestyle': "Your lifestyles are highly compatible",
                    'schedule': "Your schedules align well",
                    'habits': "You have similar cleanliness and living habits"
                }
                reasons.append(component_reasons.get(component, f"High {component} compatibility"))

        # Overall compatibility level
        overall_level = compatibility_score.compatibility_level.lower()

        if compatibility_score.overall_score >= 90:
            intro = "This is an excellent match! "
        elif compatibility_score.overall_score >= 80:
            intro = "This looks like a great potential roommate. "
        elif compatibility_score.overall_score >= 70:
            intro = "You have good compatibility. "
        else:
            intro = "There's moderate compatibility here. "

        if reasons:
            return intro + " ".join(reasons[:2]) + "."
        else:
            return intro + f"Overall compatibility score: {compatibility_score.overall_score:.0f}%."

    def _generate_highlighted_matches(self, compatibility_score: CompatibilityScore) -> List[str]:
        """Generate key factors to highlight about this match"""
        breakdown = compatibility_score.score_breakdown
        highlights = []

        # Check each component for high scores
        if breakdown.get('budget', {}).get('score', 0) >= 80:
            highlights.append("budget_compatible")

        if breakdown.get('location', {}).get('score', 0) >= 80:
            highlights.append("location_match")

        if breakdown.get('lifestyle', {}).get('score', 0) >= 80:
            highlights.append("lifestyle_compatible")

        if breakdown.get('schedule', {}).get('score', 0) >= 80:
            highlights.append("schedule_aligned")

        if breakdown.get('habits', {}).get('score', 0) >= 80:
            highlights.append("habits_compatible")

        # Add overall compatibility level
        if compatibility_score.overall_score >= 90:
            highlights.append("excellent_match")
        elif compatibility_score.overall_score >= 80:
            highlights.append("strong_match")

        return highlights

    def record_user_interaction(self, source_user: User, target_user: User,
                              interaction_type: str, was_recommended: bool = False,
                              metadata: Dict = None) -> UserInteraction:
        """Record a user interaction for algorithm improvement"""

        # Get current compatibility score if it exists
        compatibility_score_value = None
        try:
            user1, user2 = (source_user, target_user) if source_user.id < target_user.id else (target_user, source_user)
            compatibility_score = CompatibilityScore.objects.get(user1=user1, user2=user2)
            compatibility_score_value = compatibility_score.overall_score
        except CompatibilityScore.DoesNotExist:
            pass

        interaction = UserInteraction.objects.create(
            source_user=source_user,
            target_user=target_user,
            interaction_type=interaction_type,
            was_recommended=was_recommended,
            compatibility_score_at_time=compatibility_score_value,
            metadata=metadata or {}
        )

        return interaction

    def get_user_recommendations(self, user: User, refresh: bool = False) -> List[UserRecommendation]:
        """Get recommendations for a user"""

        # Check if we need to refresh recommendations
        if refresh or not UserRecommendation.objects.filter(target_user=user, is_dismissed=False).exists():
            return self.generate_recommendations(user)

        # Return existing recommendations
        return UserRecommendation.objects.filter(
            target_user=user,
            is_dismissed=False
        ).select_related(
            'recommended_user__profile',
            'compatibility_score'
        ).order_by('-compatibility_score__overall_score')