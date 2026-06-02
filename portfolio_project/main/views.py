import csv
from django.conf import settings
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import user_passes_test
from django.core.mail import EmailMultiAlternatives, send_mail
from django.db import DatabaseError
from django.template.loader import render_to_string
from django.shortcuts import get_object_or_404, render, redirect
from django.contrib import messages
from django.http import HttpResponse, JsonResponse
from django.db.models import Count, Q, Sum
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from .forms import BlogPostForm, ContactForm, CourseCohortForm, ProjectForm, SEOSettingsForm, SiteProfileForm
from .models import BlogPost, Contact, CourseCohort, CoursePayment, Project, SEOSettings, SiteProfile
from .payments import MpesaConfigurationError, MpesaRequestError, extract_callback_metadata, normalize_phone, stk_push, stk_query


COURSES = {
    "vibe-coding": {
        "name": "Weekend Vibe Code",
        "checkout_course": "Course Vibe Coding Bootcamp",
        "checkout_title": "Vibe Coding",
        "summary": "Build a real working app from scratch using AI tools, no coding background needed whatsoever.",
        "duration": "3 days . Live on Google Meet",
        "card_duration": "3 Day course",
        "format": "Complete beginners welcome",
        "price": 1,
        "price_display": "1",
    },
    "ai-automation": {
        "name": "AI Automation Course",
        "checkout_course": "AI Automation with Bootcamp",
        "checkout_title": "Automation",
        "summary": "Master make.com, build real automation workflows, and save hours every week starting from absolute zero.",
        "duration": "5 days . Live on Google Meet",
        "card_duration": "5 Day course",
        "format": "Complete beginners welcome",
        "price": 1,
        "price_display": "1",
    },
}


MPESA_STILL_PROCESSING_CODES = {"4999"}
MPESA_PHONE_PROMPT_SECONDS = 12


def _course_choices():
    return [(slug, course["name"]) for slug, course in COURSES.items()]


def _active_course_cohort(course_slug):
    active_cohorts = CourseCohort.objects.filter(
        course_slug=course_slug,
        is_active=True,
    )
    today = timezone.localdate()
    current_or_recent = active_cohorts.filter(starts_on__lte=today).order_by("-starts_on", "-created_at").first()
    if current_or_recent:
        return current_or_recent
    return active_cohorts.filter(starts_on__gt=today).order_by("starts_on", "created_at").first()


def _send_enrollment_email(payment, force=False):
    if payment.enrollment_email_sent_at and not force:
        return True, "Enrollment email was already sent."
    if not payment.cohort:
        payment.cohort = _active_course_cohort(payment.course_slug)
        if payment.cohort:
            payment.save(update_fields=["cohort", "updated_at"])
    if not payment.cohort:
        return False, "No active course week is set for this course."
    whatsapp_url = payment.cohort.whatsapp_group_url
    profile = get_site_profile()
    instructor_name = profile.name or "Wambugu Moses"
    subject = f"Welcome to {payment.course_name}"
    context = {
        "payment": payment,
        "student_name": payment.first_name,
        "course_name": payment.course_name,
        "cohort": payment.cohort,
        "whatsapp_url": whatsapp_url,
        "instructor_name": instructor_name,
    }
    text_body = render_to_string("emails/course_enrollment.txt", context)
    html_body = render_to_string("emails/course_enrollment.html", context)
    email = EmailMultiAlternatives(
        subject=subject,
        body=text_body,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[payment.email],
        reply_to=[settings.DEFAULT_FROM_EMAIL],
    )
    email.attach_alternative(html_body, "text/html")
    email.send(fail_silently=False)
    payment.enrollment_email_sent_at = timezone.now()
    payment.save(update_fields=["enrollment_email_sent_at", "updated_at"])
    return True, "Enrollment email sent."


def _mark_payment_paid(payment, save_fields):
    payment.status = CoursePayment.STATUS_PAID
    payment.save(update_fields=save_fields)
    try:
        _send_enrollment_email(payment)
    except Exception:
        pass


