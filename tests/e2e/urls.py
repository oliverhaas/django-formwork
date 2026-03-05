from django.urls import path

from . import views

urlpatterns = [
    path("", views.index),
    path("e2e/search/cities/", views.E2ECitySearchView.as_view(), name="e2e-city-search"),
    path("e2e/search/languages/", views.E2ELanguageSearchView.as_view(), name="e2e-lang-search"),
    path("e2e/validate/bio/", views.E2EBioValidateView.as_view(), name="e2e-validate-bio"),
]
