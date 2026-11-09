"""Webinars, meetups and conferences with the CRM contacts who sign up."""

from __future__ import annotations

import uuid
from decimal import Decimal

from crm.models import Contact
from django.core.exceptions import ValidationError
from django.db import models
from taskmanager.models import Member, Profile


class Venue(models.Model):
    name = models.CharField(max_length=120)
    is_virtual = models.BooleanField("virtual", default=False, help_text="Streams have a URL instead of an address.")
    city = models.CharField(max_length=60, blank=True)
    country = models.CharField(max_length=2, blank=True, choices=Profile.Country.choices)
    address = models.TextField(blank=True)
    url = models.URLField("URL", blank=True)
    capacity = models.PositiveIntegerField(null=True, blank=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class Event(models.Model):
    class Kind(models.TextChoices):
        WEBINAR = "webinar", "Webinar"
        MEETUP = "meetup", "Meetup"
        WORKSHOP = "workshop", "Workshop"
        CONFERENCE = "conference", "Conference"

    KIND_COLORS = {Kind.WEBINAR: "info", Kind.MEETUP: "accent", Kind.WORKSHOP: "warning", Kind.CONFERENCE: "primary"}

    title = models.CharField(max_length=160)
    slug = models.SlugField(max_length=160, unique=True)
    kind = models.CharField(max_length=12, choices=Kind.choices, default=Kind.WEBINAR)
    venue = models.ForeignKey(Venue, null=True, blank=True, on_delete=models.SET_NULL, related_name="events")
    host = models.ForeignKey(Member, on_delete=models.PROTECT, related_name="hosted_events")
    starts_at = models.DateTimeField()
    ends_at = models.DateTimeField()
    capacity = models.PositiveIntegerField(null=True, blank=True, help_text="Empty for no limit.")
    price = models.DecimalField(max_digits=8, decimal_places=2, default=Decimal(0), help_text="0 for a free event.")
    is_published = models.BooleanField("published", default=False)
    description = models.TextField(blank=True)
    cover = models.ImageField(upload_to="events/", blank=True)

    class Meta:
        ordering = ["-starts_at"]

    def __str__(self):
        return self.title

    def clean(self):
        if self.starts_at and self.ends_at and self.ends_at <= self.starts_at:
            raise ValidationError({"ends_at": "The event has to end after it starts."})


class Registration(models.Model):
    class Status(models.TextChoices):
        REGISTERED = "registered", "Registered"
        WAITLIST = "waitlist", "Wait list"
        ATTENDED = "attended", "Attended"
        NO_SHOW = "no_show", "No show"
        CANCELLED = "cancelled", "Cancelled"

    STATUS_COLORS = {
        Status.REGISTERED: "info",
        Status.WAITLIST: "warning",
        Status.ATTENDED: "success",
        Status.NO_SHOW: "error",
        Status.CANCELLED: "neutral",
    }

    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name="registrations")
    contact = models.ForeignKey(Contact, on_delete=models.CASCADE, related_name="registrations")
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.REGISTERED)
    code = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    registered_at = models.DateTimeField()
    checked_in_at = models.DateTimeField(null=True, blank=True)
    dietary_needs = models.CharField(max_length=120, blank=True)

    class Meta:
        ordering = ["-registered_at"]
        constraints = [models.UniqueConstraint(fields=["event", "contact"], name="one_registration_per_contact")]

    def __str__(self):
        return f"{self.contact} at {self.event}"