def _save_payment_fields(payment, fields):
    try:
        payment.save(update_fields=fields)
    except DatabaseError:
        pass


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
        first_name = request.POST.get("first_name", "").strip()
        second_name = request.POST.get("second_name", "").strip()
        email = request.POST.get("email", "").strip()

        if not all([first_name, second_name, email]):
            messages.error(request, "Please fill in your learner details.")
        else:
            payment = CoursePayment.objects.create(
                course_slug=course_slug,
                course_name=course["checkout_course"],
                cohort=_active_course_cohort(course_slug),
                first_name=first_name,
                second_name=second_name,
                email=email,
                phone="",
                amount=course["price"],
                status=CoursePayment.STATUS_PENDING,
            )
            return redirect("course_payment", payment_id=payment.id)

    return render(request, "course_checkout.html", {
        "course": course,
        "course_slug": course_slug,
        "profile": get_site_profile(),
    })


def course_payment(request, payment_id):
    payment = get_object_or_404(CoursePayment, pk=payment_id)
    if payment.status == CoursePayment.STATUS_PAID:
        return redirect("course_payment_status", payment_id=payment.id)

    if request.method == "POST":
        mpesa_phone = request.POST.get("mpesa_phone", "").strip()
        try:
            normalized_mpesa_phone = normalize_phone(mpesa_phone)
            payment.phone = normalized_mpesa_phone
            payment.mpesa_phone = normalized_mpesa_phone
            payment.save(update_fields=["phone", "mpesa_phone", "updated_at"])

            response = stk_push(request, payment)
            payment.status = CoursePayment.STATUS_PROCESSING
            payment.checkout_request_id = response.get("CheckoutRequestID", "")
            payment.merchant_request_id = response.get("MerchantRequestID", "")
            payment.result_description = response.get("ResponseDescription", "")
            payment.save(update_fields=[
                "status",
                "checkout_request_id",
                "merchant_request_id",
                "result_description",
                "updated_at",
            ])
            messages.success(request, "M-Pesa prompt sent. Enter your PIN on your phone to complete enrollment.")
            return redirect("course_payment_status", payment_id=payment.id)
        except ValueError as error:
            messages.error(request, str(error))
        except MpesaConfigurationError:
            messages.error(request, "M-Pesa Express is not configured yet. Please check the Daraja settings.")
        except MpesaRequestError:
            messages.error(request, "Could not start M-Pesa payment. Please try again in a moment.")

    return render(request, "course_payment.html", {
        "payment": payment,
        "profile": get_site_profile(),
    })


def course_payment_status(request, payment_id):
    payment = get_object_or_404(CoursePayment, pk=payment_id)
    prompt_seconds = (timezone.now() - payment.updated_at).total_seconds()
    show_phone_prompt = (
        payment.status == CoursePayment.STATUS_PROCESSING
        and payment.checkout_request_id
        and not payment.result_code
        and prompt_seconds < MPESA_PHONE_PROMPT_SECONDS
    )

    if payment.status == CoursePayment.STATUS_PROCESSING and payment.checkout_request_id and not show_phone_prompt:
        try:
            response = stk_query(payment)
            result_code = str(response.get("ResultCode", ""))
            payment.result_code = result_code
            payment.result_description = response.get("ResultDesc", response.get("ResponseDescription", ""))
            if result_code == "0":
                _mark_payment_paid(payment, ["result_code", "result_description", "status", "updated_at"])
                return render(request, "course_payment_status.html", {
                    "payment": payment,
                    "profile": get_site_profile(),
                    "show_phone_prompt": show_phone_prompt,
                })
            elif result_code and result_code not in MPESA_STILL_PROCESSING_CODES:
                payment.status = CoursePayment.STATUS_FAILED
                _save_payment_fields(payment, ["result_code", "result_description", "status", "updated_at"])
            else:
                _save_payment_fields(payment, ["result_code", "result_description", "status"])
        except (MpesaConfigurationError, MpesaRequestError) as error:
            if "still under processing" in str(error).lower():
                payment.result_description = "The transaction is still under processing."
            else:
                payment.result_description = f"Waiting for M-Pesa confirmation: {error}"
            _save_payment_fields(payment, ["result_description"])

    return render(request, "course_payment_status.html", {
        "payment": payment,
        "profile": get_site_profile(),
        "show_phone_prompt": show_phone_prompt,
    })


