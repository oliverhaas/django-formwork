"""The action every admin offers: delete the selected rows, after a confirmation page."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from django.contrib import messages
from django.contrib.admin.helpers import ACTION_CHECKBOX_NAME
from django.contrib.admin.utils import model_ngettext
from django.core.exceptions import PermissionDenied
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy

from django_formwork.admin.decorators import action
from django_formwork.admin.jinja import AdminTemplateResponse

if TYPE_CHECKING:
    from django.db.models import QuerySet
    from django.http import HttpRequest, HttpResponse

__all__ = ["delete_selected"]


@action(
    permissions=["delete"],
    description=gettext_lazy("Delete selected %(verbose_name_plural)s"),
    icon="trash",
    danger=True,
)
def delete_selected(modeladmin: Any, request: HttpRequest, queryset: QuerySet[Any]) -> HttpResponse | None:
    """Show what the deletion takes with it; delete after the page posts back ``post=yes``."""
    opts = modeladmin.model._meta
    deletable_objects, model_count, perms_needed, protected = modeladmin.get_deleted_objects(queryset, request)

    if request.POST.get("post") and not protected:
        if perms_needed:
            raise PermissionDenied
        count = len(queryset)
        if count:
            modeladmin.log_deletions(request, queryset)
            modeladmin.delete_queryset(request, queryset)
            modeladmin.message_user(
                request,
                _("Successfully deleted %(count)d %(items)s.") % {"count": count, "items": model_ngettext(opts, count)},
                messages.SUCCESS,
            )
        return None

    objects_name = model_ngettext(queryset)
    title = (
        _("Cannot delete %(name)s") % {"name": objects_name}
        if perms_needed or protected
        else _("Delete multiple objects")
    )
    context = {
        **modeladmin.admin_site.each_context(request),
        "title": title,
        "subtitle": None,
        "objects_name": str(objects_name),
        "deletable_objects": deletable_objects,
        "delete_confirmation_max_display": modeladmin.delete_confirmation_max_display,
        "model_count": list(dict(model_count).items()),
        "queryset": queryset,
        "perms_lacking": sorted(str(name) for name in perms_needed),
        "protected": protected,
        "opts": opts,
        "model_admin": modeladmin,
        "media": modeladmin.media,
        "select_across": request.POST.get("select_across") == "1",
        "selected": request.POST.getlist("_selected_action"),
        "action_name": request.POST.get("action", ""),
        "action_checkbox_name": ACTION_CHECKBOX_NAME,
    }
    request.current_app = modeladmin.admin_site.name
    return AdminTemplateResponse(
        request,
        modeladmin.delete_selected_confirmation_template
        or [
            f"formwork_admin/{opts.app_label}/{opts.model_name}/delete_selected_confirmation.html",
            f"formwork_admin/{opts.app_label}/delete_selected_confirmation.html",
            "formwork_admin/delete_selected_confirmation.html",
        ],
        context,
    )
