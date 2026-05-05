from django.urls import path
from . import views, api_views

urlpatterns = [
    path('', views.bucket_list, name='bucket_list'),
    path('create/', views.bucket_create, name='bucket_create'),
    path('<uuid:pk>/', views.bucket_detail, name='bucket_detail'),
    path('<uuid:pk>/delete/', views.bucket_delete, name='bucket_delete'),
    path('<uuid:pk>/upload/', views.bucket_file_upload, name='bucket_file_upload'),
    path('<uuid:pk>/folder/create/', views.bucket_folder_create, name='bucket_folder_create'),
    path('<uuid:pk>/files/<uuid:file_id>/download/', views.bucket_file_download, name='bucket_file_download'),
    path('<uuid:pk>/files/<uuid:file_id>/download-url/', views.bucket_file_download_url, name='bucket_file_download_url'),
    path('<uuid:pk>/files/<uuid:file_id>/preview/', views.bucket_file_preview, name='bucket_file_preview'),
    path('<uuid:pk>/files/<uuid:file_id>/edit/', views.bucket_file_edit, name='bucket_file_edit'),
    path('<uuid:pk>/files/<uuid:file_id>/delete/', views.bucket_file_delete, name='bucket_file_delete'),
    path('<uuid:pk>/files/<uuid:file_id>/rename/', views.bucket_file_rename, name='bucket_file_rename'),
    path('<uuid:pk>/folder/rename/', views.bucket_folder_rename, name='bucket_folder_rename'),
    path('<uuid:pk>/folder/download/', views.bucket_folder_download, name='bucket_folder_download'),
    # API Keys
    path('api-keys/', views.api_key_list, name='api_key_list'),
    path('api-keys/create/', views.api_key_create, name='api_key_create'),
    path('api-keys/<uuid:pk>/revoke/', views.api_key_revoke, name='api_key_revoke'),
    path('api-keys/<uuid:pk>/delete/', views.api_key_delete, name='api_key_delete'),
    # ── REST API (X-Api-Key) ──
    path('api/buckets/', api_views.api_bucket_list, name='api_bucket_list'),
    path('api/buckets/create/', api_views.api_bucket_create, name='api_bucket_create'),
    path('api/buckets/<uuid:pk>/', api_views.api_bucket_delete, name='api_bucket_delete'),
    path('api/buckets/<uuid:pk>/files/', api_views.api_bucket_file_list, name='api_bucket_file_list'),
    path('api/buckets/<uuid:pk>/upload/', api_views.api_bucket_file_upload, name='api_bucket_file_upload'),
    path('api/buckets/<uuid:pk>/files/<uuid:file_id>/', api_views.api_bucket_file_delete, name='api_bucket_file_delete_api'),
    path('api/buckets/<uuid:pk>/folder/create/', api_views.api_bucket_folder_create, name='api_bucket_folder_create'),
    path('api/buckets/<uuid:pk>/folder/', api_views.api_bucket_folder_delete, name='api_bucket_folder_delete'),
    # Legacy
    path('api/<uuid:pk>/files/<uuid:file_id>/download/', views.api_bucket_file_download, name='api_bucket_file_download'),
    # Path-based download
    path('<uuid:pk>/dl/<path:file_path>', views.bucket_file_download_path, name='bucket_file_download_path'),
    # API docs
    path('api-keys/docs/', views.api_docs, name='api_docs'),
]
