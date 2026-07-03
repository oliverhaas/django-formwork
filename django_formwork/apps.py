from django.apps import AppConfig


class FormworkConfig(AppConfig):
    name = "django_formwork"
    verbose_name = "Django Formwork"

    def ready(self) -> None:
        # Import every app's ``forms`` module so search-capable widgets register
        # their endpoints in all worker processes at startup, not lazily on
        # first render (see django_formwork.autodiscover).
        from django_formwork.autodiscover import autodiscover_forms

        autodiscover_forms()
