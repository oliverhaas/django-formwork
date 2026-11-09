"""Invoices to CRM companies and the payments that settle them."""

from __future__ import annotations

from decimal import Decimal

from crm.models import Company, Currency
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import F, Sum
from django.utils import timezone


class Invoice(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        SENT = "sent", "Sent"
        PAID = "paid", "Paid"
        OVERDUE = "overdue", "Overdue"
        VOID = "void", "Void"

    STATUS_COLORS = {
        Status.DRAFT: "neutral",
        Status.SENT: "info",
        Status.PAID: "success",
        Status.OVERDUE: "error",
        Status.VOID: "warning",
    }

    number = models.CharField(max_length=14, unique=True)
    company = models.ForeignKey(Company, on_delete=models.PROTECT, related_name="invoices")
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.DRAFT)
    currency = models.CharField(max_length=3, choices=Currency.choices, default=Currency.EUR)
    issued_on = models.DateField(default=timezone.localdate)
    due_on = models.DateField()
    paid_on = models.DateField(null=True, blank=True)
    pdf = models.FileField("PDF", upload_to="invoices/", blank=True)
    notes = models.TextField(blank=True)
    total = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    class Meta:
        ordering = ["-issued_on", "-number"]

    def __str__(self):
        return self.number

    def clean(self):
        if self.issued_on and self.due_on and self.due_on < self.issued_on:
            raise ValidationError({"due_on": "The due date can't be before the issue date."})

    @property
    def is_overdue(self) -> bool:
        return self.status in (self.Status.SENT, self.Status.OVERDUE) and self.due_on < timezone.localdate()

    def recalculate(self) -> None:
        """Store the gross total of the lines."""
        gross = F("quantity") * F("unit_price") * (100 + F("tax_rate")) / 100
        self.total = (self.lines.aggregate(sum=Sum(gross))["sum"] or Decimal(0)).quantize(Decimal("0.01"))
        self.save(update_fields=["total"])


class InvoiceLine(models.Model):
    class TaxRate(models.IntegerChoices):
        NONE = 0, "0 %"
        REDUCED = 7, "7 %"
        STANDARD = 19, "19 %"

    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name="lines")
    description = models.CharField(max_length=200)
    quantity = models.DecimalField(max_digits=8, decimal_places=2, default=1)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    tax_rate = models.PositiveSmallIntegerField(choices=TaxRate.choices, default=TaxRate.STANDARD)

    class Meta:
        ordering = ["pk"]

    def __str__(self):
        return self.description


class Payment(models.Model):
    class Method(models.TextChoices):
        TRANSFER = "transfer", "Bank transfer"
        CARD = "card", "Card"
        DIRECT_DEBIT = "direct_debit", "Direct debit"

    invoice = models.ForeignKey(Invoice, on_delete=models.PROTECT, related_name="payments")
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    received_on = models.DateField(default=timezone.localdate)
    method = models.CharField(max_length=12, choices=Method.choices, default=Method.TRANSFER)
    reference = models.CharField(max_length=40, blank=True)

    class Meta:
        ordering = ["-received_on"]

    def __str__(self):
        return f"{self.amount} on {self.invoice}"
