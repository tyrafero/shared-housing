from django.urls import path
from . import views

app_name = 'properties'

urlpatterns = [
    # Property listing and search
    path('', views.property_list, name='list'),
    path('<int:pk>/', views.property_detail, name='detail'),
    path('map/', views.property_map, name='map'),

    # Property interactions
    path('<int:pk>/save/', views.save_property, name='save'),
    path('<int:pk>/inquiry/', views.create_inquiry, name='inquiry'),
    path('saved/', views.saved_properties, name='saved'),

    # Individual room details
    path('<int:property_id>/room/<int:room_id>/', views.room_detail, name='room_detail'),

    # Search functionality
    path('search/save/', views.save_search, name='save_search'),
    path('search/saved/', views.save_search, name='saved_searches'),
    path('search/saved/<int:search_id>/delete/', views.delete_saved_search, name='delete_saved_search'),
    path('search/suggestions/', views.search_suggestions, name='search_suggestions'),

    # API endpoints
    path('api/stats/', views.api_property_stats, name='api_stats'),
    path('api/search/', views.api_property_search, name='api_search'),

    # Property management (future features)
    path('my-properties/', views.my_properties, name='my_properties'),
    path('add/', views.add_property, name='add'),
    path('<int:pk>/edit/', views.edit_property, name='edit'),
]
