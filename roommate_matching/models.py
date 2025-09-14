from django.db import models
from django.contrib.auth import get_user_model
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone
from decimal import Decimal
import json

User = get_user_model()


class CompatibilityScore(models.Model):
    """Compatibility score between two users"""

    user1 = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='compatibility_scores_as_user1'
    )
    user2 = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='compatibility_scores_as_user2'
    )

    # Overall compatibility score (0-100)
    overall_score = models.FloatField(
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="Overall compatibility score from 0-100"
    )

    # Individual component scores
    lifestyle_score = models.FloatField(default=0.0)
    budget_score = models.FloatField(default=0.0)
    location_score = models.FloatField(default=0.0)
    schedule_score = models.FloatField(default=0.0)
    preferences_score = models.FloatField(default=0.0)
    habits_score = models.FloatField(default=0.0)

    # Score breakdown as JSON for detailed analysis
    score_breakdown = models.JSONField(default=dict, help_text="Detailed score breakdown")

    # Metadata
    calculated_at = models.DateTimeField(default=timezone.now)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = 'roommate_matching_compatibilityscore'
        unique_together = ['user1', 'user2']
        ordering = ['-overall_score']
        indexes = [
            models.Index(fields=['user1', 'overall_score']),
            models.Index(fields=['user2', 'overall_score']),
            models.Index(fields=['overall_score']),
        ]

    def __str__(self):
        return f"{self.user1.get_short_name()} & {self.user2.get_short_name()}: {self.overall_score:.1f}%"

    @property
    def compatibility_level(self):
        """Return compatibility level as string"""
        if self.overall_score >= 90:
            return 'Excellent'
        elif self.overall_score >= 80:
            return 'Very Good'
        elif self.overall_score >= 70:
            return 'Good'
        elif self.overall_score >= 60:
            return 'Fair'
        elif self.overall_score >= 50:
            return 'Moderate'
        else:
            return 'Low'

    @property
    def match_strength(self):
        """Return match strength for UI display"""
        if self.overall_score >= 80:
            return 'strong'
        elif self.overall_score >= 60:
            return 'moderate'
        else:
            return 'weak'


class UserRecommendation(models.Model):
    """Personalized user recommendations based on compatibility"""

    target_user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='recommendations'
    )
    recommended_user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='recommended_to'
    )

    compatibility_score = models.ForeignKey(
        CompatibilityScore,
        on_delete=models.CASCADE,
        related_name='recommendations'
    )

    # Recommendation context
    reason = models.TextField(help_text="Why this user is recommended")
    highlighted_matches = models.JSONField(
        default=list,
        help_text="Key matching factors to highlight"
    )

    # Status tracking
    is_viewed = models.BooleanField(default=False)
    is_contacted = models.BooleanField(default=False)
    is_dismissed = models.BooleanField(default=False)

    # Metadata
    created_at = models.DateTimeField(default=timezone.now)
    viewed_at = models.DateTimeField(null=True, blank=True)
    contacted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'roommate_matching_userrecommendation'
        unique_together = ['target_user', 'recommended_user']
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['target_user', 'is_dismissed']),
            models.Index(fields=['recommended_user']),
        ]

    def __str__(self):
        return f"Recommend {self.recommended_user.get_short_name()} to {self.target_user.get_short_name()}"

    def mark_viewed(self):
        """Mark recommendation as viewed"""
        if not self.is_viewed:
            self.is_viewed = True
            self.viewed_at = timezone.now()
            self.save(update_fields=['is_viewed', 'viewed_at'])

    def mark_contacted(self):
        """Mark recommendation as contacted"""
        if not self.is_contacted:
            self.is_contacted = True
            self.contacted_at = timezone.now()
            self.save(update_fields=['is_contacted', 'contacted_at'])


