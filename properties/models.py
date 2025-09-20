from django.db import models
from django.contrib.auth import get_user_model
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone
from django.urls import reverse
from decimal import Decimal
import logging

logger = logging.getLogger(__name__)

User = get_user_model()


class Property(models.Model):
    """Main property model for rental listings"""

    # Basic Information
    title = models.CharField(max_length=200, help_text="Property listing title")
    description = models.TextField(help_text="Detailed description of the property")
    property_type = models.CharField(max_length=30, choices=[
        ('house', 'House'),
        ('apartment', 'Apartment'),
        ('townhouse', 'Townhouse'),
        ('studio', 'Studio'),
        ('room', 'Single Room'),
        ('granny_flat', 'Granny Flat'),
    ])

    # Location Details
    address = models.CharField(max_length=300)
    suburb = models.CharField(max_length=100)
    state = models.CharField(max_length=20, choices=[
        ('NSW', 'New South Wales'),
        ('VIC', 'Victoria'),
        ('QLD', 'Queensland'),
        ('WA', 'Western Australia'),
        ('SA', 'South Australia'),
        ('TAS', 'Tasmania'),
        ('NT', 'Northern Territory'),
        ('ACT', 'Australian Capital Territory'),
    ])
    postcode = models.CharField(max_length=10)
    latitude = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    longitude = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)

    # Property Specifications
    bedrooms = models.PositiveIntegerField(validators=[MinValueValidator(1), MaxValueValidator(20)])
    bathrooms = models.PositiveIntegerField(validators=[MinValueValidator(1), MaxValueValidator(10)])
    car_spaces = models.PositiveIntegerField(default=0, validators=[MaxValueValidator(10)])
    total_rooms = models.PositiveIntegerField(null=True, blank=True)

    # Financial Information
    rent_per_week = models.DecimalField(max_digits=8, decimal_places=2)
    bond_amount = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    rent_includes = models.JSONField(default=list, help_text="List of what's included in rent")
    additional_costs = models.JSONField(default=dict, help_text="Additional costs like utilities")

    # Availability
    available_from = models.DateField()
    available_until = models.DateField(null=True, blank=True, help_text="Leave empty for ongoing")
    min_lease_term = models.PositiveIntegerField(
        default=12,
        help_text="Minimum lease term in months",
        validators=[MinValueValidator(1), MaxValueValidator(60)]
    )
    max_lease_term = models.PositiveIntegerField(
        null=True, blank=True,
        help_text="Maximum lease term in months",
        validators=[MinValueValidator(1), MaxValueValidator(60)]
    )

    # Property Features
    furnished = models.CharField(max_length=20, choices=[
        ('unfurnished', 'Unfurnished'),
        ('semi_furnished', 'Semi-furnished'),
        ('fully_furnished', 'Fully Furnished'),
    ], default='unfurnished')

    pets_allowed = models.BooleanField(default=False)
    smoking_allowed = models.BooleanField(default=False)
    features = models.JSONField(default=list, help_text="List of property features")
    appliances = models.JSONField(default=list, help_text="List of included appliances")

    # Transport & Connectivity
    public_transport = models.JSONField(default=dict, help_text="Public transport information")
    internet_included = models.BooleanField(default=False)

    # Room Information (for shared properties)
    rooms_available = models.PositiveIntegerField(
        default=1,
        validators=[MinValueValidator(1), MaxValueValidator(10)],
        help_text="Number of rooms available for rent"
    )
    current_occupants = models.PositiveIntegerField(default=0, validators=[MaxValueValidator(20)])
    max_occupants = models.PositiveIntegerField(validators=[MinValueValidator(1), MaxValueValidator(20)])

    # Contact & Management
    contact_person = models.CharField(max_length=100, null=True, blank=True)
    contact_email = models.EmailField(null=True, blank=True)
    contact_phone = models.CharField(max_length=20, null=True, blank=True)
    agency = models.CharField(max_length=100, null=True, blank=True)
    listing_agent = models.CharField(max_length=100, null=True, blank=True)

    # External References
    external_id = models.CharField(max_length=50, null=True, blank=True, help_text="External listing ID")
    source_website = models.CharField(max_length=100, null=True, blank=True)
    external_url = models.URLField(null=True, blank=True)

    # Status and Metadata
    is_active = models.BooleanField(default=True)
    is_verified = models.BooleanField(default=False)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    view_count = models.PositiveIntegerField(default=0)

    # User interactions
    added_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='properties_added')
    favorited_by = models.ManyToManyField(User, blank=True, related_name='favorite_properties')

    # Amenities
    amenities = models.ManyToManyField('PropertyAmenity', blank=True, related_name='properties')

    class Meta:
        db_table = 'properties_property'
        verbose_name = 'Property'
        verbose_name_plural = 'Properties'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['suburb', 'state']),
            models.Index(fields=['rent_per_week']),
            models.Index(fields=['available_from']),
            models.Index(fields=['bedrooms', 'bathrooms']),
        ]

    def __str__(self):
        return f"{self.title} - {self.suburb}, {self.state}"

    def get_absolute_url(self):
        return reverse('properties:detail', kwargs={'pk': self.pk})

    @property
    def rent_per_person_estimate(self):
        """Estimate rent per person based on max occupants"""
        if self.max_occupants > 0:
            return self.rent_per_week / self.max_occupants
        return self.rent_per_week

    @property
    def full_address(self):
        return f"{self.address}, {self.suburb} {self.state} {self.postcode}"

    @property
    def is_available_now(self):
        return self.available_from <= timezone.now().date()

    @property
    def rooms_remaining(self):
        return self.rooms_available

    def save(self, *args, **kwargs):
        """Override save to automatically geocode address if coordinates are missing"""
        # Check if we need to geocode (no coordinates or address changed)
        need_geocoding = False

        if not self.latitude or not self.longitude:
            need_geocoding = True
            logger.info(f"Property {self.title} missing coordinates, will geocode")
        elif self.pk:  # Existing property - check if address changed
            try:
                old_instance = Property.objects.get(pk=self.pk)
                if (old_instance.address != self.address or
                    old_instance.suburb != self.suburb or
                    old_instance.state != self.state):
                    need_geocoding = True
                    logger.info(f"Property {self.title} address changed, will re-geocode")
            except Property.DoesNotExist:
                pass

        # Perform geocoding if needed
        if need_geocoding and self.address and self.suburb and self.state:
            try:
                from .geocoding import GeocodingService
                lat, lon = GeocodingService.geocode_with_retry(
                    address=self.address,
                    suburb=self.suburb,
                    state=self.state
                )
                if lat and lon:
                    self.latitude = lat
                    self.longitude = lon
                    logger.info(f"Successfully geocoded {self.title}: ({lat}, {lon})")
                else:
                    logger.warning(f"Failed to geocode {self.title}: {self.address}, {self.suburb}, {self.state}")
            except Exception as e:
                logger.error(f"Error during geocoding for {self.title}: {e}")

        super().save(*args, **kwargs)


