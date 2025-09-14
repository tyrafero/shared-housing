from django.db import models
from django.contrib.auth import get_user_model
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone

User = get_user_model()


class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')

    # Personal Information
    date_of_birth = models.DateField(null=True, blank=True)
    gender = models.CharField(max_length=20, choices=[
        ('male', 'Male'),
        ('female', 'Female'),
        ('non_binary', 'Non-binary'),
        ('prefer_not_say', 'Prefer not to say'),
    ], blank=True)
    occupation = models.CharField(max_length=100, blank=True)
    education_level = models.CharField(max_length=50, choices=[
        ('high_school', 'High School'),
        ('bachelor', "Bachelor's Degree"),
        ('master', "Master's Degree"),
        ('phd', 'PhD'),
        ('trade', 'Trade/Vocational'),
        ('other', 'Other'),
    ], blank=True)

    # Location Preferences
    preferred_locations = models.JSONField(default=list, help_text="List of preferred suburbs/areas")
    max_commute_time = models.IntegerField(
        null=True, blank=True,
        validators=[MinValueValidator(5), MaxValueValidator(120)],
        help_text="Maximum commute time in minutes"
    )
    has_car = models.BooleanField(default=False)

    # Budget and Housing
    min_budget = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    max_budget = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    preferred_room_type = models.CharField(max_length=30, choices=[
        ('private', 'Private Room'),
        ('shared', 'Shared Room'),
        ('master', 'Master Room with Ensuite'),
        ('studio', 'Studio/Granny Flat'),
    ], blank=True)
    lease_duration = models.CharField(max_length=20, choices=[
        ('short', 'Short-term (1-6 months)'),
        ('medium', 'Medium-term (6-12 months)'),
        ('long', 'Long-term (12+ months)'),
        ('flexible', 'Flexible'),
    ], blank=True)
    move_in_date = models.DateField(null=True, blank=True)

    # Lifestyle Preferences
    cleanliness_level = models.IntegerField(
        default=5,
        validators=[MinValueValidator(1), MaxValueValidator(10)],
        help_text="1 = Very messy, 10 = Extremely clean"
    )
    noise_tolerance = models.IntegerField(
        default=5,
        validators=[MinValueValidator(1), MaxValueValidator(10)],
        help_text="1 = Need complete quiet, 10 = Don't mind noise"
    )
    social_level = models.IntegerField(
        default=5,
        validators=[MinValueValidator(1), MaxValueValidator(10)],
        help_text="1 = Very private, 10 = Very social"
    )

    # Habits
    smoker = models.CharField(max_length=20, choices=[
        ('never', 'Never'),
        ('occasionally', 'Occasionally'),
        ('regularly', 'Regularly'),
    ], default='never')
    drinking = models.CharField(max_length=20, choices=[
        ('never', 'Never'),
        ('socially', 'Socially'),
        ('regularly', 'Regularly'),
    ], default='socially')
    pets = models.CharField(max_length=30, choices=[
        ('none', 'No pets'),
        ('cat', 'Have cat(s)'),
        ('dog', 'Have dog(s)'),
        ('other', 'Have other pets'),
        ('want_pets', 'Want to get pets'),
    ], default='none')

    # Work/Study Schedule
    schedule_type = models.CharField(max_length=20, choices=[
        ('regular', 'Regular 9-5'),
        ('shift', 'Shift work'),
        ('flexible', 'Flexible hours'),
        ('student', 'Student'),
        ('freelance', 'Freelance/Self-employed'),
    ], blank=True)
    works_from_home = models.BooleanField(default=False)

    # Preferences for Roommates
    preferred_age_min = models.IntegerField(
        null=True, blank=True,
        validators=[MinValueValidator(18), MaxValueValidator(99)]
    )
    preferred_age_max = models.IntegerField(
        null=True, blank=True,
        validators=[MinValueValidator(18), MaxValueValidator(99)]
    )
    preferred_gender = models.CharField(max_length=20, choices=[
        ('any', 'No preference'),
        ('same', 'Same gender only'),
        ('female_only', 'Female only'),
        ('male_only', 'Male only'),
    ], default='any')
    max_roommates = models.IntegerField(
        default=3,
        validators=[MinValueValidator(1), MaxValueValidator(10)]
    )

    # Bio and Additional Info
    bio = models.TextField(max_length=1000, blank=True, help_text="Tell others about yourself")
    interests = models.JSONField(default=list, help_text="List of interests/hobbies")
    languages = models.JSONField(default=list, help_text="Languages spoken")

    # Verification and Safety
    phone_verified = models.BooleanField(default=False)
    id_verified = models.BooleanField(default=False)
    background_check = models.BooleanField(default=False)
    references_provided = models.BooleanField(default=False)

    # Profile Media
    profile_picture = models.ImageField(upload_to='profiles/pictures/', null=True, blank=True)
    additional_photos = models.JSONField(default=list, help_text="List of additional photo URLs")

    # Metadata
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    profile_views = models.PositiveIntegerField(default=0)

    class Meta:
        db_table = 'profiles_userprofile'
        verbose_name = 'User Profile'
        verbose_name_plural = 'User Profiles'

    def __str__(self):
        return f"{self.user.get_full_name()}'s Profile"

    @property
    def age(self):
        if self.date_of_birth:
            today = timezone.now().date()
            return today.year - self.date_of_birth.year - (
                (today.month, today.day) < (self.date_of_birth.month, self.date_of_birth.day)
            )
        return None

    @property
    def is_complete(self):
        """Check if profile has minimum required fields completed"""
        required_fields = [
            'date_of_birth', 'occupation', 'min_budget', 'max_budget',
            'preferred_room_type', 'cleanliness_level', 'bio'
        ]
        return all(getattr(self, field) for field in required_fields if hasattr(self, field))

    @property
    def completion_percentage(self):
        """Calculate profile completion percentage"""
        fields_to_check = [
            'date_of_birth', 'gender', 'occupation', 'education_level',
            'preferred_locations', 'min_budget', 'max_budget', 'preferred_room_type',
            'lease_duration', 'move_in_date', 'bio', 'profile_picture'
        ]

        completed_fields = 0
        for field in fields_to_check:
            value = getattr(self, field)
            if value:  # Check if field has a value (not empty list, None, etc.)
                if isinstance(value, list) and len(value) > 0:
                    completed_fields += 1
                elif not isinstance(value, list):
                    completed_fields += 1

        return round((completed_fields / len(fields_to_check)) * 100)

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        # Update user's profile_completed status
        if self.is_complete and not self.user.profile_completed:
            self.user.profile_completed = True
            self.user.save(update_fields=['profile_completed'])