from django.urls import path
from . import admin_views

urlpatterns = [
    path('settings/', admin_views.admin_settings, name='admin_settings'),
    path('users/', admin_views.admin_user_list, name='admin_user_list'),
    path('users/create/', admin_views.admin_user_create, name='admin_user_create'),
    path('users/<int:pk>/update/', admin_views.admin_user_update, name='admin_user_update'),
    path('groups/', admin_views.admin_group_list, name='admin_group_list'),
    path('groups/create/', admin_views.admin_group_create, name='admin_group_create'),
    path('groups/<uuid:pk>/edit/', admin_views.admin_group_edit, name='admin_group_edit'),
    path('groups/<uuid:pk>/delete/', admin_views.admin_group_delete, name='admin_group_delete'),
]
