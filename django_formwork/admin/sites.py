"""``AdminSite``: the registry of model admins, the URLs and the site-wide pages."""

from __future__ import annotations

import re
import zlib
from contextlib import suppress
from functools import update_wrapper
from pathlib import PurePosixPath
from typing import TYPE_CHECKING, Any, cast
from weakref import WeakValueDictionary

from django.apps import apps
from django.conf import settings
from django.contrib import messages
from django.contrib.admin.exceptions import AlreadyRegistered, NotRegistered
from django.contrib.admin.utils import quote
from django.contrib.auth import REDIRECT_FIELD_NAME
from django.contrib.auth.forms import AuthenticationForm, PasswordChangeForm
from django.core.exceptions import ImproperlyConfigured, ValidationError
from django.db.models.base import ModelBase
from django.http import (
    FileResponse,
    Http404,
    HttpResponse,
    HttpResponseBase,
    HttpResponsePermanentRedirect,
    HttpResponseRedirect,
)
from django.shortcuts import get_object_or_404
from django.urls import NoReverseMatch, Resolver404, include, path, re_path, resolve, reverse
from django.utils.functional import LazyObject, empty
from django.utils.module_loading import import_string
from django.utils.text import capfirst
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy
from django.views.decorators.cache import never_cache
from django.views.decorators.common import no_append_slash
from django.views.decorators.csrf import csrf_protect

from django_formwork.admin.actions import delete_selected
from django_formwork.admin.history import DELETE, History, ModelHistory
from django_formwork.admin.jinja import AdminTemplateResponse
from django_formwork.admin.options import ModelAdmin
from django_formwork.renderers import FormworkRenderer

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable, Sequence

    from django.db import models
    from django.http import HttpRequest
    from django.urls import URLPattern, URLResolver

    from django_formwork.admin.models import ExportJob

__all__ = [
    "AdminAuthenticationForm",
    "AdminPasswordChangeForm",
    "AdminSite",
    "AlreadyRegistered",
    "DefaultAdminSite",
    "NotRegistered",
    "get_site",
    "site",
]

_sites: WeakValueDictionary[str, AdminSite] = WeakValueDictionary()


def get_site(name: str) -> AdminSite | None:
    """The site registered under ``name``, None for an unknown name."""
    lazy_site = cast("DefaultAdminSite", site)
    if lazy_site._wrapped is empty:
        lazy_site._setup()
    return _sites.get(name)


class AdminAuthenticationForm(AuthenticationForm):
    """Django's login form, for staff only, drawn with formwork's field templates."""

    default_renderer = FormworkRenderer
    error_messages = {  # noqa: RUF012 (Django reads it per instance, as AuthenticationForm does)
        **AuthenticationForm.error_messages,
        "invalid_login": gettext_lazy(
            "Please enter the correct %(username)s and password for a staff account. "
            "Note that both fields may be case-sensitive.",
        ),
    }
    required_css_class = "required"

    def confirm_login_allowed(self, user: Any) -> None:
        super().confirm_login_allowed(user)
        if not user.is_staff:
            raise ValidationError(
                self.error_messages["invalid_login"],
                code="invalid_login",
                params={"username": self.username_field.verbose_name},
            )


class AdminPasswordChangeForm(PasswordChangeForm):
    default_renderer = FormworkRenderer


#: Lucide outlines for models without an icon, told apart at the size of the navigation.
PLACEHOLDER_ICONS = ("circle", "triangle", "square", "diamond", "pentagon", "hexagon", "star")


