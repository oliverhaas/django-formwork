"""Models for the task manager example."""

from django.core.validators import MaxValueValidator, MinValueValidator, RegexValidator
from django.db import models


class Tag(models.Model):
    """A label that can be attached to many tasks."""

    name = models.CharField(max_length=40, unique=True)
    color = models.CharField(max_length=20, default="primary")

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class Member(models.Model):
    """A person tasks can be assigned to. Stands in for a real user model
    so the assignee SearchSelect has actual rows to search over.
    """

    name = models.CharField(max_length=100)
    email = models.EmailField(unique=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name

    @property
    def initials(self) -> str:
        """First letters of first + last name, or first two letters of a
        single name.
        """
        parts = self.name.split()
        if not parts:
            return ""
        if len(parts) == 1:
            return parts[0][:2].upper()
        return (parts[0][:1] + parts[-1][:1]).upper()


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
    assignee = models.ForeignKey(
        Member,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="tasks",
    )
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


class Profile(models.Model):
    """Account settings of the demo's single local user.

    The example has no auth, so exactly one row exists, pinned to pk=1.
    ``load()`` is the only intended way to get hold of it. The password and
    2FA fields on the settings form are widget showcases and never stored.
    """

    # Demo country list; real projects supply their own (or use django-countries).
    class Country(models.TextChoices):
        US = "us", "🇺🇸 United States"
        GB = "gb", "🇬🇧 United Kingdom"
        DE = "de", "🇩🇪 Germany"
        FR = "fr", "🇫🇷 France"
        ES = "es", "🇪🇸 Spain"
        IT = "it", "🇮🇹 Italy"
        NL = "nl", "🇳🇱 Netherlands"
        SE = "se", "🇸🇪 Sweden"
        PL = "pl", "🇵🇱 Poland"
        CA = "ca", "🇨🇦 Canada"
        BR = "br", "🇧🇷 Brazil"
        MX = "mx", "🇲🇽 Mexico"
        JP = "jp", "🇯🇵 Japan"
        KR = "kr", "🇰🇷 South Korea"
        CN = "cn", "🇨🇳 China"
        IN = "in", "🇮🇳 India"
        AU = "au", "🇦🇺 Australia"
        ZA = "za", "🇿🇦 South Africa"
        NG = "ng", "🇳🇬 Nigeria"

    full_name = models.CharField(max_length=100)
    email = models.EmailField()
    phone = models.CharField(
        max_length=30,
        blank=True,
        default="",
        validators=[
            RegexValidator(
                r"^\+\d{1,4} [\d ()/-]{3,20}$",
                "Enter a dial code and number, e.g. '+49 171 1234567'.",
            ),
        ],
    )
    country = models.CharField(max_length=2, blank=True, default="", choices=Country.choices)
    avatar = models.ImageField(upload_to="avatars/", blank=True, null=True)
    favourite_food = models.CharField(max_length=50, blank=True, default="")
    satisfaction = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(1), MaxValueValidator(5)],
    )

    def __str__(self):
        return self.full_name

    def save(self, *args, **kwargs):
        self.full_clean()
        self.pk = 1
        super().save(*args, **kwargs)

    def clean(self):
        self.full_name = self.full_name.strip()

    @classmethod
    def load(cls) -> Profile:
        obj, _ = cls.objects.get_or_create(
            pk=1,
            defaults={"full_name": "Devon Vega", "email": "devon@example.com"},
        )
        return obj
