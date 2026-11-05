from django.apps import AppConfig
from django.utils.module_loading import autodiscover_modules


class FormworkConfig(AppConfig):
    name = "django_formwork"
    verbose_name = "Django Formwork"

    def ready(self) -> None:
        from django_formwork import checks  # noqa: F401 (registers the system checks)

        # Registers every search key at startup, so a fresh worker does not 404.
        autodiscover_modules("forms")
