from django.urls import path
from . import views

app_name = 'matching'

urlpatterns = [
    # Main matching views
    path('', views.matching_dashboard, name='dashboard'),
    path('find-roommates/', views.find_roommates, name='find_roommates'),
    path('my-matches/', views.my_matches, name='my_matches'),

    # Compatibility and recommendations
    path('compatibility/<int:user_id>/', views.compatibility_detail, name='compatibility_detail'),
    path('recommendations/', views.get_user_recommendations, name='recommendations'),

    # User interaction
    path('connect/<int:user_id>/', views.connect_with_user, name='connect'),
    path('dismiss/<int:recommendation_id>/', views.dismiss_recommendation, name='dismiss'),

    # API endpoints
    path('api/calculate-compatibility/<int:user_id>/', views.api_calculate_compatibility, name='api_compatibility'),
    path('api/user-search/', views.api_user_search, name='api_user_search'),
]