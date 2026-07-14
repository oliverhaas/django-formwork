from django.conf import settings
from django.conf.urls.static import static
from django.urls import include, path

from . import views

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("tasks/", views.task_list, name="task_list"),
    path("tasks/new/", views.task_create, name="task_create"),
    path("tasks/<int:pk>/edit/", views.task_edit, name="task_edit"),
    path("tasks/<int:pk>/delete/", views.task_delete, name="task_delete"),
    path("tasks/row/", views.TaskRowSave.as_view(), name="task_row_save"),
    path("wizard/", views.wizard, name="wizard"),
    path("wizard/confirm/", views.wizard_confirm, name="wizard_confirm"),
    path("settings/", views.settings_page, name="settings"),
    path("__formwork__/", include("django_formwork.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
