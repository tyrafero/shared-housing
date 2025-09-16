from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth import get_user_model
from django.http import JsonResponse, Http404
from django.views.decorators.http import require_http_methods, require_POST
from django.contrib import messages
from django.db.models import Q, Count, Avg
from django.core.paginator import Paginator
from django.utils import timezone
from decimal import Decimal
import json

from .models import Property, PropertyImage, RoomListing, PropertySavedSearch
from .forms import PropertyCreationForm
from messaging.services import MessagingService

User = get_user_model()


@login_required
def property_list(request):
    """List properties with search and filtering"""

    # Base queryset
    properties = Property.objects.filter(
        is_active=True,
        rooms_available__gt=0
    ).select_related('added_by').prefetch_related('images')

    # Search functionality
    search_query = request.GET.get('search', '').strip()
    if search_query:
        properties = properties.filter(
            Q(title__icontains=search_query) |
            Q(description__icontains=search_query) |
            Q(address__icontains=search_query) |
            Q(suburb__icontains=search_query)
        )

    # Location filtering
    location = request.GET.get('location', '').strip()
    if location:
        properties = properties.filter(
            Q(suburb__icontains=location) |
            Q(state__icontains=location)
        )

    # Price filtering
    min_price = request.GET.get('min_price')
    if min_price:
        try:
            properties = properties.filter(weekly_rent__gte=Decimal(min_price))
        except (ValueError, TypeError):
            pass

    max_price = request.GET.get('max_price')
    if max_price:
        try:
            properties = properties.filter(weekly_rent__lte=Decimal(max_price))
        except (ValueError, TypeError):
            pass

    # Property type filtering
    property_type = request.GET.get('property_type')
    if property_type:
        properties = properties.filter(property_type=property_type)

    # Bedroom filtering
    bedrooms = request.GET.get('bedrooms')
    if bedrooms:
        try:
            properties = properties.filter(bedrooms=int(bedrooms))
        except (ValueError, TypeError):
            pass

    # Bathroom filtering
    bathrooms = request.GET.get('bathrooms')
    if bathrooms:
        try:
            properties = properties.filter(bathrooms=int(bathrooms))
        except (ValueError, TypeError):
            pass

    # Features filtering
    features = request.GET.getlist('features')
    if features:
        for feature in features:
            if feature in ['pet_friendly', 'furnished', 'parking_available',
                          'air_conditioning', 'heating', 'internet_included']:
                properties = properties.filter(**{feature: True})

    # Sorting
    sort_by = request.GET.get('sort', '-created_at')
    if sort_by in ['weekly_rent', '-weekly_rent', 'created_at', '-created_at', 'bedrooms', '-bedrooms']:
        properties = properties.order_by(sort_by)
    else:
        properties = properties.order_by('-created_at')

    # Pagination
    paginator = Paginator(properties, 12)  # 12 properties per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    # Get user's saved searches
    saved_searches = []
    if hasattr(request.user, 'profile'):
        saved_searches = PropertySavedSearch.objects.filter(
            user=request.user
        ).order_by('-created_at')[:5]

    context = {
        'page_obj': page_obj,
        'search_query': search_query,
        'location': location,
        'min_price': min_price,
        'max_price': max_price,
        'property_type': property_type,
        'bedrooms': bedrooms,
        'bathrooms': bathrooms,
        'features': features,
        'sort_by': sort_by,
        'saved_searches': saved_searches,
        'property_types': Property._meta.get_field('property_type').choices,
        'total_count': paginator.count,
    }

    return render(request, 'properties/property_list.html', context)


@login_required
def property_detail(request, pk):
    """View property details"""
    property_obj = get_object_or_404(
        Property.objects.select_related('added_by').prefetch_related(
            'images', 'room_listings', 'amenities'
        ),
        pk=pk,
        is_active=True
    )

    # Get available rooms
    available_rooms = property_obj.room_listings.filter(is_available=True)

    # Check if user has inquired about this property
    has_inquired = False
    if hasattr(request.user, 'sent_messages'):
        from messaging.models import Conversation
        has_inquired = Conversation.objects.filter(
            conversation_type='property_inquiry',
            property_listing=property_obj,
            participants=request.user
        ).exists()

    # Get similar properties
    similar_properties = Property.objects.filter(
        suburb=property_obj.suburb,
        property_type=property_obj.property_type,
        is_active=True,
        rooms_available__gt=0
    ).exclude(pk=property_obj.pk)[:4]

    context = {
        'property': property_obj,
        'available_rooms': available_rooms,
        'has_inquired': has_inquired,
        'similar_properties': similar_properties,
    }

    return render(request, 'properties/property_detail.html', context)


