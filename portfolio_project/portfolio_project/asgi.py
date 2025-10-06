"""
ASGI config for portfolio_project project.

It exposes the ASGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/5.1/howto/deployment/asgi/
"""

import os
import django
from django.core.wsgi import get_wsgi_application
from django.core.management import call_command

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "portfolio_project.settings")
django.setup()

# Run migrations on Vercel
if os.environ.get("VERCEL") == "1":
    try:
        call_command("migrate", interactive=False)
    except Exception as e:
        print("Migration failed:", e)

application = get_wsgi_application()

app = application