class MatchingCriteria(models.Model):
    """User-defined matching criteria and weights"""

    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='matching_criteria'
    )

    # Importance weights (1-5 scale)
    budget_importance = models.IntegerField(
        default=5,
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        help_text="How important is budget compatibility (1-5)"
    )
    location_importance = models.IntegerField(
        default=4,
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        help_text="How important is location compatibility (1-5)"
    )
    lifestyle_importance = models.IntegerField(
        default=4,
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        help_text="How important is lifestyle compatibility (1-5)"
    )
    schedule_importance = models.IntegerField(
        default=3,
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        help_text="How important is schedule compatibility (1-5)"
    )
    habits_importance = models.IntegerField(
        default=4,
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        help_text="How important are habits/cleanliness compatibility (1-5)"
    )

    # Deal breakers
    deal_breakers = models.JSONField(
        default=list,
        help_text="Absolute deal breakers (smoking, pets, etc.)"
    )

    # Preferred matches
    preferred_traits = models.JSONField(
        default=list,
        help_text="Preferred traits in roommates"
    )

    # Age preferences
    strict_age_preference = models.BooleanField(
        default=False,
        help_text="Strictly enforce age preferences"
    )

    # Gender preferences
    strict_gender_preference = models.BooleanField(
        default=False,
        help_text="Strictly enforce gender preferences"
    )

    # Metadata
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'roommate_matching_matchingcriteria'
        verbose_name_plural = 'Matching Criteria'

    def __str__(self):
        return f"{self.user.get_short_name()}'s matching criteria"

    @property
    def total_importance_weight(self):
        """Calculate total importance weight for normalization"""
        return (
            self.budget_importance +
            self.location_importance +
            self.lifestyle_importance +
            self.schedule_importance +
            self.habits_importance
        )


class MatchingActivity(models.Model):
    """Track matching algorithm activity and performance"""

    ACTIVITY_TYPES = [
        ('score_calculation', 'Score Calculation'),
        ('recommendation_generation', 'Recommendation Generation'),
        ('criteria_update', 'Criteria Update'),
        ('batch_processing', 'Batch Processing'),
    ]

    activity_type = models.CharField(max_length=30, choices=ACTIVITY_TYPES)
    user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='matching_activities'
    )

    # Activity details
    details = models.JSONField(default=dict)
    success = models.BooleanField(default=True)
    error_message = models.TextField(blank=True)

    # Performance metrics
    execution_time_ms = models.PositiveIntegerField(null=True, blank=True)
    scores_calculated = models.PositiveIntegerField(default=0)
    recommendations_generated = models.PositiveIntegerField(default=0)

    # Metadata
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = 'roommate_matching_matchingactivity'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['activity_type', 'created_at']),
            models.Index(fields=['user', 'created_at']),
        ]

    def __str__(self):
        return f"{self.get_activity_type_display()} - {self.created_at.strftime('%Y-%m-%d %H:%M')}"


class UserInteraction(models.Model):
    """Track user interactions for improving matching algorithm"""

    INTERACTION_TYPES = [
        ('view_profile', 'View Profile'),
        ('send_message', 'Send Message'),
        ('like_profile', 'Like Profile'),
        ('dismiss_recommendation', 'Dismiss Recommendation'),
        ('report_user', 'Report User'),
        ('block_user', 'Block User'),
    ]

    source_user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='interactions_made'
    )
    target_user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='interactions_received'
    )

    interaction_type = models.CharField(max_length=30, choices=INTERACTION_TYPES)

    # Context
    was_recommended = models.BooleanField(
        default=False,
        help_text="Was this interaction from a recommendation"
    )
    compatibility_score_at_time = models.FloatField(null=True, blank=True)

    # Additional data
    metadata = models.JSONField(default=dict)

    # Timestamps
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = 'roommate_matching_userinteraction'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['source_user', 'interaction_type']),
            models.Index(fields=['target_user', 'interaction_type']),
            models.Index(fields=['was_recommended']),
        ]

    def __str__(self):
        return f"{self.source_user.get_short_name()} -> {self.target_user.get_short_name()}: {self.get_interaction_type_display()}"