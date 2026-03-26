"""URL configuration for auto-registered formwork search endpoints.

Add to your project's ``urlpatterns``::

    from django.urls import include, path

    urlpatterns = [
        path("__formwork__/", include("django_formwork.urls")),
    ]
"""

from django.urls import path

from django_formwork.views import FormworkAutoSearchView

app_name = "formwork"

urlpatterns = [
    path("search/<str:key>/", FormworkAutoSearchView.as_view(), name="search"),
]
