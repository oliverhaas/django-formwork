from __future__ import annotations

import random
from datetime import timedelta
from decimal import Decimal

from crm.models import Company
from django.utils import timezone
from taskmanager import sample_data as fake

from .models import Invoice, InvoiceLine, Payment

SERVICES = [
    ("Onboarding workshop", 1200, 2400),
    ("Platform licence, monthly", 300, 900),
    ("Support plan", 150, 600),
    ("Custom integration", 2000, 9000),
    ("Training day", 800, 1600),
    ("Data migration", 1500, 5000),
    ("Consulting hours", 90, 180),
]


def clear() -> None:
    Payment.objects.all().delete()
    InvoiceLine.objects.all().delete()
    Invoice.objects.all().delete()


def seed(rng: random.Random, scale: float) -> str:
    companies = list(Company.objects.all())
    today = timezone.localdate()
    invoices = []
    lines = []
    for number in range(1, fake.scaled(700, scale) + 1):
        company = rng.choice(companies)
        issued_on = fake.day(rng, 540)
        due_on = issued_on + timedelta(days=rng.choice([14, 30, 30, 45]))
        if issued_on > today - timedelta(days=3):
            status = Invoice.Status.DRAFT
        elif due_on < today:
            status = rng.choices(
                [Invoice.Status.PAID, Invoice.Status.OVERDUE, Invoice.Status.VOID], weights=[20, 3, 1]
            )[0]
        else:
            status = rng.choices([Invoice.Status.SENT, Invoice.Status.PAID], weights=[3, 1])[0]
        invoice = Invoice(
            number=f"INV-{issued_on.year}-{number:05d}",
            company=company,
            status=status,
            currency=rng.choices(["EUR", "USD", "GBP"], weights=[6, 2, 1])[0],
            issued_on=issued_on,
            due_on=due_on,
            paid_on=min(today, issued_on + timedelta(days=rng.randint(3, 40)))
            if status == Invoice.Status.PAID
            else None,
        )
        invoices.append(invoice)
        for name, low, high in rng.sample(SERVICES, rng.randint(1, 4)):
            lines.append(
                InvoiceLine(
                    invoice=invoice,
                    description=name,
                    quantity=Decimal(rng.choice([1, 1, 2, 3, 8])),
                    unit_price=fake.money(rng, low, high),
                    tax_rate=rng.choices([19, 7, 0], weights=[8, 1, 1])[0],
                )
            )
    Invoice.objects.bulk_create(invoices)
    InvoiceLine.objects.bulk_create(lines)

    totals: dict[int, Decimal] = {}
    for line in lines:
        gross = line.quantity * line.unit_price * (100 + line.tax_rate) / 100
        totals[line.invoice.pk] = totals.get(line.invoice.pk, Decimal(0)) + gross
    for invoice in invoices:
        invoice.total = totals[invoice.pk].quantize(Decimal("0.01"))
    Invoice.objects.bulk_update(invoices, fields=["total"])

    payments = []
    for invoice in invoices:
        if invoice.status != Invoice.Status.PAID:
            continue
        parts = (
            [invoice.total]
            if rng.random() < 0.85
            else [
                (invoice.total / 2).quantize(Decimal("0.01")),
                invoice.total - (invoice.total / 2).quantize(Decimal("0.01")),
            ]
        )
        for part in parts:
            payments.append(
                Payment(
                    invoice=invoice,
                    amount=part,
                    received_on=invoice.paid_on,
                    method=rng.choices(list(Payment.Method), weights=[6, 2, 2])[0],
                    reference=f"{invoice.number}/{rng.randint(1000, 9999)}",
                )
            )
    Payment.objects.bulk_create(payments)
    return f"{len(invoices)} invoices, {len(lines)} invoice lines, {len(payments)} payments"
