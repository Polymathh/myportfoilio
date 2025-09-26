from django.db import models

class Project(models.Model):
    CATEGORY_CHOICES = [
        ('all', 'All'),
        ('software', 'Software'),
        ('design', 'Graphic Design'),
        ('ai', 'AI work'),
    ]

    title = models.CharField(max_length=100)
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES)
    description = models.CharField(max_length=300)
    image = models.ImageField(upload_to='projects/')
    link = models.URLField(blank=True)

    def __str__(self):
        return self.title