class PropertyImage(models.Model):
    """Property images for listings"""

    property_listing = models.ForeignKey(Property, on_delete=models.CASCADE, related_name='images')
    image = models.ImageField(upload_to='properties/images/', blank=True, null=True)
    image_url = models.URLField(blank=True, null=True, help_text="Alternative to uploading: provide image URL")
    caption = models.CharField(max_length=200, blank=True)
    is_primary = models.BooleanField(default=False)
    order = models.PositiveIntegerField(default=0)
    uploaded_at = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = 'properties_propertyimage'
        ordering = ['order', 'uploaded_at']

    def __str__(self):
        return f"Image for {self.property_listing.title}"

    @property
    def image_src(self):
        """Return the image source - either uploaded file URL or external URL"""
        if self.image:
            return self.image.url
        elif self.image_url:
            return self.image_url
        return None


class RoomListing(models.Model):
    """Individual room within a property"""

    property_listing = models.ForeignKey(Property, on_delete=models.CASCADE, related_name='room_listings')

    # Room Details
    room_type = models.CharField(max_length=30, choices=[
        ('single', 'Single Room'),
        ('double', 'Double Room'),
        ('master', 'Master Room'),
        ('ensuite', 'Room with Ensuite'),
        ('shared', 'Shared Room'),
    ])

    size_sqm = models.PositiveIntegerField(null=True, blank=True, help_text="Room size in square meters")
    has_ensuite = models.BooleanField(default=False)
    has_balcony = models.BooleanField(default=False)
    has_built_in_wardrobe = models.BooleanField(default=False)

    # Pricing
    rent_per_week = models.DecimalField(max_digits=6, decimal_places=2)
    bond_weeks = models.PositiveIntegerField(default=4, help_text="Bond in weeks of rent")

    # Availability
    available_from = models.DateField()
    is_available = models.BooleanField(default=True)

    # Room Features
    furnished = models.BooleanField(default=False)
    includes_utilities = models.BooleanField(default=False)
    features = models.JSONField(default=list, help_text="Room-specific features")

    # Current Occupant (if shared room)
    current_occupant = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='current_rooms'
    )

    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'properties_roomlisting'
        ordering = ['rent_per_week']

    def __str__(self):
        return f"{self.get_room_type_display()} at {self.property_listing.title}"

    @property
    def bond_amount(self):
        return self.rent_per_week * self.bond_weeks

    @property
    def weekly_cost_estimate(self):
        """Estimate total weekly cost including utilities"""
        base_rent = self.rent_per_week
        if not self.includes_utilities:
            # Estimate utilities (this could be made more sophisticated)
            utilities_estimate = base_rent * Decimal('0.15')  # ~15% of rent
            return base_rent + utilities_estimate
        return base_rent


