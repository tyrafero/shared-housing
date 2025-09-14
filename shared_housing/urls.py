from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    # Admin
    path('admin/', admin.site.urls),

    # Authentication
    path('accounts/', include('accounts.urls')),

    # Django Allauth (backup authentication system)
    path('auth/', include('allauth.urls')),

    # Core app (dashboard, home)
    path('', include('core.urls')),

    # Profile management
    path('profile/', include('profiles.urls')),

    # Property listings
    path('properties/', include('properties.urls')),

    # Matching system
    path('matching/', include('roommate_matching.urls')),

    # Messaging
    path('messages/', include('messaging.urls')),

    # Groups
    path('groups/', include('groups.urls')),

    # Applications
    path('applications/', include('applications.urls')),
]

# Serve media files in development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)