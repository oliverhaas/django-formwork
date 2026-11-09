"""Departments, employees, time off and company equipment."""

from __future__ import annotations

from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone
from taskmanager.models import Member


class Department(models.Model):
    name = models.CharField(max_length=60, unique=True)
    code = models.CharField(max_length=8, unique=True)
    head = models.ForeignKey(
        Member, null=True, blank=True, on_delete=models.SET_NULL, related_name="headed_departments"
    )
    standup_time = models.TimeField(null=True, blank=True)
    budget = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class EmployeeManager(models.Manager["Employee"]):
    def get_queryset(self):
        # The name lives on the member, so every list of employees joins it.
        return super().get_queryset().select_related("member")


class Employee(models.Model):
    class Type(models.TextChoices):
        FULL_TIME = "full_time", "Full time"
        PART_TIME = "part_time", "Part time"
        CONTRACTOR = "contractor", "Contractor"
        INTERN = "intern", "Intern"

    TYPE_COLORS = {Type.FULL_TIME: "primary", Type.PART_TIME: "info", Type.CONTRACTOR: "warning", Type.INTERN: "accent"}

    member = models.OneToOneField(Member, on_delete=models.CASCADE, related_name="employee")
    department = models.ForeignKey(Department, on_delete=models.PROTECT, related_name="employees")
    job_title = models.CharField(max_length=80)
    manager = models.ForeignKey("self", null=True, blank=True, on_delete=models.SET_NULL, related_name="reports")
    employment_type = models.CharField(max_length=20, choices=Type.choices, default=Type.FULL_TIME)
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)
    weekly_hours = models.PositiveSmallIntegerField(default=40)
    remote = models.BooleanField(default=False)

    objects = EmployeeManager()

    class Meta:
        ordering = ["member__name"]

    def __str__(self):
        return self.member.name


class TimeOff(models.Model):
    class Kind(models.TextChoices):
        VACATION = "vacation", "Vacation"
        SICK = "sick", "Sick leave"
        PARENTAL = "parental", "Parental leave"
        TRAINING = "training", "Training"
        UNPAID = "unpaid", "Unpaid"

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        APPROVED = "approved", "Approved"
        DECLINED = "declined", "Declined"

    STATUS_COLORS = {Status.PENDING: "warning", Status.APPROVED: "success", Status.DECLINED: "error"}

    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name="time_off")
    kind = models.CharField(max_length=20, choices=Kind.choices, default=Kind.VACATION)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    starts_on = models.DateField()
    ends_on = models.DateField()
    note = models.TextField(blank=True)
    requested_at = models.DateTimeField(default=timezone.now)
    decided_by = models.ForeignKey(Member, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")

    class Meta:
        ordering = ["-starts_on"]
        verbose_name = "time off request"

    def __str__(self):
        return f"{self.get_kind_display()} {self.starts_on:%b %d}"

    def clean(self):
        if self.starts_on and self.ends_on and self.ends_on < self.starts_on:
            raise ValidationError({"ends_on": "The last day can't be before the first."})

    @property
    def days(self) -> int:
        return (self.ends_on - self.starts_on).days + 1


class Equipment(models.Model):
    class Kind(models.TextChoices):
        LAPTOP = "laptop", "Laptop"
        MONITOR = "monitor", "Monitor"
        PHONE = "phone", "Phone"
        HEADSET = "headset", "Headset"
        DOCK = "dock", "Docking station"

    asset_tag = models.CharField(max_length=12, unique=True)
    kind = models.CharField(max_length=20, choices=Kind.choices)
    model_name = models.CharField(max_length=80)
    serial_number = models.CharField(max_length=40, blank=True)
    assigned_to = models.ForeignKey(
        Employee, null=True, blank=True, on_delete=models.SET_NULL, related_name="equipment"
    )
    purchased_on = models.DateField()
    purchase_price = models.DecimalField(max_digits=8, decimal_places=2)
    warranty_until = models.DateField(null=True, blank=True)
    retired = models.BooleanField(default=False)

    class Meta:
        ordering = ["asset_tag"]
        verbose_name_plural = "equipment"

    def __str__(self):
        return f"{self.asset_tag} {self.model_name}"
