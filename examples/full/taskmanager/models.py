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

    class Priority(models.TextChoices):
        LOW = "low", "Low"
        MEDIUM = "medium", "Medium"
        HIGH = "high", "High"
        CRITICAL = "critical", "Critical"

    class Status(models.TextChoices):
        TODO = "todo", "To Do"
        IN_PROGRESS = "in_progress", "In Progress"
        REVIEW = "review", "In Review"
        DONE = "done", "Done"

    # Status badges sit on a "lifecycle" ramp (neutral → primary → accent → success).
    # Priority badges sit on a "severity" ramp (info → secondary → warning → error).
    # No two cells in either column share a colour with the other axis, so a
    # row's status and priority badges always read as visually distinct.
    STATUS_COLORS: dict[str, str] = {
        Status.TODO: "neutral",
        Status.IN_PROGRESS: "primary",
        Status.REVIEW: "accent",
        Status.DONE: "success",
    }
    PRIORITY_COLORS: dict[str, str] = {
        Priority.LOW: "info",
        Priority.MEDIUM: "secondary",
        Priority.HIGH: "warning",
        Priority.CRITICAL: "error",
    }

    title = models.CharField(max_length=200)
    description = models.TextField(blank=True, default="")
    priority = models.CharField(max_length=20, choices=Priority.choices, default=Priority.MEDIUM)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.TODO)
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
    def assignee_initials(self) -> str:
        """First letters of first + last name, or first two letters of the
        single name. Empty for unassigned tasks (template handles that case).
        """
        parts = self.assignee.split()
        if not parts:
            return ""
        if len(parts) == 1:
            return parts[0][:2].upper()
        return (parts[0][:1] + parts[-1][:1]).upper()

    @property
    def status_color(self) -> str:
        return self.STATUS_COLORS.get(self.status, "neutral")

    @property
    def priority_color(self) -> str:
        return self.PRIORITY_COLORS.get(self.priority, "neutral")
