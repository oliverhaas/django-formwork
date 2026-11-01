from django.urls import include, path

from . import views

urlpatterns = [
    path("__formwork__/", include("django_formwork.urls")),
    path("", views.index_view),
    path("basic/", views.basic_view),
    path("elements/", views.elements_view),
    path("simple/", views.simple_view),
    path("inline-errors/", views.inline_errors_view),
    path("tight/", views.tight_view),
    path("builtin/", views.builtin_view),
    path("select/", views.select_view),
    path("select-multiple/", views.select_multiple_view),
    path("combobox/", views.combobox_view),
    path("dropdowns/", views.dropdowns_view),
    path("read-only/", views.read_only_view),
    path("uploads/", views.uploads_view),
    path("textarea/", views.textarea_view),
    path("new-widgets/", views.new_widgets_view),
    path("icon-modifiers/", views.icon_modifiers_view),
    path("complex/", views.complex_view),
    path("autosave/", views.autosave_view),
    path("autosave-dropdowns/", views.autosave_dropdowns_view),
    path("sections/", views.sections_view),
    path("translated/", views.translated_view),
    path("e2e/validate/bio/", views.E2EBioValidateView.as_view(), name="e2e-validate-bio"),
]
