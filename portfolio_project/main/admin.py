from django.contrib import admin
from django.contrib import messages
from .models import BlogPost, Contact, CourseCohort, CoursePayment, Project, SEOSettings, SiteProfile
from .payments import MpesaConfigurationError, MpesaRequestError, c2b_register_urls, transaction_status_query


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


@admin.register(CoursePayment)
class CoursePaymentAdmin(admin.ModelAdmin):
    list_display = (
        "course_name",
        "first_name",
        "second_name",
        "account_reference",
        "payment_method",
        "phone",
        "amount",
        "status",
        "created_at",
    )
    list_filter = ("status", "payment_method", "course_slug", "created_at")
    search_fields = (
        "first_name",
        "second_name",
        "email",
        "phone",
        "mpesa_phone",
        "account_reference",
        "mpesa_receipt_number",
    )
    actions = ("request_transaction_status", "register_c2b_urls")
    readonly_fields = (
        "account_reference",
        "checkout_request_id",
        "merchant_request_id",
        "mpesa_receipt_number",
        "transaction_status_request_id",
        "result_code",
        "result_description",
        "callback_payload",
        "created_at",
        "updated_at",
    )

    @admin.action(description="Request M-Pesa transaction status")
    def request_transaction_status(self, request, queryset):
        requested = 0
        for payment in queryset:
            try:
                response = transaction_status_query(request, payment)
                payment.transaction_status_request_id = response.get("ConversationID", "")
                payment.result_description = response.get("ResponseDescription", "")
                payment.save(update_fields=["transaction_status_request_id", "result_description", "updated_at"])
                requested += 1
            except (MpesaConfigurationError, MpesaRequestError) as error:
                self.message_user(request, f"{payment.account_reference}: {error}", level=messages.ERROR)
        if requested:
            self.message_user(request, f"Requested transaction status for {requested} payment(s).")

    @admin.action(description="Register C2B validation/confirmation URLs")
    def register_c2b_urls(self, request, queryset):
        try:
            c2b_register_urls(request)
            self.message_user(request, "C2B URLs registered with Daraja.")
        except (MpesaConfigurationError, MpesaRequestError) as error:
            self.message_user(request, str(error), level=messages.ERROR)


@admin.register(CourseCohort)
class CourseCohortAdmin(admin.ModelAdmin):
    list_display = ("title", "course_slug", "starts_on", "is_active", "created_at")
    list_filter = ("course_slug", "is_active", "starts_on")
    search_fields = ("title", "whatsapp_group_url")
