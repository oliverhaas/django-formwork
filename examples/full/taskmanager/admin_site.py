"""The admin site of the example, styled by the project's own Tailwind build."""

from django.conf import settings

from django_formwork.admin import AdminSite
from django_formwork.admin.history import PghistoryHistory


class TaskworkAdminSite(AdminSite):
    site_title = "Taskwork admin"
    site_header = "Taskwork"
    stylesheets = ("dist.css",)
    # Chart.js draws the charts in the list and change page slots; charts.js gives them the theme's colors.
    scripts = (
        *AdminSite.scripts,
        "https://cdn.jsdelivr.net/npm/chart.js@4.5.1/dist/chart.umd.min.js",
        "taskmanager/charts.js",
    )

    # On PostgreSQL, the history panel shows pghistory's events (see settings.py).
    if "pghistory" in settings.INSTALLED_APPS:
        history = PghistoryHistory()
