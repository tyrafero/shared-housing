from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.db.models import Count, Avg, Q
from .models import (
    CompatibilityScore, UserRecommendation, MatchingCriteria,
    MatchingActivity, UserInteraction
)


@admin.register(CompatibilityScore)
class CompatibilityScoreAdmin(admin.ModelAdmin):
    list_display = (
        'user_pair', 'overall_score', 'compatibility_level', 'match_strength',
        'lifestyle_score', 'budget_score', 'calculated_at', 'is_active'
    )
    list_filter = (
        'calculated_at', 'is_active',
        'user1__profile__gender', 'user2__profile__gender'
    )
    search_fields = (
        'user1__email', 'user1__first_name', 'user1__last_name',
        'user2__email', 'user2__first_name', 'user2__last_name'
    )
    readonly_fields = ('calculated_at', 'compatibility_level', 'match_strength')
    date_hierarchy = 'calculated_at'

    fieldsets = (
        ('Users', {
            'fields': ('user1', 'user2')
        }),
        ('Overall Score', {
            'fields': ('overall_score', 'compatibility_level', 'match_strength')
        }),
        ('Component Scores', {
            'fields': ('lifestyle_score', 'budget_score', 'location_score', 'schedule_score', 'habits_score')
        }),
        ('Detailed Analysis', {
            'fields': ('score_breakdown',),
            'classes': ('collapse',)
        }),
        ('Status', {
            'fields': ('is_active', 'calculated_at')
        })
    )

    def user_pair(self, obj):
        return f"{obj.user1.get_short_name()} ↔ {obj.user2.get_short_name()}"
    user_pair.short_description = 'User Pair'

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user1', 'user2')


@admin.register(UserRecommendation)
class UserRecommendationAdmin(admin.ModelAdmin):
    list_display = (
        'target_user', 'recommended_user', 'compatibility_score_value',
        'status_badges', 'created_at', 'viewed_at'
    )
    list_filter = (
        'is_viewed', 'is_contacted', 'is_dismissed', 'created_at',
        'target_user__profile__gender', 'recommended_user__profile__gender'
    )
    search_fields = (
        'target_user__email', 'target_user__first_name', 'target_user__last_name',
        'recommended_user__email', 'recommended_user__first_name', 'recommended_user__last_name'
    )
    readonly_fields = ('created_at', 'viewed_at', 'contacted_at', 'status_badges')
    date_hierarchy = 'created_at'

    fieldsets = (
        ('Recommendation', {
            'fields': ('target_user', 'recommended_user', 'compatibility_score')
        }),
        ('Reason & Highlights', {
            'fields': ('reason', 'highlighted_matches')
        }),
        ('Status', {
            'fields': ('status_badges', 'is_viewed', 'is_contacted', 'is_dismissed')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'viewed_at', 'contacted_at')
        })
    )

    def compatibility_score_value(self, obj):
        if obj.compatibility_score:
            return f"{obj.compatibility_score.overall_score:.1f}%"
        return "N/A"
    compatibility_score_value.short_description = 'Compatibility'

    def status_badges(self, obj):
        badges = []
        if obj.is_viewed:
            badges.append('<span class="badge badge-info">Viewed</span>')
        if obj.is_contacted:
            badges.append('<span class="badge badge-success">Contacted</span>')
        if obj.is_dismissed:
            badges.append('<span class="badge badge-warning">Dismissed</span>')
        if not badges:
            badges.append('<span class="badge badge-secondary">New</span>')
        return format_html(' '.join(badges))
    status_badges.short_description = 'Status'

    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            'target_user', 'recommended_user', 'compatibility_score'
        )


@admin.register(MatchingCriteria)
class MatchingCriteriaAdmin(admin.ModelAdmin):
    list_display = (
        'user', 'importance_summary', 'strict_preferences',
        'deal_breakers_count', 'created_at', 'updated_at'
    )
    list_filter = (
        'strict_age_preference', 'strict_gender_preference',
        'budget_importance', 'lifestyle_importance', 'created_at'
    )
    search_fields = ('user__email', 'user__first_name', 'user__last_name')
    readonly_fields = ('created_at', 'updated_at', 'total_importance_weight')

    fieldsets = (
        ('User', {
            'fields': ('user',)
        }),
        ('Importance Weights (1-5)', {
            'fields': (
                'budget_importance', 'location_importance', 'lifestyle_importance',
                'schedule_importance', 'habits_importance', 'total_importance_weight'
            )
        }),
        ('Preferences', {
            'fields': ('deal_breakers', 'preferred_traits')
        }),
        ('Strict Matching', {
            'fields': ('strict_age_preference', 'strict_gender_preference')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at')
        })
    )

    def importance_summary(self, obj):
        return f"B:{obj.budget_importance} L:{obj.location_importance} LS:{obj.lifestyle_importance} S:{obj.schedule_importance} H:{obj.habits_importance}"
    importance_summary.short_description = 'Importance (B/L/LS/S/H)'

    def strict_preferences(self, obj):
        prefs = []
        if obj.strict_age_preference:
            prefs.append('Age')
        if obj.strict_gender_preference:
            prefs.append('Gender')
        return ', '.join(prefs) if prefs else 'None'
    strict_preferences.short_description = 'Strict Prefs'

    def deal_breakers_count(self, obj):
        return len(obj.deal_breakers) if obj.deal_breakers else 0
    deal_breakers_count.short_description = 'Deal Breakers'

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user')


@admin.register(MatchingActivity)
class MatchingActivityAdmin(admin.ModelAdmin):
    list_display = (
        'activity_type', 'user', 'success', 'execution_time_ms',
        'scores_calculated', 'recommendations_generated', 'created_at'
    )
    list_filter = ('activity_type', 'success', 'created_at')
    search_fields = ('user__email', 'user__first_name', 'user__last_name', 'error_message')
    readonly_fields = ('created_at',)
    date_hierarchy = 'created_at'

    fieldsets = (
        ('Activity', {
            'fields': ('activity_type', 'user', 'success')
        }),
        ('Performance', {
            'fields': ('execution_time_ms', 'scores_calculated', 'recommendations_generated')
        }),
        ('Details', {
            'fields': ('details', 'error_message'),
            'classes': ('collapse',)
        }),
        ('Timestamp', {
            'fields': ('created_at',)
        })
    )

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user')


@admin.register(UserInteraction)
class UserInteractionAdmin(admin.ModelAdmin):
    list_display = (
        'source_user', 'target_user', 'interaction_type',
        'was_recommended', 'compatibility_score_at_time', 'created_at'
    )
    list_filter = ('interaction_type', 'was_recommended', 'created_at')
    search_fields = (
        'source_user__email', 'source_user__first_name', 'source_user__last_name',
        'target_user__email', 'target_user__first_name', 'target_user__last_name'
    )
    readonly_fields = ('created_at',)
    date_hierarchy = 'created_at'

    fieldsets = (
        ('Users', {
            'fields': ('source_user', 'target_user')
        }),
        ('Interaction', {
            'fields': ('interaction_type', 'was_recommended', 'compatibility_score_at_time')
        }),
        ('Metadata', {
            'fields': ('metadata',),
            'classes': ('collapse',)
        }),
        ('Timestamp', {
            'fields': ('created_at',)
        })
    )

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('source_user', 'target_user')