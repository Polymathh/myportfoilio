from django.contrib import admin
from .models import Project

@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ('title', 'category')   # shows columns in the admin list view
    list_filter = ('category',)            # add sidebar filter by category
    search_fields = ('title', 'description')  # search bar for easier lookup