class PropertyAmenity(models.Model):
    """Standardized amenities for properties"""

    CATEGORY_CHOICES = [
        ('indoor', 'Indoor Features'),
        ('outdoor', 'Outdoor Features'),
        ('transport', 'Transport'),
        ('utilities', 'Utilities'),
        ('security', 'Security'),
        ('lifestyle', 'Lifestyle'),
    ]

    name = models.CharField(max_length=100, unique=True)
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES)
    icon = models.CharField(max_length=50, blank=True, help_text="Bootstrap icon class")
    description = models.TextField(blank=True)

    class Meta:
        db_table = 'properties_propertyamenity'
        ordering = ['category', 'name']

    def __str__(self):
        return self.name


class PropertyInspection(models.Model):
    """Scheduled property inspections"""

    property_listing = models.ForeignKey(Property, on_delete=models.CASCADE, related_name='inspections')
    datetime = models.DateTimeField()
    duration_minutes = models.PositiveIntegerField(default=30)
    max_attendees = models.PositiveIntegerField(default=10)
    contact_person = models.CharField(max_length=100)
    contact_phone = models.CharField(max_length=20)
    notes = models.TextField(blank=True)

    # Attendees
    registered_users = models.ManyToManyField(User, blank=True, related_name='property_inspections')

    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = 'properties_propertyinspection'
        ordering = ['datetime']

    def __str__(self):
        return f"Inspection: {self.property_listing.title} on {self.datetime.strftime('%Y-%m-%d %H:%M')}"

    @property
    def is_upcoming(self):
        return self.datetime > timezone.now()

    @property
    def spots_remaining(self):
        return max(0, self.max_attendees - self.registered_users.count())

    @property
    def is_full(self):
        return self.registered_users.count() >= self.max_attendees


class PropertySavedSearch(models.Model):
    """User's saved property search criteria"""

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='saved_searches')
    name = models.CharField(max_length=100, help_text="User's name for this search")

    # Search Criteria
    suburbs = models.JSONField(default=list)
    min_rent = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    max_rent = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    min_bedrooms = models.PositiveIntegerField(null=True, blank=True)
    max_bedrooms = models.PositiveIntegerField(null=True, blank=True)
    property_types = models.JSONField(default=list)
    pets_allowed = models.BooleanField(null=True, blank=True)
    furnished = models.CharField(max_length=20, blank=True)
    available_from = models.DateField(null=True, blank=True)

    # Notification settings
    email_notifications = models.BooleanField(default=True)
    notification_frequency = models.CharField(max_length=20, choices=[
        ('immediate', 'Immediate'),
        ('daily', 'Daily Digest'),
        ('weekly', 'Weekly Digest'),
    ], default='daily')

    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(default=timezone.now)
    last_notification_sent = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'properties_propertysavedsearch'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.user.get_short_name()}'s search: {self.name}"


