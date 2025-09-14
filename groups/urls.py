from django.urls import path
from . import views

app_name = 'groups'

urlpatterns = [
    # Group listing and discovery
    path('', views.group_list, name='group_list'),
    path('my-groups/', views.my_groups, name='my_groups'),
    path('create/', views.create_group, name='create_group'),
    path('join/<uuid:group_id>/', views.join_group_request, name='join_group_request'),

    # Group details and management
    path('<uuid:group_id>/', views.group_detail, name='group_detail'),
    path('<uuid:group_id>/edit/', views.edit_group, name='edit_group'),
    path('<uuid:group_id>/leave/', views.leave_group, name='leave_group'),

    # Member management
    path('<uuid:group_id>/members/', views.manage_members, name='manage_members'),
    path('<uuid:group_id>/invite/', views.invite_members, name='invite_members'),
    path('<uuid:group_id>/members/<int:user_id>/remove/', views.remove_member, name='remove_member'),
    path('<uuid:group_id>/members/<int:user_id>/promote/', views.promote_member, name='promote_member'),

    # Membership requests and invitations
    path('<uuid:group_id>/requests/', views.manage_membership_requests, name='manage_membership_requests'),
    path('<uuid:group_id>/approve/<int:user_id>/', views.approve_member, name='approve_member'),
    path('<uuid:group_id>/reject/<int:user_id>/', views.reject_member, name='reject_member'),

    # Invitations
    path('invitations/', views.my_invitations, name='my_invitations'),
    path('invitation/<uuid:invitation_id>/accept/', views.accept_invitation, name='accept_invitation'),
    path('invitation/<uuid:invitation_id>/decline/', views.decline_invitation, name='decline_invitation'),

    # Property applications
    path('<uuid:group_id>/applications/', views.group_applications, name='group_applications'),
    path('<uuid:group_id>/apply/<int:property_id>/', views.apply_for_property, name='apply_for_property'),
    path('application/<uuid:application_id>/', views.application_detail, name='application_detail'),
    path('application/<uuid:application_id>/vote/', views.vote_on_application, name='vote_on_application'),
    path('application/<uuid:application_id>/submit/', views.submit_application, name='submit_application'),

    # Group activities and messaging
    path('<uuid:group_id>/activities/', views.group_activities, name='group_activities'),
    path('<uuid:group_id>/chat/', views.group_chat, name='group_chat'),

    # AJAX endpoints
    path('api/search/', views.search_groups, name='search_groups'),
    path('api/check-eligibility/<uuid:group_id>/', views.check_join_eligibility, name='check_join_eligibility'),
]
