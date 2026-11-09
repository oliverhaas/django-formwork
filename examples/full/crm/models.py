"""Companies, their contacts, the deals in the pipeline and the activity log."""

from __future__ import annotations

from django.core.validators import MaxValueValidator
from django.db import models
from django.utils import timezone
from taskmanager.models import Member, Profile

Country = Profile.Country


class Currency(models.TextChoices):
    EUR = "EUR", "Euro"
    USD = "USD", "US dollar"
    GBP = "GBP", "Pound sterling"


class Company(models.Model):
    class Industry(models.TextChoices):
        SOFTWARE = "software", "Software"
        NONPROFIT = "nonprofit", "Nonprofit"
        MANUFACTURING = "manufacturing", "Manufacturing"
        FINANCE = "finance", "Finance"
        HEALTHCARE = "healthcare", "Healthcare"
        EDUCATION = "education", "Education"
        ENERGY = "energy", "Energy"
        MEDIA = "media", "Media"

    class Size(models.TextChoices):
        XS = "xs", "1-10"
        S = "s", "11-50"
        M = "m", "51-250"
        L = "l", "251-1000"
        XL = "xl", "1000+"

    name = models.CharField(max_length=120, unique=True)
    website = models.URLField(blank=True)
    industry = models.CharField(max_length=20, choices=Industry.choices)
    size = models.CharField(max_length=4, choices=Size.choices)
    country = models.CharField(max_length=2, choices=Country.choices)
    account_manager = models.ForeignKey(
        Member, null=True, blank=True, on_delete=models.SET_NULL, related_name="accounts"
    )
    annual_revenue = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["name"]
        verbose_name_plural = "companies"

    def __str__(self):
        return self.name


class Contact(models.Model):
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name="contacts")
    first_name = models.CharField(max_length=60)
    last_name = models.CharField(max_length=60)
    email = models.EmailField(unique=True)
    phone = models.CharField(max_length=30, blank=True)
    job_title = models.CharField(max_length=80, blank=True)
    is_primary = models.BooleanField("primary contact", default=False)
    newsletter = models.BooleanField(default=False)
    last_contacted = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["last_name", "first_name"]

    def __str__(self):
        return f"{self.first_name} {self.last_name}"


class Deal(models.Model):
    class Stage(models.TextChoices):
        LEAD = "lead", "Lead"
        QUALIFIED = "qualified", "Qualified"
        PROPOSAL = "proposal", "Proposal"
        NEGOTIATION = "negotiation", "Negotiation"
        WON = "won", "Won"
        LOST = "lost", "Lost"

    STAGE_COLORS = {
        Stage.LEAD: "neutral",
        Stage.QUALIFIED: "info",
        Stage.PROPOSAL: "primary",
        Stage.NEGOTIATION: "accent",
        Stage.WON: "success",
        Stage.LOST: "error",
    }
    OPEN_STAGES = [Stage.LEAD, Stage.QUALIFIED, Stage.PROPOSAL, Stage.NEGOTIATION]

    name = models.CharField(max_length=160)
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name="deals")
    contact = models.ForeignKey(Contact, null=True, blank=True, on_delete=models.SET_NULL, related_name="deals")
    owner = models.ForeignKey(Member, null=True, blank=True, on_delete=models.SET_NULL, related_name="deals")
    stage = models.CharField(max_length=20, choices=Stage.choices, default=Stage.LEAD)
    value = models.DecimalField(max_digits=12, decimal_places=2)
    currency = models.CharField(max_length=3, choices=Currency.choices, default=Currency.EUR)
    probability = models.PositiveSmallIntegerField(
        default=10, validators=[MaxValueValidator(100)], help_text="In percent."
    )
    expected_close = models.DateField(null=True, blank=True)
    closed_on = models.DateField(null=True, blank=True)
    lost_reason = models.CharField(max_length=200, blank=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.name


class Activity(models.Model):
    class Kind(models.TextChoices):
        CALL = "call", "Call"
        EMAIL = "email", "Email"
        MEETING = "meeting", "Meeting"
        NOTE = "note", "Note"

    KIND_COLORS = {Kind.CALL: "info", Kind.EMAIL: "neutral", Kind.MEETING: "accent", Kind.NOTE: "secondary"}

    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name="activities")
    deal = models.ForeignKey(Deal, null=True, blank=True, on_delete=models.SET_NULL, related_name="activities")
    contact = models.ForeignKey(Contact, null=True, blank=True, on_delete=models.SET_NULL, related_name="activities")
    kind = models.CharField(max_length=10, choices=Kind.choices)
    subject = models.CharField(max_length=200)
    body = models.TextField(blank=True)
    occurred_at = models.DateTimeField(default=timezone.now)
    duration = models.DurationField(null=True, blank=True, help_text="For calls and meetings, as HH:MM:SS.")
    logged_by = models.ForeignKey(Member, null=True, blank=True, on_delete=models.SET_NULL, related_name="activities")

    class Meta:
        ordering = ["-occurred_at"]
        verbose_name_plural = "activities"

    def __str__(self):
        return self.subject
