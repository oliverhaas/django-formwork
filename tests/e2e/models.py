"""Django models for e2e test forms."""

from django.db import models


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
