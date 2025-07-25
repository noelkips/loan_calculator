from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import CustomUser, Loan, Repayment

class CustomUserAdmin(UserAdmin):
    ordering = ('email',)
    list_display = ('email', 'first_name', 'last_name', 'department', 'designation', 'is_staff', 'is_active')
    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        ('Personal info', {'fields': ('first_name', 'last_name', 'department', 'designation')}),
        ('Permissions', {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        ('Important dates', {'fields': ('last_login', 'date_joined')}),
    )
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'first_name', 'last_name', 'department', 'designation', 'password1', 'password2'),
        }),
    )

admin.site.register(CustomUser, CustomUserAdmin)
admin.site.register(Loan)
admin.site.register(Repayment)