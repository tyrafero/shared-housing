from django.urls import path
from . import views

app_name = 'applications'

urlpatterns = [
    # Placeholder routes for future application management system
    path('', views.applications_list, name='list'),
    path('my/', views.my_applications, name='my_applications'),
    path('<int:pk>/', views.application_detail, name='detail'),
]
