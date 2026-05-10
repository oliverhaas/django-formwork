from django.urls import path

from . import views

urlpatterns = [
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
    path("e2e/search/cities/", views.E2ECitySearchView.as_view(), name="e2e-city-search"),
    path("e2e/search/cities-many/", views.E2ECityManySearchView.as_view(), name="e2e-city-many-search"),
    path("e2e/search/languages/", views.E2ELanguageSearchView.as_view(), name="e2e-lang-search"),
    path("e2e/search/languages-icons/", views.E2ELanguageIconsSearchView.as_view(), name="e2e-lang-icons-search"),
    path("e2e/search/countries/", views.E2ECountrySearchView.as_view(), name="e2e-country-search"),
    path("e2e/search/failing/", views.E2EFailingSearchView.as_view(), name="e2e-failing-search"),
    path("e2e/validate/bio/", views.E2EBioValidateView.as_view(), name="e2e-validate-bio"),
]
