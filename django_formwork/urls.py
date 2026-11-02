"""URL configuration for the formwork search endpoint.

Add to your project's ``urlpatterns``::

    from django.urls import include, path

    urlpatterns = [
        path("__formwork__/", include("django_formwork.urls")),
    ]
"""

from django.urls import path

from django_formwork.views import FormworkSearchView

app_name = "formwork"

urlpatterns = [
    path("search/<str:key>/", FormworkSearchView.as_view(), name="search"),
]
