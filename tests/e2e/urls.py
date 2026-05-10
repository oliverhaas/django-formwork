from django.urls import include, path

from . import views

urlpatterns = [
    path("__formwork__/", include("django_formwork.urls")),
    path("", views.index_view),
    path("basic/", views.basic_view),
    path("elements/", views.elements_view),
    path("simple/", views.simple_view),
    path("builtin/", views.builtin_view),
    path("search-select/", views.search_select_view),
    path("multi-select/", views.multi_select_view),
    path("combobox/", views.combobox_view),
    path("uploads/", views.uploads_view),
    path("textarea/", views.textarea_view),
    path("new-widgets/", views.new_widgets_view),
    path("icon-modifiers/", views.icon_modifiers_view),
    path("complex/", views.complex_view),
    path("autosave/", views.autosave_view),
    path("e2e/validate/bio/", views.E2EBioValidateView.as_view(), name="e2e-validate-bio"),
]
