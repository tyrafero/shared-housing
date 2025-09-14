from django.contrib import admin
from .models import UserProfile


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = (
        'user', 'age', 'occupation', 'budget_range', 'preferred_room_type',
        'completion_percentage', 'created_at'
    )
    list_filter = (
        'gender', 'occupation', 'education_level', 'preferred_room_type',
        'lease_duration', 'smoker', 'pets', 'phone_verified', 'id_verified'
    )
    search_fields = ('user__email', 'user__first_name', 'user__last_name', 'occupation', 'bio')
    readonly_fields = ('created_at', 'updated_at', 'profile_views', 'completion_percentage')

    fieldsets = (
        ('User', {
            'fields': ('user',)
        }),
        ('Personal Information', {
            'fields': ('date_of_birth', 'gender', 'occupation', 'education_level')
        }),
        ('Location & Transport', {
            'fields': ('preferred_locations', 'max_commute_time', 'has_car')
        }),
        ('Budget & Housing', {
            'fields': ('min_budget', 'max_budget', 'preferred_room_type', 'lease_duration', 'move_in_date')
        }),
        ('Lifestyle', {
            'fields': ('cleanliness_level', 'noise_tolerance', 'social_level')
        }),
        ('Habits', {
            'fields': ('smoker', 'drinking', 'pets')
        }),
        ('Work/Study', {
            'fields': ('schedule_type', 'works_from_home')
        }),
        ('Roommate Preferences', {
            'fields': ('preferred_age_min', 'preferred_age_max', 'preferred_gender', 'max_roommates')
        }),
        ('About', {
            'fields': ('bio', 'interests', 'languages')
        }),
        ('Verification', {
            'fields': ('phone_verified', 'id_verified', 'background_check', 'references_provided')
        }),
        ('Media', {
            'fields': ('profile_picture', 'additional_photos')
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at', 'profile_views', 'completion_percentage'),
            'classes': ('collapse',)
        }),
    )

    def budget_range(self, obj):
        if obj.min_budget and obj.max_budget:
            return f"${obj.min_budget} - ${obj.max_budget}"
        elif obj.min_budget:
            return f"${obj.min_budget}+"
        elif obj.max_budget:
            return f"Up to ${obj.max_budget}"
        return "Not specified"
    budget_range.short_description = "Budget Range"

    def completion_percentage(self, obj):
        return f"{obj.completion_percentage}%"
    completion_percentage.short_description = "Profile Complete"