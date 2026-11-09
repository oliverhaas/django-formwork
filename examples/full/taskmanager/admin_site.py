"""The admin site of the example, styled by the project's own Tailwind build."""

from django_formwork.admin import AdminSite


class TaskworkAdminSite(AdminSite):
    site_title = "Taskwork admin"
    site_header = "Taskwork"
    stylesheets = ("dist.css",)
