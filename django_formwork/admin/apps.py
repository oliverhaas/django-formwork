from django.apps import AppConfig


class FormworkAdminConfig(AppConfig):
    name = "django_formwork.admin"
    default_auto_field = "django.db.models.BigAutoField"
    label = "formwork_admin"
    verbose_name = "Formwork admin"

    def ready(self) -> None:
        from django_formwork.admin import autodiscover, checks  # noqa: F401 (registers the system checks)

        autodiscover()
