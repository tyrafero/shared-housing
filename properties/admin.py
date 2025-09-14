from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from .models import (
    Property, PropertyImage, RoomListing, PropertyAmenity,
    PropertyInspection, PropertySavedSearch
)


class PropertyImageInline(admin.TabularInline):
    model = PropertyImage
    extra = 1
    fields = ('image', 'caption', 'is_primary', 'order')


class RoomListingInline(admin.TabularInline):
    model = RoomListing
    extra = 1
    fields = ('room_type', 'rent_per_week', 'available_from', 'is_available', 'furnished')


@admin.register(Property)
class PropertyAdmin(admin.ModelAdmin):
    list_display = (
        'title', 'suburb', 'state', 'property_type', 'bedrooms', 'bathrooms',
        'rent_per_week', 'is_active', 'is_verified', 'view_count', 'created_at'
    )
    list_filter = (
        'property_type', 'state', 'suburb', 'furnished', 'pets_allowed',
        'is_active', 'is_verified', 'bedrooms', 'bathrooms'
    )
    search_fields = ('title', 'description', 'address', 'suburb', 'postcode')
    readonly_fields = ('view_count', 'created_at', 'updated_at', 'external_id')

    fieldsets = (
        ('Basic Information', {
            'fields': ('title', 'description', 'property_type')
        }),
        ('Location', {
            'fields': ('address', 'suburb', 'state', 'postcode', 'latitude', 'longitude')
        }),
        ('Property Details', {
            'fields': ('bedrooms', 'bathrooms', 'car_spaces', 'total_rooms')
        }),
        ('Financial', {
            'fields': ('rent_per_week', 'bond_amount', 'rent_includes', 'additional_costs')
        }),
        ('Availability', {
            'fields': ('available_from', 'available_until', 'min_lease_term', 'max_lease_term')
        }),
        ('Features', {
            'fields': ('furnished', 'pets_allowed', 'smoking_allowed', 'features', 'appliances', 'amenities')
        }),
        ('Shared Housing', {
            'fields': ('rooms_available', 'current_occupants', 'max_occupants'),
            'classes': ('collapse',)
        }),
        ('Transport & Connectivity', {
            'fields': ('public_transport', 'internet_included'),
            'classes': ('collapse',)
        }),
        ('Contact & Management', {
            'fields': ('contact_person', 'contact_email', 'contact_phone', 'agency', 'listing_agent'),
            'classes': ('collapse',)
        }),
        ('External References', {
            'fields': ('external_id', 'source_website', 'external_url'),
            'classes': ('collapse',)
        }),
        ('Status & Metadata', {
            'fields': ('is_active', 'is_verified', 'view_count', 'added_by', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )

    inlines = [PropertyImageInline, RoomListingInline]

    filter_horizontal = ('amenities', 'favorited_by')

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('added_by').prefetch_related('amenities')

    def save_model(self, request, obj, form, change):
        if not change and not obj.added_by:
            obj.added_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(PropertyImage)
class PropertyImageAdmin(admin.ModelAdmin):
    list_display = ('property_listing', 'caption', 'is_primary', 'order', 'uploaded_at')
    list_filter = ('is_primary', 'uploaded_at')
    search_fields = ('property_listing__title', 'caption')
    readonly_fields = ('uploaded_at',)

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('property_listing')


@admin.register(RoomListing)
class RoomListingAdmin(admin.ModelAdmin):
    list_display = (
        'property_listing', 'room_type', 'rent_per_week', 'bond_amount',
        'available_from', 'is_available', 'furnished'
    )
    list_filter = ('room_type', 'is_available', 'furnished', 'has_ensuite', 'includes_utilities')
    search_fields = ('property_listing__title', 'property_listing__address')
    readonly_fields = ('bond_amount', 'weekly_cost_estimate', 'created_at', 'updated_at')

    fieldsets = (
        ('Property', {
            'fields': ('property_listing',)
        }),
        ('Room Details', {
            'fields': ('room_type', 'size_sqm', 'has_ensuite', 'has_balcony', 'has_built_in_wardrobe')
        }),
        ('Pricing', {
            'fields': ('rent_per_week', 'bond_weeks', 'bond_amount', 'weekly_cost_estimate')
        }),
        ('Availability', {
            'fields': ('available_from', 'is_available')
        }),
        ('Features', {
            'fields': ('furnished', 'includes_utilities', 'features')
        }),
        ('Occupancy', {
            'fields': ('current_occupant',)
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('property_listing', 'current_occupant')


@admin.register(PropertyAmenity)
class PropertyAmenityAdmin(admin.ModelAdmin):
    list_display = ('name', 'category', 'icon')
    list_filter = ('category',)
    search_fields = ('name', 'description')

    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'category', 'icon')
        }),
        ('Description', {
            'fields': ('description',)
        })
    )


@admin.register(PropertyInspection)
class PropertyInspectionAdmin(admin.ModelAdmin):
    list_display = (
        'property_listing', 'datetime', 'duration_minutes', 'attendee_count',
        'spots_remaining', 'contact_person', 'is_active'
    )
    list_filter = ('is_active', 'datetime')
    search_fields = ('property_listing__title', 'contact_person')
    readonly_fields = ('attendee_count', 'spots_remaining', 'is_upcoming', 'created_at')

    fieldsets = (
        ('Property & Schedule', {
            'fields': ('property_listing', 'datetime', 'duration_minutes', 'is_active')
        }),
        ('Capacity', {
            'fields': ('max_attendees', 'attendee_count', 'spots_remaining')
        }),
        ('Contact', {
            'fields': ('contact_person', 'contact_phone', 'notes')
        }),
        ('Attendees', {
            'fields': ('registered_users',)
        }),
        ('Status', {
            'fields': ('is_upcoming', 'created_at'),
            'classes': ('collapse',)
        })
    )

    filter_horizontal = ('registered_users',)

    def attendee_count(self, obj):
        return obj.registered_users.count()
    attendee_count.short_description = 'Attendees'

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('property_listing').prefetch_related('registered_users')


@admin.register(PropertySavedSearch)
class PropertySavedSearchAdmin(admin.ModelAdmin):
    list_display = (
        'user', 'name', 'rent_range', 'bedroom_range', 'email_notifications',
        'notification_frequency', 'is_active', 'created_at'
    )
    list_filter = ('is_active', 'email_notifications', 'notification_frequency', 'furnished')
    search_fields = ('user__email', 'user__first_name', 'user__last_name', 'name')
    readonly_fields = ('created_at', 'last_notification_sent')

    fieldsets = (
        ('User & Search Name', {
            'fields': ('user', 'name')
        }),
        ('Location & Property Type', {
            'fields': ('suburbs', 'property_types')
        }),
        ('Budget & Size', {
            'fields': ('min_rent', 'max_rent', 'min_bedrooms', 'max_bedrooms')
        }),
        ('Preferences', {
            'fields': ('pets_allowed', 'furnished', 'available_from')
        }),
        ('Notifications', {
            'fields': ('email_notifications', 'notification_frequency', 'last_notification_sent')
        }),
        ('Status', {
            'fields': ('is_active', 'created_at')
        })
    )

    def rent_range(self, obj):
        if obj.min_rent and obj.max_rent:
            return f"${obj.min_rent} - ${obj.max_rent}"
        elif obj.min_rent:
            return f"${obj.min_rent}+"
        elif obj.max_rent:
            return f"Up to ${obj.max_rent}"
        return "Any"
    rent_range.short_description = 'Rent Range'

    def bedroom_range(self, obj):
        if obj.min_bedrooms and obj.max_bedrooms:
            return f"{obj.min_bedrooms} - {obj.max_bedrooms} bed"
        elif obj.min_bedrooms:
            return f"{obj.min_bedrooms}+ bed"
        elif obj.max_bedrooms:
            return f"Up to {obj.max_bedrooms} bed"
        return "Any"
    bedroom_range.short_description = 'Bedrooms'

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user')