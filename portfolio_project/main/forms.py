from django import forms
from .models import BlogPost, Contact, Project, SEOSettings, SiteProfile

class ContactForm(forms.ModelForm):
    class Meta:
        model = Contact
        fields = ["name", "phone", "email", "subject", "message"]
        widgets = {
            "name": forms.TextInput(attrs={"placeholder": "Name", "class": "input"}),
            "phone": forms.TextInput(attrs={"placeholder": "Phone No", "class": "input"}),
            "email": forms.EmailInput(attrs={"placeholder": "Email", "class": "input"}),
            "subject": forms.TextInput(attrs={"placeholder": "Subject", "class": "input"}),
            "message": forms.Textarea(attrs={"placeholder": "Message", "class": "textarea", "rows": 8}),
        }


class AdminFormMixin:
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.setdefault("class", "admin-input")


class SiteProfileForm(AdminFormMixin, forms.ModelForm):
    class Meta:
        model = SiteProfile
        fields = [
            "name", "headline", "intro", "about_title", "about_text", "email",
            "phone", "github_url", "linkedin_url", "tiktok_url", "instagram_url",
            "facebook_url", "whatsapp_url",
        ]
        widgets = {
            "intro": forms.Textarea(attrs={"rows": 3}),
            "about_text": forms.Textarea(attrs={"rows": 8}),
        }


class SEOSettingsForm(AdminFormMixin, forms.ModelForm):
    class Meta:
        model = SEOSettings
        fields = ["title", "description", "keywords", "canonical_url"]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 4}),
            "keywords": forms.Textarea(attrs={"rows": 4}),
        }


class ProjectForm(AdminFormMixin, forms.ModelForm):
    class Meta:
        model = Project
        fields = ["title", "category", "description", "image", "pdf", "link"]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 5}),
        }


class BlogPostForm(AdminFormMixin, forms.ModelForm):
    class Meta:
        model = BlogPost
        fields = [
            "title", "slug", "excerpt", "content", "cover_image", "status",
            "seo_title", "seo_description", "published_at",
        ]
        widgets = {
            "excerpt": forms.Textarea(attrs={"rows": 4}),
            "content": forms.Textarea(attrs={"rows": 12}),
            "seo_description": forms.Textarea(attrs={"rows": 3}),
            "published_at": forms.DateTimeInput(attrs={"type": "datetime-local"}),
        }