@login_required
@require_POST
def save_property(request, pk):
    """Save/unsave a property"""
    property_obj = get_object_or_404(Property, pk=pk, is_active=True)

    # Check if property is already saved
    if hasattr(request.user, 'saved_properties'):
        if property_obj in request.user.saved_properties.all():
            request.user.saved_properties.remove(property_obj)
            saved = False
            message = 'Property removed from saved list'
        else:
            request.user.saved_properties.add(property_obj)
            saved = True
            message = 'Property saved successfully'
    else:
        # Handle case where user doesn't have saved_properties relation
        saved = False
        message = 'Unable to save property'

    if request.headers.get('Content-Type') == 'application/json':
        return JsonResponse({
            'saved': saved,
            'message': message
        })
    else:
        messages.success(request, message)
        return redirect('properties:detail', pk=pk)


@login_required
def saved_properties(request):
    """View user's saved properties"""
    if not hasattr(request.user, 'saved_properties'):
        saved_properties_list = []
    else:
        saved_properties_list = request.user.saved_properties.filter(
            is_active=True
        ).order_by('-created_at')

    paginator = Paginator(saved_properties_list, 12)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'page_obj': page_obj,
        'total_count': len(saved_properties_list) if hasattr(request.user, 'saved_properties') else 0,
    }

    return render(request, 'properties/saved_properties.html', context)


@login_required
@require_POST
def create_inquiry(request, pk):
    """Create inquiry conversation for a property"""
    property_obj = get_object_or_404(Property, pk=pk, is_active=True)

    message_content = request.POST.get('message', '').strip()
    if not message_content:
        messages.error(request, 'Please provide an inquiry message.')
        return redirect('properties:detail', pk=pk)

    if len(message_content) < 20:
        messages.error(request, 'Inquiry message must be at least 20 characters long.')
        return redirect('properties:detail', pk=pk)

    try:
        messaging_service = MessagingService()
        conversation = messaging_service.create_property_inquiry(
            property_listing=property_obj,
            inquirer=request.user,
            message_content=message_content
        )

        messages.success(request, 'Your inquiry has been sent to the property owner!')
        return redirect('messaging:conversation_detail', conversation_id=conversation.id)

    except ValueError as e:
        messages.error(request, str(e))
        return redirect('properties:detail', pk=pk)


@login_required
def save_search(request):
    """Save current search parameters"""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            search_name = data.get('name', '').strip()

            if not search_name:
                return JsonResponse({'error': 'Search name is required'}, status=400)

            # Create saved search
            saved_search = PropertySavedSearch.objects.create(
                user=request.user,
                name=search_name,
                search_params=data.get('params', {}),
                location=data.get('params', {}).get('location', ''),
                min_price=data.get('params', {}).get('min_price'),
                max_price=data.get('params', {}).get('max_price'),
                property_type=data.get('params', {}).get('property_type', ''),
                min_bedrooms=data.get('params', {}).get('bedrooms'),
                min_bathrooms=data.get('params', {}).get('bathrooms')
            )

            return JsonResponse({
                'success': True,
                'message': 'Search saved successfully',
                'search_id': saved_search.id
            })

        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON data'}, status=400)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)

    # GET request - show saved searches
    saved_searches = PropertySavedSearch.objects.filter(
        user=request.user
    ).order_by('-created_at')

    return render(request, 'properties/saved_searches.html', {
        'saved_searches': saved_searches
    })


@login_required
@require_POST
def delete_saved_search(request, search_id):
    """Delete a saved search"""
    saved_search = get_object_or_404(
        PropertySavedSearch,
        id=search_id,
        user=request.user
    )

    saved_search.delete()
    messages.success(request, 'Saved search deleted successfully.')

    return redirect('properties:saved_searches')


@login_required
def search_suggestions(request):
    """Get search suggestions for autocomplete"""
    query = request.GET.get('q', '').strip()

    if len(query) < 2:
        return JsonResponse({'suggestions': []})

    # Get suburb suggestions
    suburbs = Property.objects.filter(
        suburb__icontains=query,
        is_active=True
    ).values_list('suburb', flat=True).distinct()[:5]

    # Get address suggestions
    addresses = Property.objects.filter(
        address__icontains=query,
        is_active=True
    ).values_list('address', flat=True).distinct()[:3]

    suggestions = list(set(list(suburbs) + list(addresses)))[:8]

    return JsonResponse({'suggestions': suggestions})


