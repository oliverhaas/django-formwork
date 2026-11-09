"""Support tickets from CRM contacts, with replies and saved answers."""

from __future__ import annotations

from datetime import timedelta

from crm.models import Contact
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone
from taskmanager.models import Member


class Ticket(models.Model):
    class Status(models.TextChoices):
        NEW = "new", "New"
        OPEN = "open", "Open"
        WAITING = "waiting", "Waiting on requester"
        SOLVED = "solved", "Solved"
        CLOSED = "closed", "Closed"

    class Priority(models.TextChoices):
        LOW = "low", "Low"
        NORMAL = "normal", "Normal"
        HIGH = "high", "High"
        URGENT = "urgent", "Urgent"

    class Channel(models.TextChoices):
        EMAIL = "email", "Email"
        CHAT = "chat", "Chat"
        PHONE = "phone", "Phone"
        FORM = "form", "Contact form"

    STATUS_COLORS = {
        Status.NEW: "info",
        Status.OPEN: "primary",
        Status.WAITING: "warning",
        Status.SOLVED: "success",
        Status.CLOSED: "neutral",
    }
    PRIORITY_COLORS = {
        Priority.LOW: "neutral",
        Priority.NORMAL: "info",
        Priority.HIGH: "warning",
        Priority.URGENT: "error",
    }
    OPEN_STATUSES = [Status.NEW, Status.OPEN, Status.WAITING]
    FIRST_RESPONSE_TARGET = timedelta(hours=8)

    subject = models.CharField(max_length=200)
    requester = models.ForeignKey(Contact, on_delete=models.CASCADE, related_name="tickets")
    assignee = models.ForeignKey(Member, null=True, blank=True, on_delete=models.SET_NULL, related_name="tickets")
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.NEW)
    priority = models.CharField(max_length=10, choices=Priority.choices, default=Priority.NORMAL)
    channel = models.CharField(max_length=10, choices=Channel.choices, default=Channel.EMAIL)
    opened_at = models.DateTimeField(default=timezone.now)
    first_response_at = models.DateTimeField(null=True, blank=True)
    solved_at = models.DateTimeField(null=True, blank=True)
    time_spent = models.DurationField(null=True, blank=True, help_text="Format: hh:mm:ss")
    satisfaction = models.PositiveSmallIntegerField(
        null=True, blank=True, validators=[MinValueValidator(1), MaxValueValidator(5)], help_text="Rating from 1 to 5."
    )

    class Meta:
        ordering = ["-opened_at"]

    def __str__(self):
        return f"#{self.pk} {self.subject}"


class Reply(models.Model):
    ticket = models.ForeignKey(Ticket, on_delete=models.CASCADE, related_name="replies")
    author = models.ForeignKey(
        Member, null=True, blank=True, on_delete=models.SET_NULL, related_name="+", help_text="Empty for the requester."
    )
    body = models.TextField()
    is_internal = models.BooleanField("internal note", default=False)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["created_at"]
        verbose_name_plural = "replies"

    def __str__(self):
        author = self.author.name if self.author else "Requester"
        return f"{author}, {self.created_at:%b %d, %H:%M}"


class CannedResponse(models.Model):
    title = models.CharField(max_length=100, unique=True)
    body = models.TextField()
    shortcut = models.SlugField(max_length=30, unique=True, help_text="Type /shortcut in a reply to insert it.")
    times_used = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["title"]

    def __str__(self):
        return self.title
