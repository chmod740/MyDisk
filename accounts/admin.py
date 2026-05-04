from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import User


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    list_display = ['username', 'email', 'storage_used', 'storage_quota', 'is_staff', 'date_joined']
    fieldsets = UserAdmin.fieldsets + (
        ('存储信息', {'fields': ('storage_used', 'storage_quota')}),
    )
