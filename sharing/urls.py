from django.urls import path
from . import views

urlpatterns = [
    path('create/', views.share_create, name='share_create'),
    path('manage/', views.share_manage, name='share_manage'),
    path('<uuid:share_id>/delete/', views.share_delete, name='share_delete'),
    path('<uuid:share_id>/', views.share_access, name='share_access'),
]
