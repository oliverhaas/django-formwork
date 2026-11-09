"""Job openings, the candidates who apply and their interviews."""

from __future__ import annotations

from crm.models import Currency
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone
from people.models import Department, Employee
from taskmanager.models import Member, Profile

RATING = [MinValueValidator(1), MaxValueValidator(5)]


class Opening(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        OPEN = "open", "Open"
        ON_HOLD = "on_hold", "On hold"
        FILLED = "filled", "Filled"
        CLOSED = "closed", "Closed"

    class Workplace(models.TextChoices):
        OFFICE = "office", "Office"
        HYBRID = "hybrid", "Hybrid"
        REMOTE = "remote", "Remote"

    STATUS_COLORS = {
        Status.DRAFT: "neutral",
        Status.OPEN: "success",
        Status.ON_HOLD: "warning",
        Status.FILLED: "primary",
        Status.CLOSED: "secondary",
    }

    title = models.CharField(max_length=120)
    department = models.ForeignKey(Department, on_delete=models.PROTECT, related_name="openings")
    hiring_manager = models.ForeignKey(
        Member, null=True, blank=True, on_delete=models.SET_NULL, related_name="openings"
    )
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.DRAFT)
    workplace = models.CharField(max_length=10, choices=Workplace.choices, default=Workplace.HYBRID)
    employment_type = models.CharField(max_length=20, choices=Employee.Type.choices, default=Employee.Type.FULL_TIME)
    headcount = models.PositiveSmallIntegerField(default=1)
    salary_min = models.PositiveIntegerField(null=True, blank=True)
    salary_max = models.PositiveIntegerField(null=True, blank=True)
    currency = models.CharField(max_length=3, choices=Currency.choices, default=Currency.EUR)
    opened_on = models.DateField(default=timezone.localdate)
    closes_on = models.DateField(null=True, blank=True)
    description = models.TextField(blank=True)
    screening_questions = models.JSONField(
        default=list, blank=True, help_text="A JSON list of questions for the application form."
    )

    class Meta:
        ordering = ["-opened_on", "title"]

    def __str__(self):
        return self.title

    def clean(self):
        if self.salary_min and self.salary_max and self.salary_max < self.salary_min:
            raise ValidationError({"salary_max": "The maximum can't be below the minimum."})


class Candidate(models.Model):
    class Source(models.TextChoices):
        REFERRAL = "referral", "Referral"
        CAREERS_PAGE = "careers_page", "Careers page"
        JOB_BOARD = "job_board", "Job board"
        SOURCING = "sourcing", "Sourcing"
        AGENCY = "agency", "Agency"

    first_name = models.CharField(max_length=60)
    last_name = models.CharField(max_length=60)
    email = models.EmailField(unique=True)
    phone = models.CharField(max_length=30, blank=True)
    city = models.CharField(max_length=60, blank=True)
    country = models.CharField(max_length=2, blank=True, choices=Profile.Country.choices)
    profile_url = models.URLField("profile URL", blank=True)
    source = models.CharField(max_length=20, choices=Source.choices, default=Source.CAREERS_PAGE)
    referred_by = models.ForeignKey(Member, null=True, blank=True, on_delete=models.SET_NULL, related_name="referrals")
    resume = models.FileField(upload_to="resumes/", blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["last_name", "first_name"]

    def __str__(self):
        return f"{self.first_name} {self.last_name}"


class ApplicationManager(models.Manager["Application"]):
    def get_queryset(self):
        # The name of an application reads the candidate and the opening.
        return super().get_queryset().select_related("candidate", "opening")


class Application(models.Model):
    class Stage(models.TextChoices):
        APPLIED = "applied", "Applied"
        SCREEN = "screen", "Screen"
        INTERVIEW = "interview", "Interview"
        OFFER = "offer", "Offer"
        HIRED = "hired", "Hired"
        REJECTED = "rejected", "Rejected"

    STAGE_COLORS = {
        Stage.APPLIED: "neutral",
        Stage.SCREEN: "info",
        Stage.INTERVIEW: "primary",
        Stage.OFFER: "warning",
        Stage.HIRED: "success",
        Stage.REJECTED: "error",
    }
    NEXT_STAGE = {
        Stage.APPLIED: Stage.SCREEN,
        Stage.SCREEN: Stage.INTERVIEW,
        Stage.INTERVIEW: Stage.OFFER,
        Stage.OFFER: Stage.HIRED,
    }

    candidate = models.ForeignKey(Candidate, on_delete=models.CASCADE, related_name="applications")
    opening = models.ForeignKey(Opening, on_delete=models.CASCADE, related_name="applications")
    stage = models.CharField(max_length=10, choices=Stage.choices, default=Stage.APPLIED)
    owner = models.ForeignKey(
        Member,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
        help_text="The recruiter who runs this application.",
    )
    applied_at = models.DateTimeField(default=timezone.now)
    moved_at = models.DateTimeField("last stage change", default=timezone.now)
    rating = models.PositiveSmallIntegerField(null=True, blank=True, validators=RATING)
    rejection_reason = models.CharField(max_length=200, blank=True)

    objects = ApplicationManager()

    class Meta:
        ordering = ["-applied_at"]
        constraints = [models.UniqueConstraint(fields=["candidate", "opening"], name="one_application_per_opening")]

    def __str__(self):
        return f"{self.candidate} for {self.opening}"


class Interview(models.Model):
    class Kind(models.TextChoices):
        PHONE = "phone", "Phone screen"
        TECHNICAL = "technical", "Technical"
        ONSITE = "onsite", "On site"
        CULTURE = "culture", "Team fit"

    application = models.ForeignKey(Application, on_delete=models.CASCADE, related_name="interviews")
    kind = models.CharField(max_length=10, choices=Kind.choices, default=Kind.PHONE)
    interviewer = models.ForeignKey(Member, on_delete=models.PROTECT, related_name="interviews")
    scheduled_at = models.DateTimeField()
    duration = models.DurationField(null=True, blank=True, help_text="Format: hh:mm:ss")
    score = models.PositiveSmallIntegerField(
        null=True, blank=True, validators=RATING, help_text="Empty until the feedback is in."
    )
    feedback = models.TextField(blank=True)

    class Meta:
        ordering = ["scheduled_at"]

    def __str__(self):
        return f"{self.get_kind_display()} on {self.scheduled_at:%b %d}"
