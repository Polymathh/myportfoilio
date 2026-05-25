from django.db import models
from django.urls import reverse
from django.utils import timezone
from django.utils.text import slugify


class SiteProfile(models.Model):
    name = models.CharField(max_length=120, default="Wambugu Moses")
    headline = models.CharField(
        max_length=220,
        default="Software Engineer | Graphic Designer | Upcoming AI Engineer",
    )
    intro = models.TextField(
        default="Building tech solutions that inspire change. Advocate for sustainability & STEM mentoring."
    )
    about_title = models.CharField(max_length=120, default="Who I am.")
    about_text = models.TextField(
        default="I'm a versatile Software Developer, Graphic Designer, and aspiring AI Engineer. My journey blends creativity with technology, allowing me to design and build digital solutions that are functional and visually impactful."
    )
    github_url = models.URLField(blank=True, default="https://github.com/Polymathh")
    linkedin_url = models.URLField(blank=True, default="https://www.linkedin.com/in/wambugumoses/")
    tiktok_url = models.URLField(blank=True, default="https://www.tiktok.com/@wambugu_ai")
    instagram_url = models.URLField(blank=True)
    facebook_url = models.URLField(blank=True)
    whatsapp_url = models.URLField(blank=True, default="https://wa.me/+254704141329")
    phone = models.CharField(max_length=40, blank=True, default="+254704141329")
    email = models.EmailField(blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Site Profile"
        verbose_name_plural = "Site Profile"

    def __str__(self):
        return self.name


class SEOSettings(models.Model):
    title = models.CharField(
        max_length=180,
        default="Wambugu Moses | AI Engineer, AI Agents & Agentic Systems",
    )
    description = models.TextField(
        default="Wambugu Moses, also known as WambuguAI, builds AI agents, agentic systems, software products, and digital experiences."
    )
    keywords = models.TextField(
        default="Wambugu Moses, Moses, WambuguAI, AI, artificial intelligence, AI agents, agentic systems, software engineer Kenya"
    )
    canonical_url = models.URLField(blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "SEO Settings"
        verbose_name_plural = "SEO Settings"

    def __str__(self):
        return self.title

class Project(models.Model):
    CATEGORY_CHOICES = [
        ('software', 'Software'),
        ('design', 'Graphic Design'),
        ('ai', 'AI work'),
    ]

    title = models.CharField(max_length=100)
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES)
    description = models.TextField()
    image = models.ImageField(upload_to='projects/')
    pdf = models.FileField(upload_to='projects/', blank=True, null=True)
    link = models.URLField(blank=True)
    display_order = models.PositiveIntegerField(default=100, help_text="Lower numbers appear first.")

    class Meta:
        ordering = ["display_order", "title"]

    def __str__(self):
        return self.title


class BlogPost(models.Model):
    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("published", "Published"),
    ]

    title = models.CharField(max_length=180)
    slug = models.SlugField(max_length=200, unique=True, blank=True)
    excerpt = models.TextField(help_text="Short summary shown on the blog page.")
    content = models.TextField()
    cover_image = models.ImageField(upload_to="blog/", blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="draft")
    seo_title = models.CharField(max_length=180, blank=True)
    seo_description = models.TextField(blank=True)
    display_order = models.PositiveIntegerField(default=100, help_text="Lower numbers appear first.")
    published_at = models.DateTimeField(default=timezone.now)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["display_order", "-published_at"]

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.title)
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse("blog_detail", kwargs={"slug": self.slug})

    def __str__(self):
        return self.title
    
class Contact(models.Model):
    name = models.CharField(max_length=150)
    phone = models.CharField(max_length=20, blank=True, null=True)
    email = models.EmailField()
    subject = models.CharField(max_length=250)
    message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} - {self.subject}"
