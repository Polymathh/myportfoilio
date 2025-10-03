from django.conf import settings
from django.core.mail import send_mail
from django.shortcuts import render, redirect
from django.contrib import messages

from .forms import ContactForm
from .models import Project

def home(request):
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
            return redirect("home")
        else:
            messages.error(request, "Please fix the errors below.")

    return render(request, "home.html", {
        "categories": categories,
        "projects": projects,
        "form": form
    })
