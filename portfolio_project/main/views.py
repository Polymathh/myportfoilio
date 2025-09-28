from django.shortcuts import render
from .models import Project

def home(request):
    categories = Project.CATEGORY_CHOICES
    projects = Project.objects.all()[:6]
    return render(request, "home.html", {
        "categories": categories,
        "projects": projects,
    })

