from django.apps import AppConfig
from django.utils.module_loading import autodiscover_modules


class FormworkConfig(AppConfig):
    name = "django_formwork"
    verbose_name = "Django Formwork"

    def ready(self) -> None:
        # Registers every search key at startup, so a fresh worker does not 404.
        autodiscover_modules("forms")
