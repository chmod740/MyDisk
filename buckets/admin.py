from django.contrib import admin
from .models import Bucket, BucketFile, ApiKey


@admin.register(Bucket)
class BucketAdmin(admin.ModelAdmin):
    list_display = ['name', 'owner', 'is_public', 'file_count', 'created_at']
    list_filter = ['is_public', 'owner']
    search_fields = ['name']


@admin.register(BucketFile)
class BucketFileAdmin(admin.ModelAdmin):
    list_display = ['name', 'bucket', 'size', 'mime_type', 'created_at']
    list_filter = ['bucket__owner']
    search_fields = ['name']


@admin.register(ApiKey)
class ApiKeyAdmin(admin.ModelAdmin):
    list_display = ['name', 'user', 'prefix', 'is_active', 'created_at', 'last_accessed_at']
    list_filter = ['is_active', 'user']
    search_fields = ['name', 'prefix']
    readonly_fields = ['key_hash', 'prefix']