class PropertyRequirements(models.Model):
    """Property owner requirements and preferences for tenants"""
    
    property = models.OneToOneField(Property, on_delete=models.CASCADE, related_name='requirements')
    
    # Financial Requirements
    minimum_combined_income = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True,
        help_text="Minimum combined annual income required"
    )
    income_verification_required = models.BooleanField(default=True)
    employment_verification_required = models.BooleanField(default=True)
    
    # Group Size Preferences
    preferred_group_size = models.PositiveIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(10)],
        help_text="Preferred number of tenants"
    )
    min_group_size = models.PositiveIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(10)],
        default=1
    )
    max_group_size = models.PositiveIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(10)]
    )
    
    # Tenant Preferences
    preferred_age_min = models.PositiveIntegerField(
        null=True, blank=True,
        validators=[MinValueValidator(18), MaxValueValidator(99)]
    )
    preferred_age_max = models.PositiveIntegerField(
        null=True, blank=True,
        validators=[MinValueValidator(18), MaxValueValidator(99)]
    )
    preferred_occupations = models.JSONField(
        default=list, 
        help_text="List of preferred occupations"
    )
    
    # Deal Breakers
    no_pets = models.BooleanField(default=False)
    no_smoking = models.BooleanField(default=True)
    no_parties = models.BooleanField(default=False)
    references_required = models.BooleanField(default=True)
    
    # Application Requirements
    required_documents = models.JSONField(
        default=list,
        help_text="List of required documents for application"
    )
    application_fee = models.DecimalField(
        max_digits=6, decimal_places=2, default=0,
        help_text="Application fee amount"
    )
    
    # Timeline
    viewing_required = models.BooleanField(default=True)
    group_viewing_preferred = models.BooleanField(default=True)
    decision_timeline_days = models.PositiveIntegerField(
        default=7,
        help_text="Days to make decision after application"
    )
    
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'properties_propertyrequirements'
        verbose_name = 'Property Requirements'
        verbose_name_plural = 'Property Requirements'
    
    def __str__(self):
        return f"Requirements for {self.property.title}"


class PropertyInterest(models.Model):
    """Track user interest in specific properties"""
    
    STATUS_CHOICES = [
        ('interested', 'Interested'),
        ('contacted', 'Contacted Property Owner'),
        ('viewing_scheduled', 'Viewing Scheduled'),
        ('applied', 'Applied'),
        ('withdrawn', 'Withdrawn Interest'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='property_interests')
    property_listing = models.ForeignKey(Property, on_delete=models.CASCADE, related_name='interested_users')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='interested')
    
    # Interest Details
    notes = models.TextField(blank=True, help_text="User's notes about this property")
    budget_confirmed = models.BooleanField(default=False)
    timeline_compatible = models.BooleanField(default=False)
    
    # Group Formation
    open_to_group_formation = models.BooleanField(default=True)
    preferred_group_size = models.PositiveIntegerField(
        null=True, blank=True,
        validators=[MinValueValidator(1), MaxValueValidator(10)]
    )
    
    # Compatibility Scores (calculated)
    budget_compatibility_score = models.FloatField(default=0.0)
    lifestyle_compatibility_score = models.FloatField(default=0.0)
    overall_compatibility_score = models.FloatField(default=0.0)
    
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'properties_propertyinterest'
        unique_together = ['user', 'property_listing']
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['property_listing', 'status']),
            models.Index(fields=['user', 'status']),
        ]
    
    def __str__(self):
        return f"{self.user.get_short_name()} interested in {self.property_listing.title}"
    
    @property
    def can_form_group(self):
        """Check if user can participate in group formation for this property"""
        return (self.open_to_group_formation and 
                self.status in ['interested', 'contacted'] and 
                self.budget_confirmed)


