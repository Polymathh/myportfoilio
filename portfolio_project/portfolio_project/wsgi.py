"""
WSGI config for portfolio_project project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/5.1/howto/deployment/wsgi/
"""

import os
import shutil
from django.core.wsgi import get_wsgi_application

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TMP_DB = '/tmp/db.sqlite3'
LOCAL_DB = os.path.join(BASE_DIR, 'db.sqlite3')  # your local database

# Copy the database if it doesn't exist in /tmp
if not os.path.exists(TMP_DB) and os.path.exists(LOCAL_DB):
    shutil.copy(LOCAL_DB, TMP_DB)

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'portfolio_project.settings')

application = get_wsgi_application()


