"""Models for the pghistory tests, installed by ``settings.postgres`` only."""

import pghistory
from django.conf import settings
from django.db import models


@pghistory.track()
class Draft(models.Model):
    class Status(models.TextChoices):
        OPEN = "open", "Open"
        DONE = "done", "Done"

    title = models.CharField(max_length=100)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.OPEN)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )

    def __str__(self):
        return self.title


class Plain(models.Model):
    name = models.CharField(max_length=100)

    def __str__(self):
        return self.name


@pghistory.track(pghistory.InsertEvent("snapshot"), pghistory.UpdateEvent("snapshot"))
class Memo(models.Model):
    """Tracked as pghistory 2's ``Snapshot`` tracked a model: each event has the one label."""

    text = models.CharField(max_length=100)

    def __str__(self):
        return self.text
