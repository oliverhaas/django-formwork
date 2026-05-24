"""Models for the task manager example."""

from django.db import models


class Tag(models.Model):
    """A label that can be attached to many tasks."""

    name = models.CharField(max_length=40, unique=True)
    color = models.CharField(max_length=20, default="primary")

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class Task(models.Model):
    """A task with priority, status, assignee, tags, and attachments."""

    PRIORITY_CHOICES = [
        ("low", "Low"),
        ("medium", "Medium"),
        ("high", "High"),
        ("critical", "Critical"),
    ]
    STATUS_CHOICES = [
        ("todo", "To Do"),
        ("in_progress", "In Progress"),
        ("review", "In Review"),
        ("done", "Done"),
    ]
    # Status badges sit on a "lifecycle" ramp (neutral → primary → accent → success).
    # Priority badges sit on a "severity" ramp (info → secondary → warning → error).
    # No two cells in either column share a colour with the other axis, so a
    # row's status and priority badges always read as visually distinct.
    STATUS_COLORS = {
        "todo": "neutral",
        "in_progress": "primary",
        "review": "accent",
        "done": "success",
    }
    PRIORITY_COLORS = {
        "low": "info",
        "medium": "secondary",
        "high": "warning",
        "critical": "error",
    }

    title = models.CharField(max_length=200)
    description = models.TextField(blank=True, default="")
    priority = models.CharField(max_length=20, choices=PRIORITY_CHOICES, default="medium")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="todo")
    assignee = models.CharField(max_length=100, blank=True, default="")
    tags = models.ManyToManyField(Tag, blank=True, related_name="tasks")
    due_date = models.DateField(null=True, blank=True)
    cover_image = models.ImageField(upload_to="covers/", blank=True, null=True)
    attachment = models.FileField(upload_to="attachments/", blank=True, null=True)
    rating = models.IntegerField(null=True, blank=True, help_text="Quality rating after completion")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]

    def __str__(self):
        return self.title

    @property
    def status_color(self) -> str:
        return self.STATUS_COLORS.get(self.status, "neutral")

    @property
    def priority_color(self) -> str:
        return self.PRIORITY_COLORS.get(self.priority, "neutral")

    @property
    def status_label(self) -> str:
        return dict(self.STATUS_CHOICES).get(self.status, self.status)

    @property
    def priority_label(self) -> str:
        return dict(self.PRIORITY_CHOICES).get(self.priority, self.priority)