@csrf_exempt
@require_POST
def mpesa_callback(request):
    try:
        import json

        payload = json.loads(request.body.decode("utf-8"))
    except ValueError:
        return JsonResponse({"ResultCode": 1, "ResultDesc": "Invalid payload"}, status=400)

    callback = payload.get("Body", {}).get("stkCallback", {})
    checkout_request_id = callback.get("CheckoutRequestID", "")
    result_code = str(callback.get("ResultCode", ""))
    result_description = callback.get("ResultDesc", "")
    metadata = extract_callback_metadata(callback)

    payment = CoursePayment.objects.filter(checkout_request_id=checkout_request_id).first()
    if payment:
        payment.callback_payload = payload
        payment.result_code = result_code
        payment.result_description = result_description
        payment.mpesa_receipt_number = str(metadata.get("MpesaReceiptNumber", ""))
        if result_code == "0":
            payment.status = CoursePayment.STATUS_PAID
        elif result_code not in MPESA_STILL_PROCESSING_CODES:
            payment.status = CoursePayment.STATUS_FAILED
        payment.save(update_fields=[
            "callback_payload",
            "result_code",
            "result_description",
            "mpesa_receipt_number",
            "status",
            "updated_at",
        ])
        if payment.status == CoursePayment.STATUS_PAID:
            try:
                _send_enrollment_email(payment)
            except Exception:
                pass

    return JsonResponse({"ResultCode": 0, "ResultDesc": "Accepted"})


@csrf_exempt
@require_POST
def mpesa_c2b_validation(request):
    return JsonResponse({"ResultCode": 0, "ResultDesc": "Accepted"})


@csrf_exempt
@require_POST
def mpesa_c2b_confirmation(request):
    try:
        import json

        payload = json.loads(request.body.decode("utf-8"))
    except ValueError:
        return JsonResponse({"ResultCode": 1, "ResultDesc": "Invalid payload"}, status=400)

    account_reference = str(payload.get("BillRefNumber", "")).strip()
    receipt_number = str(payload.get("TransID", "")).strip()
    amount = payload.get("TransAmount")
    phone = str(payload.get("MSISDN", "")).strip()
    payment = CoursePayment.objects.filter(account_reference__iexact=account_reference).first()
    if payment:
        payment.payment_method = CoursePayment.METHOD_TILL
        payment.status = CoursePayment.STATUS_PAID
        payment.mpesa_receipt_number = receipt_number
        payment.phone = phone or payment.phone
        payment.mpesa_phone = phone or payment.mpesa_phone
        payment.result_code = "0"
        payment.result_description = f"C2B payment confirmed for KES {amount}."
        payment.callback_payload = payload
        payment.save(update_fields=[
            "payment_method",
            "status",
            "mpesa_receipt_number",
            "phone",
            "mpesa_phone",
            "result_code",
            "result_description",
            "callback_payload",
            "updated_at",
        ])
        try:
            _send_enrollment_email(payment)
        except Exception:
            pass

    return JsonResponse({"ResultCode": 0, "ResultDesc": "Accepted"})


@csrf_exempt
@require_POST
def mpesa_transaction_status_result(request):
    try:
        import json

        payload = json.loads(request.body.decode("utf-8"))
    except ValueError:
        return JsonResponse({"ResultCode": 1, "ResultDesc": "Invalid payload"}, status=400)

    result = payload.get("Result", {})
    reference = str(result.get("ReferenceData", {}).get("ReferenceItem", {}).get("Value", ""))
    receipt = str(result.get("TransactionID", ""))
    payment = CoursePayment.objects.filter(account_reference__iexact=reference).first()
    if not payment and receipt:
        payment = CoursePayment.objects.filter(mpesa_receipt_number=receipt).first()
    if payment:
        result_code = str(result.get("ResultCode", ""))
        payment.result_code = result_code
        payment.result_description = result.get("ResultDesc", "")
        payment.callback_payload = payload
        if result_code == "0":
            payment.status = CoursePayment.STATUS_PAID
        payment.save(update_fields=["result_code", "result_description", "callback_payload", "status", "updated_at"])
        if payment.status == CoursePayment.STATUS_PAID:
            try:
                _send_enrollment_email(payment)
            except Exception:
                pass

    return JsonResponse({"ResultCode": 0, "ResultDesc": "Accepted"})