def property_map(request):
    """Show properties on a map using OpenStreetMap"""
    # Get filtered properties based on search params
    properties = Property.objects.filter(
        is_active=True,
        rooms_available__gt=0,
        latitude__isnull=False,
        longitude__isnull=False
    ).prefetch_related('images')  # Prefetch images for efficiency

    # Apply same filters as property_list
    search_query = request.GET.get('search', '').strip()
    if search_query:
        properties = properties.filter(
            Q(title__icontains=search_query) |
            Q(suburb__icontains=search_query)
        )

    location = request.GET.get('location', '').strip()
    if location:
        properties = properties.filter(
            Q(suburb__icontains=location) |
            Q(state__icontains=location)
        )

    min_price = request.GET.get('min_price')
    if min_price:
        try:
            properties = properties.filter(rent_per_week__gte=Decimal(min_price))
        except (ValueError, TypeError):
            pass

    max_price = request.GET.get('max_price')
    if max_price:
        try:
            properties = properties.filter(rent_per_week__lte=Decimal(max_price))
        except (ValueError, TypeError):
            pass

    property_type = request.GET.get('property_type', '').strip()
    if property_type:
        properties = properties.filter(property_type=property_type)

    bedrooms = request.GET.get('bedrooms', '').strip()
    if bedrooms:
        try:
            properties = properties.filter(bedrooms__gte=int(bedrooms))
        except (ValueError, TypeError):
            pass

    # Limit to first 100 properties for performance
    properties = properties[:100]

    context = {
        'properties': properties,
        'search_query': search_query,
        'location': location,
        'min_price': min_price,
        'max_price': max_price,
        'property_type': property_type,
        'bedrooms': bedrooms,
        'property_types': Property._meta.get_field('property_type').choices,
    }

    return render(request, 'properties/property_map.html', context)


@login_required
def room_detail(request, property_id, room_id):
    """View individual room details"""
    property_obj = get_object_or_404(Property, pk=property_id, is_active=True)
    room = get_object_or_404(
        RoomListing,
        pk=room_id,
        property_listing=property_obj,
        is_available=True
    )

    context = {
        'property': property_obj,
        'room': room,
    }

    return render(request, 'properties/room_detail.html', context)


# API endpoints for AJAX calls

@login_required
def api_property_stats(request):
    """Get property statistics for dashboard"""
    total_properties = Property.objects.filter(is_active=True).count()
    available_properties = Property.objects.filter(
        is_active=True,
        rooms_available__gt=0
    ).count()

    # Average rent by property type
    avg_rents = Property.objects.filter(
        is_active=True,
        rooms_available__gt=0
    ).values('property_type').annotate(
        avg_rent=Avg('weekly_rent'),
        count=Count('id')
    ).order_by('property_type')

    return JsonResponse({
        'total_properties': total_properties,
        'available_properties': available_properties,
        'avg_rents': list(avg_rents)
    })


@login_required
def api_property_search(request):
    """AJAX endpoint for property search"""
    query = request.GET.get('q', '').strip()
    limit = int(request.GET.get('limit', 10))

    if len(query) < 2:
        return JsonResponse({'properties': []})

    properties = Property.objects.filter(
        Q(title__icontains=query) |
        Q(address__icontains=query) |
        Q(suburb__icontains=query),
        is_active=True,
        rooms_available__gt=0
    ).select_related('added_by')[:limit]

    properties_data = []
    for prop in properties:
        properties_data.append({
            'id': prop.id,
            'title': prop.title,
            'address': prop.address,
            'suburb': prop.suburb,
            'weekly_rent': str(prop.weekly_rent),
            'bedrooms': prop.bedrooms,
            'bathrooms': prop.bathrooms,
            'property_type': prop.get_property_type_display(),
            'url': f'/properties/{prop.id}/',
            'image_url': prop.featured_image.url if prop.featured_image else None,
        })

    return JsonResponse({'properties': properties_data})


# Management views (for property owners/agents - future implementation)

@login_required
def my_properties(request):
    """View user's own properties (placeholder)"""
    messages.info(request, 'Property management coming soon!')
    return redirect('properties:list')


