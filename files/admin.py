from django.contrib import admin
from .models import Folder, File


@admin.register(Folder)
class FolderAdmin(admin.ModelAdmin):
    list_display = ['name', 'owner', 'parent', 'is_deleted', 'created_at']
    list_filter = ['is_deleted', 'owner']
    search_fields = ['name']


@admin.register(File)
class FileAdmin(admin.ModelAdmin):
    list_display = ['name', 'size', 'mime_type', 'owner', 'folder', 'is_deleted', 'created_at']
    list_filter = ['is_deleted', 'mime_type', 'owner']
    search_fields = ['name']
