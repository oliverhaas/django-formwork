"""Django models for e2e test forms."""

from django.core.exceptions import ValidationError
from django.db import models

from django_formwork.models import FormworkModel


def _reject_legacy_bad(value: str) -> None:
    """Test validator used by ``DirtyTrackedData`` to demonstrate dirty-only skipping."""
    if value == "LEGACY_BAD":
        raise ValidationError("Legacy bad value not allowed.")


class BasicFormData(models.Model):
    """Stores a single BasicForm submission."""

    name = models.CharField(max_length=255)
    email = models.EmailField()
    message = models.TextField(blank=True, default="")
    priority = models.CharField(max_length=20, default="low")
    notify = models.CharField(max_length=20, default="email")
    agree = models.BooleanField(default=False)
    attachment = models.FileField(upload_to="attachments/", blank=True)

    class Meta:
        app_label = "e2e"

    def __str__(self):
        return self.name or f"BasicFormData #{self.pk}"


class Region(models.Model):
    """Geographic region for grouping cities."""

    name = models.CharField(max_length=100)

    class Meta:
        app_label = "e2e"
        ordering = ["name"]

    def __str__(self):
        return self.name


class City(models.Model):
    """City belonging to a region."""

    name = models.CharField(max_length=100)
    region = models.ForeignKey(Region, on_delete=models.CASCADE, related_name="cities")

    class Meta:
        app_label = "e2e"
        ordering = ["name"]

    def __str__(self):
        return self.name


class AutoSaveFormData(models.Model):
    """Stores auto-saved form data (partial saves allowed)."""

    name = models.CharField(max_length=255, blank=True, default="")
    email = models.EmailField(blank=True, default="")
    message = models.TextField(blank=True, default="")
    priority = models.CharField(max_length=20, default="low")
    notify = models.CharField(max_length=20, default="email")
    agree = models.BooleanField(default=False)
    attachment = models.FileField(upload_to="attachments/", blank=True)

    class Meta:
        app_label = "e2e"

    def __str__(self):
        return self.name or f"AutoSaveFormData #{self.pk}"


class DirtyTrackedData(FormworkModel):
    """Inherits :class:`FormworkModel` for tests of ``validate_dirty_only``.

    ``name`` has a validator that fails on ``"LEGACY_BAD"`` so tests can
    seed a row with a value that would normally fail validation, then
    submit a form that leaves the field unchanged.
    """

    name = models.CharField(max_length=255, validators=[_reject_legacy_bad])
    email = models.EmailField()
    note = models.TextField(blank=True, default="")
    region = models.ForeignKey("Region", null=True, blank=True, on_delete=models.SET_NULL)

    class Meta:
        app_label = "e2e"
        constraints = [
            models.CheckConstraint(condition=~models.Q(name="LEGACY_BAD_CONSTRAINT"), name="name_not_legacy_bad"),
        ]

    def __str__(self):
        return self.name or f"DirtyTrackedData #{self.pk}"

    def clean(self):
        # Cross-field rule, guarded with fields_dirty() so it only fires
        # when one of the referenced fields was actually changed.
        if self.fields_dirty("name", "email") and self.name == self.email:
            raise ValidationError({"name": "Name must differ from email."})