@csrf_exempt
@require_POST
def mpesa_transaction_status_timeout(request):
    return JsonResponse({"ResultCode": 0, "ResultDesc": "Accepted"})


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
    payment_summary = CoursePayment.objects.aggregate(
        total=Count("id"),
        paid=Count("id", filter=Q(status=CoursePayment.STATUS_PAID)),
        processing=Count("id", filter=Q(status=CoursePayment.STATUS_PROCESSING)),
        failed=Count("id", filter=Q(status=CoursePayment.STATUS_FAILED)),
        revenue=Sum("amount", filter=Q(status=CoursePayment.STATUS_PAID)),
    )
    return render(request, "custom_admin/dashboard.html", {
        "project_count": Project.objects.count(),
        "post_count": BlogPost.objects.count(),
        "published_count": BlogPost.objects.filter(status="published").count(),
        "contact_count": Contact.objects.count(),
        "payment_summary": payment_summary,
        "course_counts": _course_payment_counts(),
        "recent_cohorts": CourseCohort.objects.all()[:5],
        "recent_payments": CoursePayment.objects.order_by("-created_at")[:5],
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
def custom_admin_cohorts(request):
    return render(request, "custom_admin/cohorts.html", {
        "cohorts": CourseCohort.objects.all(),
        "courses": COURSES,
    })


@staff_required
def custom_admin_cohort_edit(request, pk=None):
    cohort = get_object_or_404(CourseCohort, pk=pk) if pk else None
    form = CourseCohortForm(
        request.POST or None,
        instance=cohort,
        course_choices=_course_choices(),
    )
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Course week saved.")
        return redirect("custom_admin_cohorts")
    return render(request, "custom_admin/form.html", {
        "title": "Edit Course Week" if cohort else "Add Course Week",
        "form": form,
    })


@staff_required
def custom_admin_cohort_delete(request, pk):
    cohort = get_object_or_404(CourseCohort, pk=pk)
    if request.method == "POST":
        cohort.delete()
        messages.success(request, "Course week deleted.")
        return redirect("custom_admin_cohorts")
    return render(request, "custom_admin/confirm_delete.html", {
        "title": "Delete Course Week",
        "object_name": cohort.title,
        "cancel_url": "custom_admin_cohorts",
    })


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


def _filtered_payments(request):
    payments = CoursePayment.objects.order_by("-created_at")
    status = request.GET.get("status", "").strip()
    course = request.GET.get("course", "").strip()
    query = request.GET.get("q", "").strip()

    if status:
        payments = payments.filter(status=status)
    if course:
        payments = payments.filter(course_slug=course)
    if query:
        payments = payments.filter(
            Q(first_name__icontains=query)
            | Q(second_name__icontains=query)
            | Q(email__icontains=query)
            | Q(phone__icontains=query)
            | Q(mpesa_phone__icontains=query)
            | Q(account_reference__icontains=query)
            | Q(mpesa_receipt_number__icontains=query)
            | Q(checkout_request_id__icontains=query)
        )
    return payments


def _course_payment_counts(payments=None):
    payments = payments or CoursePayment.objects.all()
    rows = payments.values("course_slug").annotate(
        total=Count("id"),
        paid=Count("id", filter=Q(status=CoursePayment.STATUS_PAID)),
        processing=Count("id", filter=Q(status=CoursePayment.STATUS_PROCESSING)),
        failed=Count("id", filter=Q(status=CoursePayment.STATUS_FAILED)),
        revenue=Sum("amount", filter=Q(status=CoursePayment.STATUS_PAID)),
    )
    counts_by_slug = {row["course_slug"]: row for row in rows}
    counts = []
    for slug, course in COURSES.items():
        row = counts_by_slug.get(slug, {})
        counts.append({
            "slug": slug,
            "name": course["name"],
            "total": row.get("total", 0),
            "paid": row.get("paid", 0),
            "processing": row.get("processing", 0),
            "failed": row.get("failed", 0),
            "revenue": row.get("revenue", 0) or 0,
        })
    return counts


@staff_required
def custom_admin_payments(request):
    payments = _filtered_payments(request)
    summary = payments.aggregate(
        count=Count("id"),
        paid=Count("id", filter=Q(status=CoursePayment.STATUS_PAID)),
        processing=Count("id", filter=Q(status=CoursePayment.STATUS_PROCESSING)),
        failed=Count("id", filter=Q(status=CoursePayment.STATUS_FAILED)),
        revenue=Sum("amount", filter=Q(status=CoursePayment.STATUS_PAID)),
    )
    return render(request, "custom_admin/payments.html", {
        "payments": payments[:100],
        "summary": summary,
        "course_counts": _course_payment_counts(payments),
        "status_choices": CoursePayment.STATUS_CHOICES,
        "course_choices": COURSES,
        "selected_status": request.GET.get("status", ""),
        "selected_course": request.GET.get("course", ""),
        "query": request.GET.get("q", ""),
    })


@staff_required
def custom_admin_payments_export(request):
    payments = _filtered_payments(request)
    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="course-payments.csv"'
    writer = csv.writer(response)
    writer.writerow([
        "ID",
        "Status",
        "Course",
        "First name",
        "Second name",
        "Email",
        "Phone",
        "Amount",
        "Reference",
        "Receipt",
        "Checkout request",
        "Created",
    ])
    for payment in payments:
        writer.writerow([
            payment.id,
            payment.status,
            payment.course_name,
            payment.first_name,
            payment.second_name,
            payment.email,
            payment.phone or payment.mpesa_phone,
            payment.amount,
            payment.account_reference,
            payment.mpesa_receipt_number,
            payment.checkout_request_id,
            payment.created_at.isoformat(),
        ])
    return response


@staff_required
@require_POST
def custom_admin_payment_action(request, pk, action):
    payment = get_object_or_404(CoursePayment, pk=pk)
    if action == "confirm":
        receipt = request.POST.get("receipt", "").strip().upper()
        payment.status = CoursePayment.STATUS_PAID
        payment.result_code = "0"
        payment.result_description = "Payment confirmed manually by admin."
        if receipt:
            payment.mpesa_receipt_number = receipt
        payment.save(update_fields=["status", "result_code", "result_description", "mpesa_receipt_number", "updated_at"])
        try:
            email_sent, email_message = _send_enrollment_email(payment)
            if email_sent:
                messages.success(request, f"Payment {payment.account_reference} confirmed. {email_message}")
            else:
                messages.warning(request, f"Payment {payment.account_reference} confirmed, but email was not sent: {email_message}")
        except Exception as error:
            messages.warning(request, f"Payment {payment.account_reference} confirmed, but email failed: {error}")
    elif action == "fail":
        payment.status = CoursePayment.STATUS_FAILED
        payment.result_description = "Payment marked failed by admin."
        payment.save(update_fields=["status", "result_description", "updated_at"])
        messages.success(request, f"Payment {payment.account_reference} marked failed.")
    elif action == "send-email":
        if payment.status != CoursePayment.STATUS_PAID:
            messages.error(request, "Only paid enrollments can receive the WhatsApp group email.")
        else:
            try:
                email_sent, email_message = _send_enrollment_email(payment, force=True)
                if email_sent:
                    messages.success(request, email_message)
                else:
                    messages.warning(request, f"Email was not sent: {email_message}")
            except Exception as error:
                messages.error(request, f"Email failed: {error}")
    else:
        messages.error(request, "Unknown payment action.")
    return redirect("custom_admin_payments")


@staff_required
def custom_admin_payment_delete(request, pk):
    payment = get_object_or_404(CoursePayment, pk=pk)
    if request.method == "POST":
        reference = payment.account_reference
        payment.delete()
        messages.success(request, f"Payment {reference} deleted.")
        return redirect("custom_admin_payments")
    return render(request, "custom_admin/confirm_delete.html", {
        "title": "Delete Payment Record",
        "object_name": f"{payment.account_reference} - {payment.first_name} {payment.second_name}",
        "cancel_url": "custom_admin_payments",
    })


@staff_required
@require_POST
def custom_admin_payments_bulk_delete(request):
    payment_ids = request.POST.getlist("payment_ids")
    payments = CoursePayment.objects.filter(id__in=payment_ids)
    if not payment_ids or not payments.exists():
        messages.error(request, "Select at least one payment record to delete.")
        return redirect("custom_admin_payments")

    if request.POST.get("confirm") == "yes":
        count = payments.count()
        payments.delete()
        messages.success(request, f"Deleted {count} payment record(s).")
        return redirect("custom_admin_payments")

    return render(request, "custom_admin/bulk_delete_payments.html", {
        "payments": payments.order_by("-created_at"),
        "payment_ids": payment_ids,
    })
