from django.urls import path
from views import BioValidateView, CitySearchView, LanguageSearchView, index

urlpatterns = [
    path("", index),
    path("search/cities/", CitySearchView.as_view(), name="city-search"),
    path("search/languages/", LanguageSearchView.as_view(), name="language-search"),
    path("validate/bio/", BioValidateView.as_view(), name="validate-bio"),
]
