from django.db import models
from django.contrib.auth import get_user_model
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone
from django.urls import reverse
from decimal import Decimal

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


class PropertyImage(models.Model):
    """Property images for listings"""

    property_listing = models.ForeignKey(Property, on_delete=models.CASCADE, related_name='images')
    image = models.ImageField(upload_to='properties/images/')
    caption = models.CharField(max_length=200, blank=True)
    is_primary = models.BooleanField(default=False)
    order = models.PositiveIntegerField(default=0)
    uploaded_at = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = 'properties_propertyimage'
        ordering = ['order', 'uploaded_at']

    def __str__(self):
        return f"Image for {self.property_listing.title}"


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