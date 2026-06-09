"""Models for the cookbook example."""

from django.core.exceptions import ValidationError
from django.db import models

from django_formwork.models import FormworkModel

PRIORITY_CHOICES = [
    ("low", "Low"),
    ("medium", "Medium"),
    ("high", "High"),
]


class Person(models.Model):
    """Someone a ticket can be assigned to."""

    name = models.CharField(max_length=100)
    email = models.EmailField()

    def __str__(self):
        return self.name


def reject_legacy_title(value: str) -> None:
    """Title validator used to show validate_dirty_only skipping legacy data."""
    if value == "LEGACY":
        raise ValidationError("Legacy titles are no longer allowed.")


class Ticket(FormworkModel):
    """A ticket. Inherits FormworkModel for dirty-field tracking."""

    title = models.CharField(max_length=200, validators=[reject_legacy_title])
    assignee = models.ForeignKey(Person, null=True, blank=True, on_delete=models.SET_NULL)
    priority = models.CharField(max_length=10, choices=PRIORITY_CHOICES, default="low")
    description = models.TextField(blank=True, default="")
    screenshot = models.ImageField(upload_to="screenshots/", blank=True)

    def __str__(self):
        return self.title or f"Ticket #{self.pk}"
