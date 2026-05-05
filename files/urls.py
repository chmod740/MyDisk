from django.urls import path
from . import views, api_views

urlpatterns = [
    # ── REST API (X-Api-Key) ──
    path('api/list/', api_views.api_file_list, name='api_file_list'),
    path('api/upload/', api_views.api_file_upload, name='api_file_upload'),
    path('api/<uuid:file_id>/download/', api_views.api_file_download, name='api_file_download'),
    path('api/<uuid:file_id>/delete/', api_views.api_file_delete, name='api_file_delete'),
    path('api/folder/create/', api_views.api_folder_create, name='api_folder_create'),

    # ── Browser routes ──
    path('', views.file_list, name='file_list'),
    path('upload/', views.file_upload, name='file_upload'),
    path('<uuid:file_id>/download/', views.file_download, name='file_download'),
    path('<uuid:file_id>/preview/', views.file_preview, name='file_preview'),
    path('<uuid:file_id>/edit/', views.file_edit, name='file_edit'),
    path('<uuid:file_id>/rename/', views.file_rename, name='file_rename'),
    path('<uuid:file_id>/delete/', views.file_delete, name='file_delete'),
    path('<uuid:file_id>/move/', views.file_move, name='file_move'),
    path('batch/delete/', views.batch_delete, name='batch_delete'),
    path('batch/move/', views.batch_move, name='batch_move'),
    path('batch/download/', views.batch_download, name='batch_download'),

    path('folder/create/', views.folder_create, name='folder_create'),
    path('folder/<uuid:folder_id>/rename/', views.folder_rename, name='folder_rename'),
    path('folder/<uuid:folder_id>/delete/', views.folder_delete, name='folder_delete'),
    path('folder/<uuid:folder_id>/download/', views.folder_download, name='folder_download'),

    path('trash/', views.trash_list, name='trash'),
    path('trash/folder/<uuid:folder_id>/', views.trash_folder_detail, name='trash_folder_detail'),
    path('trash/<str:item_type>/<uuid:item_id>/restore/', views.trash_restore, name='trash_restore'),
    path('trash/<str:item_type>/<uuid:item_id>/destroy/', views.trash_destroy, name='trash_destroy'),
]
