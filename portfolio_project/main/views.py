from django.conf import settings
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import user_passes_test
from django.core.mail import send_mail
from django.shortcuts import get_object_or_404, render, redirect
from django.contrib import messages
from django.http import HttpResponse
from django.views.decorators.http import require_POST

from .forms import BlogPostForm, ContactForm, ProjectForm, SEOSettingsForm, SiteProfileForm
from .models import BlogPost, Contact, Project, SEOSettings, SiteProfile


COURSES = {
    "vibe-coding": {
        "name": "Weekend Vibe Code",
        "checkout_course": "Course Vibe Coding Bootcamp",
        "checkout_title": "Vibe Coding",
        "summary": "Build a real working app from scratch using AI tools, no coding background needed whatsoever.",
        "duration": "3 days . Live on Google Meet",
        "card_duration": "3 Day course",
        "format": "Complete beginners welcome",
        "price": 4500,
        "price_display": "4,500",
    },
    "ai-automation": {
        "name": "AI Automation Course",
        "checkout_course": "AI Automation with Bootcamp",
        "checkout_title": "Automation",
        "summary": "Master make.com, build real automation workflows, and save hours every week starting from absolute zero.",
        "duration": "5 days . Live on Google Meet",
        "card_duration": "5 Day course",
        "format": "Complete beginners welcome",
        "price": 6500,
        "price_display": "6,500",
    },
}


def get_site_profile():
    return SiteProfile.objects.first() or SiteProfile()


def get_seo_settings():
    return SEOSettings.objects.first() or SEOSettings()


def staff_required(view_func):
    return user_passes_test(lambda user: user.is_staff, login_url="custom_admin_login")(view_func)

def courses_home(request):
    return render(request, "courses.html", {
        "courses": COURSES,
        "profile": get_site_profile(),
        "whatsapp_url": "https://wa.me/254704141329",
    })


def course_checkout(request, course_slug):
    course = COURSES.get(course_slug)
    if course is None:
        return redirect("courses_home")

    if request.method == "POST":
        messages.info(request, "M-Pesa checkout is ready for Daraja credentials. The payment request was not sent yet.")

    return render(request, "course_checkout.html", {
        "course": course,
        "course_slug": course_slug,
        "profile": get_site_profile(),
    })


def portfolio_home(request):
    categories = Project.CATEGORY_CHOICES
    selected_category = request.GET.get("category", "all")
    if selected_category == "all":
        projects = Project.objects.all()[:6]
    else:
        projects = Project.objects.filter(category=selected_category)


    form = ContactForm()

    if request.method == "POST":
        form = ContactForm(request.POST)
        if form.is_valid():
            contact = form.save()
            subject = f"Portfolio Contact: {contact.subject}"
            message = f"Name: {contact.name}\nPhone: {contact.phone}\nEmail: {contact.email}\nMessage:\n{contact.message}"
            send_mail(
                subject=subject,
                message=message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[settings.DEFAULT_FROM_EMAIL],
                fail_silently=False,
                # headers={"Reply-To": contact.email},
            )

            # Optional: Auto-reply to sender
            send_mail(
                subject="Thanks for contacting me",
                message="Hi {},\n\nThanks for reaching out, I will reply ASAP.".format(contact.name),
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[contact.email],
                fail_silently=True,
            )

            messages.success(request, "Thanks! Your message has been sent.")
            return redirect("portfolio_home")
        else:
            messages.error(request, "Please fix the errors below.")

    featured_posts = BlogPost.objects.filter(status="published")[:3]

    return render(request, "home.html", {
        "categories": categories,
        "projects": projects,
        "form": form,
        "profile": get_site_profile(),
        "seo": get_seo_settings(),
        "featured_posts": featured_posts,
    })


def blog_list(request):
    posts = BlogPost.objects.filter(status="published")
    seo = get_seo_settings()
    return render(request, "blog_list.html", {
        "posts": posts,
        "profile": get_site_profile(),
        "seo": seo,
        "page_title": f"Blog | {seo.title}",
        "page_description": "Articles by Wambugu Moses on AI, AI agents, agentic systems, software engineering, and digital product building.",
    })


def blog_detail(request, slug):
    post = get_object_or_404(BlogPost, slug=slug, status="published")
    seo = get_seo_settings()
    return render(request, "blog_detail.html", {
        "post": post,
        "profile": get_site_profile(),
        "seo": seo,
        "page_title": post.seo_title or f"{post.title} | Wambugu Moses",
        "page_description": post.seo_description or post.excerpt,
    })


def robots_txt(request):
    lines = [
        "User-agent: *",
        "Allow: /",
        f"Sitemap: {request.build_absolute_uri('/sitemap.xml')}",
    ]
    return HttpResponse("\n".join(lines), content_type="text/plain")


def sitemap_xml(request):
    posts = BlogPost.objects.filter(status="published")
    urls = [
        request.build_absolute_uri("/"),
        request.build_absolute_uri("/portfolio/"),
        request.build_absolute_uri("/blog/"),
    ]
    urls.extend(request.build_absolute_uri(post.get_absolute_url()) for post in posts)
    xml_urls = "".join(f"<url><loc>{url}</loc></url>" for url in urls)
    xml = f'<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{xml_urls}</urlset>'
    return HttpResponse(xml, content_type="application/xml")


