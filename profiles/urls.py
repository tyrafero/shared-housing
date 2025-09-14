from django.urls import path
from . import views

app_name = 'profiles'

urlpatterns = [
    # Profile Setup (Multi-step)
    path('setup/', views.profile_setup, name='setup'),
    path('setup/<str:step>/', views.profile_setup_step, name='setup_step'),
    path('setup/<str:step>/skip/', views.profile_skip_step, name='skip_step'),

    # Profile Viewing and Editing
    path('', views.profile_view, name='profile_view'),  # Own profile
    path('<int:user_id>/', views.profile_view, name='profile_view_other'),  # Other's profile
    path('edit/', views.profile_edit, name='profile_edit'),

    # API Endpoints
    path('api/progress/', views.profile_progress_api, name='profile_progress_api'),
]