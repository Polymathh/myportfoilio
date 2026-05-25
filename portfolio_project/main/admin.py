from django.contrib import admin
from .models import BlogPost, Contact, Project, SEOSettings, SiteProfile


admin.site.site_header = "Wambugu Moses Portfolio Admin"
admin.site.site_title = "Portfolio Admin"
admin.site.index_title = "Edit portfolio content"


@admin.register(SiteProfile)
class SiteProfileAdmin(admin.ModelAdmin):
    fieldsets = (
        ("Homepage", {"fields": ("name", "headline", "intro", "about_title", "about_text")}),
        ("Contact and social links", {"fields": ("email", "phone", "github_url", "linkedin_url", "tiktok_url", "instagram_url", "facebook_url", "whatsapp_url")}),
    )

    def has_add_permission(self, request):
        return not SiteProfile.objects.exists()


@admin.register(SEOSettings)
class SEOSettingsAdmin(admin.ModelAdmin):
    fields = ("title", "description", "keywords", "canonical_url")

    def has_add_permission(self, request):
        return not SEOSettings.objects.exists()

@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ('title', 'category', 'display_order')   # shows columns in the admin list view
    list_filter = ('category',)            # add sidebar filter by category
    search_fields = ('title', 'description')  # search bar for easier lookup
    list_editable = ('display_order',)

@admin.register(Contact)
class ContactAdmin(admin.ModelAdmin):
    list_display = ('name', 'email', 'phone', 'subject', 'created_at')
    search_fields = ("name", "email", "subject")
    list_filter = ("created_at",)
    readonly_fields = ("created_at",)


@admin.register(BlogPost)
class BlogPostAdmin(admin.ModelAdmin):
    list_display = ("title", "status", "display_order", "published_at", "updated_at")
    list_filter = ("status", "published_at")
    search_fields = ("title", "excerpt", "content")
    list_editable = ("display_order",)
    prepopulated_fields = {"slug": ("title",)}
    date_hierarchy = "published_at"
    fieldsets = (
        ("Post", {"fields": ("title", "slug", "excerpt", "content", "cover_image", "status", "display_order", "published_at")}),
        ("SEO", {"fields": ("seo_title", "seo_description"), "classes": ("collapse",)}),
    )
