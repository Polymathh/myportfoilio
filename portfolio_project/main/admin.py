from django.contrib import admin
from .models import Project, Contact

@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ('title', 'category')   # shows columns in the admin list view
    list_filter = ('category',)            # add sidebar filter by category
    search_fields = ('title', 'description')  # search bar for easier lookup

@admin.register(Contact)
class ContactAdmin(admin.ModelAdmin):
    list_display = ('name', 'email', 'phone', 'subject', 'created_at')
    search_fields = ("name", "email", "subject")
    list_filter = ("created_at",)