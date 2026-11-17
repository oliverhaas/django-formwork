from django.conf import settings
from django.conf.urls.static import static
from django.urls import include, path

from django_formwork.admin import site

from . import views

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("tasks/", views.board, name="board"),
    path("tasks/add/", views.board_add, name="board_add"),
    path("tasks/move/", views.board_move, name="board_move"),
    path("tasks/new/", views.task_create, name="task_create"),
    path("tasks/<int:pk>/", views.task_detail, name="task_detail"),
    path("tasks/<int:pk>/edit/", views.task_edit, name="task_edit"),
    path("tasks/<int:pk>/comment/", views.task_comment, name="task_comment"),
    path("tasks/<int:pk>/done/", views.task_done, name="task_done"),
    path("tasks/<int:pk>/delete/", views.task_delete, name="task_delete"),
    path("wizard/", views.wizard, name="wizard"),
    path("wizard/confirm/", views.wizard_confirm, name="wizard_confirm"),
    path("settings/", views.settings_page, name="settings"),
    path("__formwork__/", include("django_formwork.urls")),
    path("admin/", site.urls),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
