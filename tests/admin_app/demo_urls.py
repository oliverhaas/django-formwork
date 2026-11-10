"""The URLs of the browsable demo: the test URLs, plus the Inter font that the test CSS names."""

from django_formwork.admin import site

from .urls import urlpatterns

__all__ = ["urlpatterns"]

site.stylesheets = ("https://fonts.googleapis.com/css2?family=Inter:wght@400..700&display=swap", *site.stylesheets)
