"""
WSGI config for portfolio_project project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/5.1/howto/deployment/wsgi/
"""

import os
import django
from django.core.wsgi import get_wsgi_application
from django.core.management import call_command

# 1️⃣ Set default settings module
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "portfolio_project.settings")

# 2️⃣ Setup Django
django.setup()

# 3️⃣ Run migrations on Vercel (ephemeral /tmp SQLite DB)
if os.environ.get("VERCEL") == "1":
    try:
        call_command("migrate", interactive=False)
        print("✅ Migrations applied successfully on Vercel.")
    except Exception as e:
        print("❌ Migration failed:", e)

# 4️⃣ Get WSGI application
application = get_wsgi_application()



app = application