@login_required
def add_property(request):
    """Add new property listing for landlords"""

    # Check if user is allowed to add properties
    if not request.user.can_list_properties():
        messages.error(request, 'You do not have permission to list properties.')
        return redirect('properties:list')

    if request.method == 'POST':
        form = PropertyCreationForm(request.POST)
        if form.is_valid():
            property = form.save(commit=False)
            property.added_by = request.user
            property.contact_person = request.user.get_full_name()
            property.contact_email = request.user.email
            property.contact_phone = getattr(request.user, 'phone_number', '')
            property.save()

            # Handle image URLs
            from .models import PropertyImage
            image_urls = [
                form.cleaned_data.get('image_url_1'),
                form.cleaned_data.get('image_url_2'),
                form.cleaned_data.get('image_url_3'),
            ]

            for i, url in enumerate(image_urls):
                if url:
                    PropertyImage.objects.create(
                        property_listing=property,
                        image_url=url,
                        order=i,
                        is_primary=(i == 0)  # First image is primary
                    )

            messages.success(request, 'Property listing created successfully!')
            return redirect('properties:detail', pk=property.pk)
    else:
        form = PropertyCreationForm()

    context = {
        'form': form,
        'title': 'Add New Property'
    }
    return render(request, 'properties/add_property.html', context)


@login_required
def edit_property(request, pk):
    """Edit existing property listing"""
    property_obj = get_object_or_404(Property, pk=pk, is_active=True)

    # Check if user owns this property or is admin
    if property_obj.added_by != request.user and not request.user.is_admin:
        messages.error(request, 'You do not have permission to edit this property.')
        return redirect('properties:detail', pk=pk)

    if request.method == 'POST':
        form = PropertyCreationForm(request.POST, instance=property_obj)
        if form.is_valid():
            property_obj = form.save()

            # Handle image URLs - first delete existing images from URLs
            from .models import PropertyImage
            existing_images = PropertyImage.objects.filter(property_listing=property_obj, image_url__isnull=False)
            existing_images.delete()

            # Add new image URLs
            image_urls = [
                form.cleaned_data.get('image_url_1'),
                form.cleaned_data.get('image_url_2'),
                form.cleaned_data.get('image_url_3'),
            ]

            for i, url in enumerate(image_urls):
                if url:
                    PropertyImage.objects.create(
                        property_listing=property_obj,
                        image_url=url,
                        order=i,
                        is_primary=(i == 0 and not PropertyImage.objects.filter(property_listing=property_obj, is_primary=True).exists())
                    )

            messages.success(request, 'Property updated successfully!')
            return redirect('properties:detail', pk=property_obj.pk)
    else:
        # Populate form with existing image URLs
        form = PropertyCreationForm(instance=property_obj)
        existing_images = property_obj.images.filter(image_url__isnull=False).order_by('order')
        if existing_images.exists():
            form.fields['image_url_1'].initial = existing_images[0].image_url if existing_images.count() > 0 else ''
            form.fields['image_url_2'].initial = existing_images[1].image_url if existing_images.count() > 1 else ''
            form.fields['image_url_3'].initial = existing_images[2].image_url if existing_images.count() > 2 else ''

    context = {
        'form': form,
        'property': property_obj,
        'title': f'Edit {property_obj.title}'
    }
    return render(request, 'properties/edit_property.html', context)


@login_required
def property_analytics(request, pk):
    """Basic analytics view for property owners"""
    property_obj = get_object_or_404(Property, pk=pk, is_active=True)

    # Check if user owns this property or is admin
    if property_obj.added_by != request.user and not request.user.is_admin:
        messages.error(request, 'You do not have permission to view analytics for this property.')
        return redirect('properties:detail', pk=pk)

    # Basic analytics data
    total_views = getattr(property_obj, 'view_count', 0)  # Placeholder - would need to implement view tracking

    # Get inquiry count (if messaging system exists)
    try:
        from messaging.models import Conversation
        total_inquiries = Conversation.objects.filter(
            conversation_type='property_inquiry',
            property_listing=property_obj
        ).count()
    except:
        total_inquiries = 0

    # Days since listing
    from django.utils import timezone
    days_listed = (timezone.now().date() - property_obj.date_listed).days if hasattr(property_obj, 'date_listed') else 0

    # Calculate some basic metrics
    avg_inquiries_per_day = total_inquiries / max(days_listed, 1) if days_listed > 0 else 0

    context = {
        'property': property_obj,
        'total_views': total_views,
        'total_inquiries': total_inquiries,
        'days_listed': days_listed,
        'avg_inquiries_per_day': round(avg_inquiries_per_day, 2),
        'title': f'Analytics - {property_obj.title}'
    }
    return render(request, 'properties/property_analytics.html', context)