def custom_admin_login(request):
    if request.user.is_authenticated and request.user.is_staff:
        return redirect("custom_admin_dashboard")

    if request.method == "POST":
        username = request.POST.get("username")
        password = request.POST.get("password")
        user = authenticate(request, username=username, password=password)
        if user is not None and user.is_staff:
            login(request, user)
            return redirect("custom_admin_dashboard")
        messages.error(request, "Invalid admin login.")

    return render(request, "custom_admin/login.html")


def custom_admin_logout(request):
    logout(request)
    return redirect("custom_admin_login")


@staff_required
def custom_admin_dashboard(request):
    return render(request, "custom_admin/dashboard.html", {
        "project_count": Project.objects.count(),
        "post_count": BlogPost.objects.count(),
        "published_count": BlogPost.objects.filter(status="published").count(),
        "contact_count": Contact.objects.count(),
        "recent_contacts": Contact.objects.order_by("-created_at")[:5],
        "recent_posts": BlogPost.objects.order_by("-updated_at")[:5],
    })


@staff_required
def custom_admin_profile(request):
    profile, _ = SiteProfile.objects.get_or_create(name="Wambugu Moses")
    form = SiteProfileForm(request.POST or None, instance=profile)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Profile updated.")
        return redirect("custom_admin_profile")
    return render(request, "custom_admin/form.html", {"title": "Edit Site Profile", "form": form})


@staff_required
def custom_admin_seo(request):
    seo, _ = SEOSettings.objects.get_or_create(title="Wambugu Moses | AI Engineer, AI Agents & Agentic Systems")
    form = SEOSettingsForm(request.POST or None, instance=seo)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "SEO settings updated.")
        return redirect("custom_admin_seo")
    return render(request, "custom_admin/form.html", {"title": "Edit SEO Settings", "form": form})


@staff_required
def custom_admin_projects(request):
    return render(request, "custom_admin/projects.html", {
        "projects": Project.objects.order_by("display_order", "title"),
    })


@staff_required
def custom_admin_project_edit(request, pk=None):
    project = get_object_or_404(Project, pk=pk) if pk else None
    form = ProjectForm(request.POST or None, request.FILES or None, instance=project)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Project saved.")
        return redirect("custom_admin_projects")
    return render(request, "custom_admin/form.html", {
        "title": "Edit Project" if project else "Add Project",
        "form": form,
    })


@staff_required
def custom_admin_project_delete(request, pk):
    project = get_object_or_404(Project, pk=pk)
    if request.method == "POST":
        project.delete()
        messages.success(request, "Project deleted.")
        return redirect("custom_admin_projects")
    return render(request, "custom_admin/confirm_delete.html", {
        "title": "Delete Project",
        "object_name": project.title,
        "cancel_url": "custom_admin_projects",
    })


def move_item(model, pk, direction):
    item = get_object_or_404(model, pk=pk)
    ordered_items = list(model.objects.order_by("display_order", "pk"))
    index = ordered_items.index(item)
    swap_index = index - 1 if direction == "up" else index + 1

    if 0 <= swap_index < len(ordered_items):
        other = ordered_items[swap_index]
        item.display_order, other.display_order = other.display_order, item.display_order
        if item.display_order == other.display_order:
            item.display_order = swap_index + 1
            other.display_order = index + 1
        item.save(update_fields=["display_order"])
        other.save(update_fields=["display_order"])


@staff_required
@require_POST
def custom_admin_project_move(request, pk, direction):
    move_item(Project, pk, direction)
    return redirect("custom_admin_projects")


@staff_required
def custom_admin_posts(request):
    return render(request, "custom_admin/posts.html", {
        "posts": BlogPost.objects.order_by("display_order", "-published_at"),
    })


@staff_required
def custom_admin_post_edit(request, pk=None):
    post = get_object_or_404(BlogPost, pk=pk) if pk else None
    form = BlogPostForm(request.POST or None, request.FILES or None, instance=post)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Blog post saved.")
        return redirect("custom_admin_posts")
    return render(request, "custom_admin/form.html", {
        "title": "Edit Blog Post" if post else "Add Blog Post",
        "form": form,
    })


@staff_required
def custom_admin_post_delete(request, pk):
    post = get_object_or_404(BlogPost, pk=pk)
    if request.method == "POST":
        post.delete()
        messages.success(request, "Blog post deleted.")
        return redirect("custom_admin_posts")
    return render(request, "custom_admin/confirm_delete.html", {
        "title": "Delete Blog Post",
        "object_name": post.title,
        "cancel_url": "custom_admin_posts",
    })


@staff_required
@require_POST
def custom_admin_post_move(request, pk, direction):
    move_item(BlogPost, pk, direction)
    return redirect("custom_admin_posts")


@staff_required
def custom_admin_contacts(request):
    return render(request, "custom_admin/contacts.html", {
        "contacts": Contact.objects.order_by("-created_at"),
    })