class AdminSite:
    """A set of model admins under one URL prefix, with its own login and dashboard."""

    site_title = gettext_lazy("Formwork admin")
    site_header = gettext_lazy("Administration")
    index_title = gettext_lazy("Dashboard")
    site_url: str | None = "/"
    empty_value_display = "-"
    enable_nav_sidebar = True
    final_catch_all_view = True

    login_form: type[AuthenticationForm] | None = None
    password_change_form: type[PasswordChangeForm] = AdminPasswordChangeForm
    index_template: str | None = None
    app_index_template: str | None = None
    login_template: str | None = None
    logout_template: str | None = None
    password_change_template: str | None = None
    password_change_done_template: str | None = None

    #: Static paths of the compiled CSS: formwork.css and formwork_admin/admin.css built by your Tailwind step.
    stylesheets: Sequence[str] = ("formwork/formwork-dist.css",)
    #: Scripts loaded before formwork's own; htmx, its Alpine bridge and Alpine itself.
    scripts: Sequence[str] = (
        "https://unpkg.com/htmx.org@4.0.1/dist/htmx.min.js",
        "https://unpkg.com/htmx.org@4.0.1/dist/ext/hx-alpine-compat.min.js",
    )
    alpine_script = "https://cdn.jsdelivr.net/npm/alpinejs@3.15.0/dist/cdn.min.js"
    #: DaisyUI themes the theme switch offers; the first is the default.
    themes: Sequence[str] = ("light", "dark")
    #: Where the history of changes goes: the admin's own table, or ``PghistoryHistory()`` for pghistory.
    history: History = ModelHistory()

    def __init__(self, name: str = "admin") -> None:
        self._registry: dict[type[models.Model], ModelAdmin] = {}
        self.name = name
        self._actions: dict[str, Callable[..., Any]] = {"delete_selected": delete_selected}
        self._global_actions = self._actions.copy()
        _sites[name] = self

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(name={self.name!r})"

    # Registry

    def register(
        self,
        model_or_iterable: type[models.Model] | Iterable[type[models.Model]],
        admin_class: type[ModelAdmin] | None = None,
        **options: Any,
    ) -> None:
        admin_class = admin_class or ModelAdmin
        models_: Iterable[type[models.Model]] = (  # ty: ignore[invalid-assignment]
            [model_or_iterable] if isinstance(model_or_iterable, ModelBase) else model_or_iterable
        )
        for model in models_:
            if model._meta.abstract:
                msg = f"The model {model.__name__} is abstract, so it cannot be registered with admin."
                raise ImproperlyConfigured(msg)
            if model._meta.is_composite_pk:
                msg = f"The model {model.__name__} has a composite primary key, so it cannot be registered with admin."
                raise ImproperlyConfigured(msg)
            if self.is_registered(model):
                registered = self._registry[model]
                msg = f"The model {model.__name__} is already registered with '{registered}'."
                raise AlreadyRegistered(msg)
            if not model._meta.swapped:
                if options:
                    options["__module__"] = __name__
                    admin_class = type(f"{model.__name__}Admin", (admin_class,), options)
                self._registry[model] = admin_class(model, self)

    def unregister(self, model_or_iterable: type[models.Model] | Iterable[type[models.Model]]) -> None:
        models_: Iterable[type[models.Model]] = (  # ty: ignore[invalid-assignment]
            [model_or_iterable] if isinstance(model_or_iterable, ModelBase) else model_or_iterable
        )
        for model in models_:
            if not self.is_registered(model):
                msg = f"The model {model.__name__} is not registered"
                raise NotRegistered(msg)
            del self._registry[model]

    def is_registered(self, model: type[models.Model]) -> bool:
        return model in self._registry

    def get_model_admin(self, model: type[models.Model]) -> ModelAdmin:
        try:
            return self._registry[model]
        except KeyError:
            msg = f"The model {model.__name__} is not registered."
            raise NotRegistered(msg) from None

    def get_model_admin_or_none(self, model: type[models.Model]) -> ModelAdmin | None:
        return self._registry.get(model)

    def placeholder_icon(self, model: type[models.Model]) -> str:
        """A shape for a model without an icon, hashed from its label, so a restart keeps it.

        The models of one app take different shapes while there are enough to go round.
        """
        shapes = PLACEHOLDER_ICONS
        label = model._meta.label_lower
        siblings = sorted(
            other._meta.label_lower
            for other, model_admin in self._registry.items()
            if other._meta.app_label == model._meta.app_label and not model_admin.icon
        )
        if label not in siblings:
            return shapes[zlib.crc32(label.encode()) % len(shapes)]
        picks: dict[str, str] = {}
        taken: set[int] = set()
        for sibling in siblings:
            if len(taken) == len(shapes):
                taken.clear()
            index = zlib.crc32(sibling.encode()) % len(shapes)
            while index in taken:
                index = (index + 1) % len(shapes)
            taken.add(index)
            picks[sibling] = shapes[index]
        return picks[label]

    def is_searchable(self, model: type[models.Model]) -> bool:
        """Whether a relation to ``model`` pages its rows from the server."""
        model_admin = self._registry.get(model)
        return model_admin is not None and bool(model_admin.search_fields)

    # Actions

    def add_action(self, action: Callable[..., Any], name: str | None = None) -> None:
        name = name or action.__name__  # ty: ignore[unresolved-attribute]
        self._actions[name] = action
        self._global_actions[name] = action

    def disable_action(self, name: str) -> None:
        del self._actions[name]

    def get_action(self, name: str) -> Callable[..., Any]:
        return self._global_actions[name]

    @property
    def actions(self) -> Iterable[tuple[str, Callable[..., Any]]]:
        return self._actions.items()

    # Access

    def has_permission(self, request: HttpRequest) -> bool:
        return request.user.is_active and request.user.is_staff  # ty: ignore[unresolved-attribute]

    def admin_view(
        self, view: Callable[..., HttpResponseBase], cacheable: bool = False
    ) -> Callable[..., HttpResponseBase]:
        """``view`` behind the site's permission check, with CSRF protection and, unless ``cacheable``, no caching."""

        def inner(request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponseBase:
            if not self.has_permission(request):
                if request.path == reverse(f"{self.name}:logout", current_app=self.name):
                    return HttpResponseRedirect(reverse(f"{self.name}:index", current_app=self.name))
                from django.contrib.auth.views import redirect_to_login

                login_url = reverse(f"{self.name}:login", current_app=self.name)
                if request.headers.get("HX-Request") == "true":
                    # A swapped-in login page would land inside the list; send the browser there instead.
                    response = HttpResponse(status=204)
                    response["HX-Redirect"] = f"{login_url}?{REDIRECT_FIELD_NAME}={request.get_full_path()}"
                    return response
                return redirect_to_login(request.get_full_path(), login_url)
            with self.history.context(request):
                return view(request, *args, **kwargs)

        if not cacheable:
            inner = never_cache(inner)
        if not getattr(view, "csrf_exempt", False):
            inner = csrf_protect(inner)  # ty: ignore[invalid-assignment, invalid-argument-type]
        return update_wrapper(inner, view)

    # URLs

    def get_urls(self) -> list[URLPattern | URLResolver]:
        def wrap(view: Callable[..., HttpResponseBase], cacheable: bool = False) -> Callable[..., HttpResponseBase]:
            def wrapper(*args: Any, **kwargs: Any) -> HttpResponseBase:
                return self.admin_view(view, cacheable)(*args, **kwargs)

            wrapper.admin_site = self  # type: ignore[attr-defined]  # ty: ignore[unresolved-attribute]
            return update_wrapper(wrapper, view)

        urlpatterns: list[URLPattern | URLResolver] = [
            path("", wrap(self.index), name="index"),
            path("login/", self.login, name="login"),
            path("logout/", wrap(self.logout), name="logout"),
            path("password_change/", wrap(self.password_change, cacheable=True), name="password_change"),
            path("password_change/done/", wrap(self.password_change_done, cacheable=True), name="password_change_done"),
            path("r/<int:content_type_id>/<path:object_id>/", wrap(self.view_on_site), name="view_on_site"),
            path("exports/", wrap(self.exports_view), name="exports"),
            path("exports/<int:pk>/download/", wrap(self.export_download), name="export_download"),
        ]
        app_labels = set()
        for model, model_admin in self._registry.items():
            urlpatterns.append(path(f"{model._meta.app_label}/{model._meta.model_name}/", include(model_admin.urls)))
            app_labels.add(model._meta.app_label)
        if app_labels:
            pattern = r"^(?P<app_label>" + "|".join(map(re.escape, sorted(app_labels))) + ")/$"
            urlpatterns.append(re_path(pattern, wrap(self.app_index), name="app_list"))
        if self.final_catch_all_view:
            urlpatterns.append(re_path(r"(?P<url>.*)$", wrap(self.catch_all_view)))
        return urlpatterns

    @property
    def urls(self) -> tuple[list[URLPattern | URLResolver], str, str]:
        return self.get_urls(), "formwork_admin", self.name

    def reverse(self, name: str, *args: Any, **kwargs: Any) -> str:
        return reverse(f"{self.name}:{name}", args=args or None, kwargs=kwargs or None, current_app=self.name)

    # Context

    def each_context(self, request: HttpRequest) -> dict[str, Any]:
        """What every page of the site reads: titles, the navigation and the messages."""
        script_name = request.META.get("SCRIPT_NAME", "")
        site_url = script_name if self.site_url == "/" and script_name else self.site_url
        return {
            "site": self,
            "site_title": self.site_title,
            "site_header": self.site_header,
            "site_url": site_url,
            "has_permission": self.has_permission(request),
            "available_apps": self.get_app_list(request),
            "is_nav_sidebar_enabled": self.enable_nav_sidebar,
            "is_popup": False,
            "stylesheets": self.stylesheets,
            "scripts": self.scripts,
            "alpine_script": self.alpine_script,
            "themes": self.themes,
            "messages": messages.get_messages(request),
            # htmx morphs the page content as one piece; htmx 4 names the target as ``tag#id``.
            "content_only": request.headers.get("HX-Request") == "true"
            and request.headers.get("HX-Target", "").rpartition("#")[2] == "content",
        }

    def _build_app_dict(self, request: HttpRequest, label: str | None = None) -> dict[str, dict[str, Any]]:
        registry = {m: a for m, a in self._registry.items() if m._meta.app_label == label} if label else self._registry
        app_dict: dict[str, dict[str, Any]] = {}
        for model, model_admin in registry.items():
            app_label = model._meta.app_label
            if not model_admin.has_module_permission(request):
                continue
            perms = model_admin.get_model_perms(request)
            if True not in perms.values():
                continue
            model_dict: dict[str, Any] = {
                "model": model,
                "name": capfirst(model._meta.verbose_name_plural),
                "object_name": model._meta.object_name,
                "icon": model_admin.get_icon(),
                "perms": perms,
                "admin_url": None,
                "add_url": None,
                "view_only": False,
            }
            if perms.get("change") or perms.get("view"):
                model_dict["view_only"] = not perms.get("change")
                with suppress(NoReverseMatch):
                    model_dict["admin_url"] = reverse(model_admin.url_name("changelist"), current_app=self.name)
            if perms.get("add"):
                with suppress(NoReverseMatch):
                    model_dict["add_url"] = reverse(model_admin.url_name("add"), current_app=self.name)
            if app_label not in app_dict:
                app_dict[app_label] = {
                    "name": apps.get_app_config(app_label).verbose_name,
                    "app_label": app_label,
                    "app_url": reverse(f"{self.name}:app_list", kwargs={"app_label": app_label}, current_app=self.name),
                    "has_module_perms": True,
                    "models": [],
                }
            app_dict[app_label]["models"].append(model_dict)
        return app_dict

    def get_app_list(self, request: HttpRequest, app_label: str | None = None) -> list[dict[str, Any]]:
        """The apps and their models the user can see, sorted by name."""
        cache_key = f"_formwork_admin_app_list_{self.name}_{app_label}"
        cached = getattr(request, cache_key, None)
        if cached is not None:
            return cached
        app_list = sorted(self._build_app_dict(request, app_label).values(), key=lambda app: str(app["name"]).lower())
        for app in app_list:
            app["models"].sort(key=lambda model: str(model["name"]))
        setattr(request, cache_key, app_list)
        return app_list

    def render(self, request: HttpRequest, templates: Any, context: dict[str, Any]) -> HttpResponse:
        request.current_app = self.name
        return AdminTemplateResponse(request, templates, context)

    # Views

    def index(self, request: HttpRequest, extra_context: dict[str, Any] | None = None) -> HttpResponse:
        context = {
            **self.each_context(request),
            "title": self.index_title,
            "subtitle": None,
            "app_list": self.get_app_list(request),
            "recent_actions": self._recent_actions(request),
            **(extra_context or {}),
        }
        return self.render(request, self.index_template or "formwork_admin/index.html", context)

    def _recent_actions(self, request: HttpRequest) -> list[dict[str, Any]]:
        """The user's last ten changes, each linked to its object on this site while it exists."""
        actions = []
        for entry in self.history.recent(request, 10):
            link = ""
            content_type = entry.content_type
            if entry.action != DELETE and content_type is not None:
                with suppress(NoReverseMatch):
                    link = reverse(
                        f"{self.name}:{content_type.app_label}_{content_type.model}_change",
                        args=(quote(entry.object_id),),
                        current_app=self.name,
                    )
            actions.append({"entry": entry, "kind": entry.action, "url": link})
        return actions

    def app_index(
        self, request: HttpRequest, app_label: str, extra_context: dict[str, Any] | None = None
    ) -> HttpResponse:
        app_list = self.get_app_list(request, app_label)
        if not app_list:
            msg = "The requested admin page does not exist."
            raise Http404(msg)
        context = {
            **self.each_context(request),
            "title": _("%(app)s administration") % {"app": app_list[0]["name"]},
            "subtitle": None,
            "app_list": app_list,
            "app_label": app_label,
            **(extra_context or {}),
        }
        return self.render(
            request,
            self.app_index_template or [f"formwork_admin/{app_label}/app_index.html", "formwork_admin/app_index.html"],
            context,
        )

    @no_append_slash
    def catch_all_view(self, request: HttpRequest, url: str) -> HttpResponse:
        """Any other URL under the site: the same URL with a slash when that one exists, else 404.

        It sits behind the login check, so a signed-out visitor cannot tell which models are registered.
        """
        if settings.APPEND_SLASH and not url.endswith("/"):
            try:
                match = resolve(f"{request.path_info}/", getattr(request, "urlconf", None))
            except Resolver404:
                match = None
            if match is not None and getattr(match.func, "should_append_slash", True):
                return HttpResponsePermanentRedirect(request.get_full_path(force_append_slash=True))
        raise Http404

    def login(self, request: HttpRequest, extra_context: dict[str, Any] | None = None) -> HttpResponse:
        if request.method == "GET" and self.has_permission(request):
            return HttpResponseRedirect(reverse(f"{self.name}:index", current_app=self.name))
        from django.contrib.auth.views import LoginView

        context = {
            **self.each_context(request),
            "title": _("Log in"),
            "subtitle": None,
            "app_path": request.get_full_path(),
            "username": request.user.get_username(),
            "password_reset_url": self._password_reset_url(),
        }
        if REDIRECT_FIELD_NAME not in request.GET and REDIRECT_FIELD_NAME not in request.POST:
            context[REDIRECT_FIELD_NAME] = reverse(f"{self.name}:index", current_app=self.name)
        context.update(extra_context or {})
        request.current_app = self.name
        view = LoginView.as_view(
            extra_context=context,
            authentication_form=self.login_form or AdminAuthenticationForm,
            template_name=self.login_template or "formwork_admin/login.html",
            response_class=AdminTemplateResponse,
        )
        return cast("HttpResponse", view(request))

    @staticmethod
    def _password_reset_url() -> str:
        """The project's ``admin_password_reset`` page, which Django's admin links from its login too."""
        try:
            return reverse("admin_password_reset")
        except NoReverseMatch:
            return ""

    def logout(self, request: HttpRequest, extra_context: dict[str, Any] | None = None) -> HttpResponse:
        from django.contrib.auth.views import LogoutView

        request.current_app = self.name
        view = LogoutView.as_view(
            extra_context={
                **self.each_context(request),
                "title": _("Logged out"),
                "subtitle": None,
                **(extra_context or {}),
            },
            template_name=self.logout_template or "formwork_admin/logged_out.html",
            response_class=AdminTemplateResponse,
        )
        return view(request)

    def password_change(self, request: HttpRequest, extra_context: dict[str, Any] | None = None) -> HttpResponse:
        from django.contrib.auth.views import PasswordChangeView

        request.current_app = self.name
        view = PasswordChangeView.as_view(
            form_class=self.password_change_form,
            success_url=reverse(f"{self.name}:password_change_done", current_app=self.name),
            extra_context={**self.each_context(request), "subtitle": None, **(extra_context or {})},
            template_name=self.password_change_template or "formwork_admin/password_change_form.html",
            response_class=AdminTemplateResponse,
        )
        return cast("HttpResponse", view(request))

    def password_change_done(self, request: HttpRequest, extra_context: dict[str, Any] | None = None) -> HttpResponse:
        from django.contrib.auth.views import PasswordChangeDoneView

        request.current_app = self.name
        view = PasswordChangeDoneView.as_view(
            extra_context={**self.each_context(request), "subtitle": None, **(extra_context or {})},
            template_name=self.password_change_done_template or "formwork_admin/password_change_done.html",
            response_class=AdminTemplateResponse,
        )
        return view(request)

    def view_on_site(self, request: HttpRequest, content_type_id: int, object_id: str) -> HttpResponse:
        from django.contrib.contenttypes.views import shortcut

        return shortcut(request, content_type_id, object_id)

    # Exports

    def enqueue_export(self, job: ExportJob) -> None:
        """Hand an export job to the task queue: Django's tasks by default.

        Override it to use another queue, such as a Celery task that calls ``run_export_job(job_id)``.
        """
        from django_formwork.admin.tasks import run_export

        run_export.enqueue(job.pk)

    def exports_view(self, request: HttpRequest, extra_context: dict[str, Any] | None = None) -> HttpResponse:
        """The user's recent exports, refreshed while one still runs."""
        from django_formwork.admin.models import ExportJob

        rows: list[dict[str, Any]] = []
        for job in ExportJob.objects.filter(user_id=cast("int | str", request.user.pk)).select_related("content_type")[
            :50
        ]:
            model = job.content_type.model_class()
            model_admin = self.get_model_admin_or_none(model) if model is not None else None
            changelist_url = ""
            if model_admin is not None and model_admin.has_view_or_change_permission(request):
                changelist_url = model_admin.changelist_url(request) + (f"?{job.query}" if job.query else "")
            name = capfirst(model._meta.verbose_name_plural) if model is not None else str(job.content_type)
            rows.append({"job": job, "name": name, "changelist_url": changelist_url})
        context = {
            **self.each_context(request),
            "title": _("Exports"),
            "subtitle": None,
            "rows": rows,
            "polling": any(not row["job"].is_finished for row in rows),
            **(extra_context or {}),
        }
        templates = ["formwork_admin/exports.html"]
        if request.headers.get("HX-Request") == "true" and request.headers.get("HX-Target", "").endswith("#exports"):
            templates = ["formwork_admin/export_list.html"]
        return self.render(request, templates, context)

    def export_download(self, request: HttpRequest, pk: int) -> FileResponse:
        """The file of one of the user's finished exports."""
        from django_formwork.admin.models import ExportJob

        job = get_object_or_404(ExportJob, pk=pk, user=request.user, status=ExportJob.Status.DONE)
        if not job.file:
            raise Http404
        filename = PurePosixPath(job.file.name or "").name.removeprefix(f"{job.pk}-")
        return FileResponse(job.file.open("rb"), as_attachment=True, filename=filename)


class DefaultAdminSite(LazyObject):
    """The site ``FORMWORK_ADMIN_SITE`` names, built on first use."""

    def _setup(self) -> None:
        site_class = import_string(getattr(settings, "FORMWORK_ADMIN_SITE", "django_formwork.admin.sites.AdminSite"))
        self._wrapped = site_class()

    def __repr__(self) -> str:
        return repr(self._wrapped)


site = cast("AdminSite", DefaultAdminSite())
