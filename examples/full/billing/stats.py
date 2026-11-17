"""The figures in the admin's slots: over the invoice list and over an invoice's fields."""

import json

from django.db.models import Case, Count, F, Max, Q, Sum, Value, When
from django.db.models.functions import TruncMonth
from django.utils import timezone
from django.utils.formats import date_format
from taskmanager.figures import (
    BLANK,
    amount,
    bar,
    day,
    figure,
    legend,
    money,
    month_labels,
    months_between,
    number,
    percent,
    plural,
    stacked,
)

from .models import Invoice

UNPAID = [Invoice.Status.SENT, Invoice.Status.OVERDUE]

# The states of an issued invoice in the chart, the bottom one first.
STATES = [("paid", "Paid", "--color-success"), ("open", "Open", "--color-info"), ("late", "Overdue", "--color-error")]


def by_month(invoices, late):
    """The issued invoices per month of issue, by state: the Chart.js config and the rows of its table."""
    state = Case(
        When(status=Invoice.Status.PAID, then=Value("paid")),
        When(late, then=Value("late")),
        default=Value("open"),
    )
    rows = (
        invoices.filter(status__in=[Invoice.Status.PAID, *UNPAID])
        .annotate(month=TruncMonth("issued_on"), state=state)
        .values_list("month", "state")
        .annotate(count=Count("pk"))
    )
    counts = {(month, state): count for month, state, count in rows}
    if not counts:
        return None, []
    issued = [month for month, _ in counts]
    months = months_between(min(issued), max(issued))
    series = [(label, [counts.get((month, key), 0) for month in months], color) for key, label, color in STATES]
    names = [date_format(month, "F Y") for month in months]
    chart = {
        "type": "bar",
        "data": {"labels": month_labels(months), "datasets": stacked(*series)},
        "options": {
            "scales": {
                "x": {"stacked": True, "grid": {"display": False}, "ticks": {"maxRotation": 0}},
                "y": {"stacked": True, "beginAtZero": True, "ticks": {"maxTicksLimit": 5, "precision": 0}},
            },
            "plugins": {"tooltip": {"titles": names}},
        },
    }
    table = [[name, *(data[index] for _, data, _ in series)] for index, name in enumerate(names)]
    return chart, table


def invoice_stats(queryset):
    """Over the invoice list: what is outstanding and overdue, how invoices get paid, and each month's invoices."""
    invoices = Invoice.objects.filter(pk__in=queryset.values("pk")).order_by()
    late = Q(status__in=UNPAID, due_on__lt=timezone.localdate())
    rows = invoices.values("status", "currency").annotate(
        count=Count("pk"),
        value=Sum("total"),
        late=Count("pk", filter=late),
        late_value=Sum("total", filter=late),
        on_time=Count("pk", filter=Q(paid_on__lte=F("due_on"))),
    )
    outstanding, overdue = {}, {}
    paid = unpaid = on_time = late_count = 0
    for row in rows:
        currency = row["currency"]
        if row["status"] == Invoice.Status.PAID:
            paid += row["count"]
            on_time += row["on_time"]
        elif row["status"] in UNPAID:
            unpaid += row["count"]
            late_count += row["late"]
            outstanding[currency] = outstanding.get(currency, 0) + row["value"]
            overdue[currency] = overdue.get(currency, 0) + (row["late_value"] or 0)
    sums = money(outstanding)
    collected = percent(paid, paid + unpaid)
    punctual = percent(on_time, paid)
    chart, table = by_month(invoices, late)
    return {
        "figures": [
            figure(
                "Outstanding",
                sums[0] if sums else BLANK,
                f"plus {' · '.join(sums[1:])}" if sums[1:] else plural(unpaid, "unpaid invoice"),
            ),
            figure("Overdue", number(late_count), " · ".join(money(overdue)) or "Nothing is late"),
            figure(
                "Collected",
                BLANK if collected is None else f"{collected}%",
                f"{number(paid)} of {number(paid + unpaid)} invoices paid",
                bar(collected or 0, "success"),
            ),
            figure(
                "Paid on time",
                BLANK if punctual is None else f"{punctual}%",
                f"{number(paid - on_time)} paid late",
                bar(punctual or 0),
            ),
        ],
        "caption": "Issued invoices by month",
        "legend": legend(*((label, color) for _, label, color in STATES)),
        "chart": json.dumps(chart) if chart else None,
        "table": {"head": ["Month", *(label for _, label, _ in STATES)], "rows": table},
        "empty": "No issued invoices match the filters.",
    }


def invoice_figures(invoice):
    """Over an invoice's fields: its total, what is paid of it, when it is due and its payments."""
    today = timezone.localdate()
    payments = invoice.payments.aggregate(paid=Sum("amount"), count=Count("pk"), last=Max("received_on"))
    paid = payments["paid"] or 0
    share = min(percent(paid, invoice.total) or 0, 100)
    left = (invoice.due_on - today).days
    if invoice.status == Invoice.Status.PAID and invoice.paid_on:
        behind = (invoice.paid_on - invoice.due_on).days
        due = figure(
            "Paid on", date_format(invoice.paid_on, "M j"), f"{plural(behind, 'day')} late" if behind > 0 else "On time"
        )
    elif invoice.status not in UNPAID:
        due = figure("Due", date_format(invoice.due_on, "M j"), invoice.get_status_display())
    elif left < 0:
        due = figure("Overdue by", plural(-left, "day"), f"Due {day(invoice.due_on)}")
    else:
        due = figure("Due in", plural(left, "day"), date_format(invoice.due_on, "D, M j, Y"))
    return {
        "figures": [
            figure("Total", amount(invoice.total, invoice.currency), plural(invoice.lines.count(), "line")),
            figure(
                "Paid",
                amount(paid, invoice.currency),
                "In full" if paid >= invoice.total else f"{amount(invoice.total - paid, invoice.currency)} to pay",
                bar(share, "success"),
            ),
            due,
            figure(
                "Payments",
                number(payments["count"]),
                f"Last on {day(payments['last'])}" if payments["last"] else "None received",
            ),
        ],
    }
