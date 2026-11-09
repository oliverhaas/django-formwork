from django.urls import include, path

from django_formwork.admin import site

urlpatterns = [
    path("__formwork__/", include("django_formwork.urls")),
    path("admin/", site.urls),
]