class PropertyGroup(models.Model):
    """Property-specific groups forming to apply together"""
    
    STATUS_CHOICES = [
        ('forming', 'Forming'),
        ('ready', 'Ready to Apply'),
        ('applied', 'Application Submitted'),
        ('approved', 'Application Approved'),
        ('rejected', 'Application Rejected'),
        ('disbanded', 'Group Disbanded'),
    ]
    
    property_listing = models.ForeignKey(Property, on_delete=models.CASCADE, related_name='groups')
    name = models.CharField(max_length=100, help_text="Group name")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='forming')
    
    # Group Members
    members = models.ManyToManyField(User, through='PropertyGroupMembership', related_name='property_groups')
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='created_property_groups')
    
    # Group Details
    target_size = models.PositiveIntegerField(validators=[MinValueValidator(1), MaxValueValidator(10)])
    current_size = models.PositiveIntegerField(default=1)
    max_size = models.PositiveIntegerField(validators=[MinValueValidator(1), MaxValueValidator(10)])
    
    # Financial Validation
    combined_income_verified = models.BooleanField(default=False)
    budget_meets_requirements = models.BooleanField(default=False)
    
    # Timeline Coordination
    agreed_move_in_date = models.DateField(null=True, blank=True)
    viewing_scheduled = models.DateTimeField(null=True, blank=True)
    application_deadline = models.DateField(null=True, blank=True)
    
    # Group Preferences
    group_bio = models.TextField(blank=True, help_text="Group description for property owner")
    shared_interests = models.JSONField(default=list)
    group_compatibility_score = models.FloatField(default=0.0)
    
    # Application Management
    application_submitted_at = models.DateTimeField(null=True, blank=True)
    application_documents_complete = models.BooleanField(default=False)
    property_owner_response = models.TextField(blank=True)
    
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'properties_propertygroup'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['property_listing', 'status']),
            models.Index(fields=['status', 'current_size']),
        ]
    
    def __str__(self):
        return f"{self.name} ({self.current_size}/{self.target_size}) - {self.property_listing.title}"
    
    @property
    def is_full(self):
        return self.current_size >= self.target_size
    
    @property
    def needs_members(self):
        return self.target_size - self.current_size
    
    @property
    def is_ready_to_apply(self):
        return (self.current_size >= self.target_size and 
                self.budget_meets_requirements and 
                self.application_documents_complete)
    
    @property
    def combined_budget_range(self):
        """Calculate combined budget range of all group members"""
        total_min = 0
        total_max = 0
        for membership in self.memberships.all():
            if hasattr(membership.user, 'profile'):
                profile = membership.user.profile
                if profile.min_budget:
                    total_min += float(profile.min_budget)
                if profile.max_budget:
                    total_max += float(profile.max_budget)
        return total_min, total_max


class PropertyGroupMembership(models.Model):
    """Through model for PropertyGroup membership with additional details"""
    
    ROLE_CHOICES = [
        ('creator', 'Group Creator'),
        ('member', 'Member'),
        ('pending', 'Pending Invitation'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    group = models.ForeignKey(PropertyGroup, on_delete=models.CASCADE, related_name='memberships')
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='member')
    
    # Membership Details
    joined_at = models.DateTimeField(default=timezone.now)
    documents_uploaded = models.BooleanField(default=False)
    income_verified = models.BooleanField(default=False)
    ready_to_apply = models.BooleanField(default=False)
    
    # Preferences for this group
    notes = models.TextField(blank=True)
    can_be_primary_contact = models.BooleanField(default=False)
    
    class Meta:
        db_table = 'properties_propertygroupmembership'
        unique_together = ['user', 'group']
        ordering = ['joined_at']
    
    def __str__(self):
        return f"{self.user.get_short_name()} in {self.group.name}"


class PropertyGroupInvitation(models.Model):
    """Invitations to join property-specific groups"""
    
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('accepted', 'Accepted'),
        ('declined', 'Declined'),
        ('expired', 'Expired'),
    ]
    
    group = models.ForeignKey(PropertyGroup, on_delete=models.CASCADE, related_name='invitations')
    invited_user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='property_group_invitations')
    invited_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sent_property_group_invitations')
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    message = models.TextField(blank=True, help_text="Personal message with invitation")
    
    created_at = models.DateTimeField(default=timezone.now)
    responded_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField()
    
    class Meta:
        db_table = 'properties_propertygroupinvitation'
        unique_together = ['group', 'invited_user']
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Invitation to {self.invited_user.get_short_name()} for {self.group.name}"
    
    @property
    def is_expired(self):
        return timezone.now() > self.expires_at
    
    @property
    def is_pending(self):
        return self.status == 'pending' and not self.is_expired