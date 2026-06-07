from django.urls import include, path

from . import views

urlpatterns = [
    path("", views.contact_view, name="contact"),
    path("cookbook/1/", views.cookbook_step1, name="ck-step1"),
    path("cookbook/2/", views.cookbook_step2, name="ck-step2"),
    path("cookbook/3/", views.cookbook_step3, name="ck-step3"),
    path("cookbook/4/", views.cookbook_step4, name="ck-step4"),
    path("__formwork__/", include("django_formwork.urls")),
]
