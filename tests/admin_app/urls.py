from django.templatetags.static import static
from django.urls import include, path

from django_formwork.admin import AdminSite, site

from .admin import CategoryAdmin, ItemAdmin
from .models import Category, Item


class SupportSite(AdminSite):
    site_header = "Support"

    def has_permission(self, request):
        return request.user.is_active and request.user.groups.filter(name="Support").exists()

    def has_model_permission(self, request, model, action, obj=None):
        return action in {"view", "change"}


support_site = SupportSite(name="support")
support_site.register(Item, ItemAdmin)
support_site.register(Category, CategoryAdmin)

for admin_site in (site, support_site):
    admin_site.scripts = ("htmx/htmx.min.js", "htmx/ext/hx-alpine-compat.min.js", "htmx/ext/hx-preload.min.js")
    admin_site.alpine_script = static("alpinejs/cdn.min.js")

urlpatterns = [
    path("__formwork__/", include("django_formwork.urls")),
    path("admin/", site.urls),
    path("support/", support_site.urls),
]
