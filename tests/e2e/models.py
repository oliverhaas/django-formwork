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


class UniqueCode(models.Model):
    """Single ``unique=True`` field, for batched formset-uniqueness tests."""

    code = models.CharField(max_length=50, unique=True)
    label = models.CharField(max_length=100, blank=True, default="")

    class Meta:
        app_label = "e2e"

    def __str__(self):
        return self.code or f"UniqueCode #{self.pk}"


class UniquePair(models.Model):
    """Classic ``unique_together``, for batched formset-uniqueness tests."""

    left = models.CharField(max_length=50)
    right = models.CharField(max_length=50)

    class Meta:
        app_label = "e2e"
        unique_together = [("left", "right")]

    def __str__(self):
        return f"{self.left}/{self.right}"


class ConstraintPair(models.Model):
    """Modern ``Meta.constraints`` ``UniqueConstraint``, for batched-uniqueness tests."""

    left = models.CharField(max_length=50)
    right = models.CharField(max_length=50)

    class Meta:
        app_label = "e2e"
        constraints = [models.UniqueConstraint(fields=["left", "right"], name="uq_constraint_pair")]

    def __str__(self):
        return f"{self.left}/{self.right}"


class UniqueAndCheckPair(models.Model):
    """A batchable ``UniqueConstraint`` next to a ``CheckConstraint``.

    The unique part is batched by the formset; the check stays on Django's
    per-form path. Used to prove the two coexist with stock parity.
    """

    left = models.CharField(max_length=50)
    right = models.CharField(max_length=50)

    class Meta:
        app_label = "e2e"
        constraints = [
            models.UniqueConstraint(fields=["left", "right"], name="uq_unique_and_check_pair"),
            models.CheckConstraint(condition=~models.Q(left="BAD"), name="ck_unique_and_check_pair_left"),
        ]

    def __str__(self):
        return f"{self.left}/{self.right}"


class ConditionalUnique(models.Model):
    """A conditional (partial) ``UniqueConstraint``.

    ``slug`` must be unique only among ``active=True`` rows. Conditional
    constraints are not batchable, so they stay on Django's per-form path; the
    test pins that parity holds.
    """

    slug = models.CharField(max_length=50)
    active = models.BooleanField(default=True)

    class Meta:
        app_label = "e2e"
        constraints = [
            models.UniqueConstraint(
                fields=["slug"],
                condition=models.Q(active=True),
                name="uq_conditional_unique_active_slug",
            ),
        ]

    def __str__(self):
        return self.slug or f"ConditionalUnique #{self.pk}"


class CustomMessageUnique(models.Model):
    """A field-based ``UniqueConstraint`` with a custom violation message.

    A custom message means Django uses ``get_violation_error_message`` rather
    than ``unique_error_message``, so this constraint is not batchable and stays
    on the per-form path. The test pins that the custom message is preserved.
    """

    code = models.CharField(max_length=50)

    class Meta:
        app_label = "e2e"
        constraints = [
            models.UniqueConstraint(
                fields=["code"],
                name="uq_custom_message_unique_code",
                violation_error_message="That code is already taken.",
            ),
        ]

    def __str__(self):
        return self.code or f"CustomMessageUnique #{self.pk}"


class Membership(models.Model):
    """Inline child, unique per ``(region, slug)``, for inline batched-uniqueness tests."""

    region = models.ForeignKey(Region, on_delete=models.CASCADE, related_name="memberships")
    slug = models.CharField(max_length=50)

    class Meta:
        app_label = "e2e"
        unique_together = [("region", "slug")]

    def __str__(self):
        return self.slug or f"Membership #{self.pk}"


class DatedCode(models.Model):
    """``unique_for_date``, for batched date-uniqueness tests."""

    slug = models.CharField(max_length=50, unique_for_date="published")
    published = models.DateField()

    class Meta:
        app_label = "e2e"

    def __str__(self):
        return self.slug or f"DatedCode #{self.pk}"


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
