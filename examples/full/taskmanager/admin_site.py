"""The admin site of the example, styled by the project's own Tailwind build."""

from django.conf import settings

from django_formwork.admin import AdminSite
from django_formwork.admin.history import PghistoryHistory


class TaskworkAdminSite(AdminSite):
    site_title = "Taskwork admin"
    site_header = "Taskwork"
    stylesheets = ("dist.css",)

    # On PostgreSQL, the history panel shows pghistory's events (see settings.py).
    if "pghistory" in settings.INSTALLED_APPS:
        history = PghistoryHistory()
