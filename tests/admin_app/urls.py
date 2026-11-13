from django.urls import include, path

from django_formwork.admin import AdminSite, site

from .admin import CategoryAdmin, ItemAdmin
from .models import Category, Item


class SupportSite(AdminSite):
    site_header = "Support"

    def has_permission(self, request):
        return request.user.is_active and request.user.groups.filter(name="Support").exists()


support_site = SupportSite(name="support")
support_site.register(Item, ItemAdmin)
support_site.register(Category, CategoryAdmin)

urlpatterns = [
    path("__formwork__/", include("django_formwork.urls")),
    path("admin/", site.urls),
    path("support/", support_site.urls),
]
