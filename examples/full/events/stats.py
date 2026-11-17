"""The figures in the admin's slots: over the event list, and over and under an event's fields."""

import json
from datetime import timedelta

from django.db.models import BooleanField, Count, ExpressionWrapper, Q, Sum
from django.db.models.functions import TruncDate, TruncMonth
from django.utils import timezone
from django.utils.formats import date_format, number_format
from django.utils.timesince import timeuntil

from .models import Event, Registration

# A longer range shows its last months.
MONTHS = 24

# Whole class names, so Tailwind finds them.
BARS = {
    "info": "progress-info",
    "warning": "progress-warning",
    "success": "progress-success",
    "error": "progress-error",
    "neutral": "",
}


def number(value):
    return number_format(value, force_grouping=True)


def percent(part, whole):
    return round(100 * part / whole) if whole else None


def by_month(ids, taken, now):
    """The registrations per month of the events' start, those of held and upcoming events stacked.

    Returns the Chart.js config and the same figures as rows, for the table a screen reader gets.
    """
    counts = {}
    rows = (
        Registration.objects.filter(taken, event__in=ids)
        .annotate(
            month=TruncMonth("event__starts_at"),
            upcoming=ExpressionWrapper(Q(event__starts_at__gte=now), output_field=BooleanField()),
        )
        .values_list("month", "upcoming")
        .annotate(count=Count("pk"))
    )
    for month, upcoming, count in rows:
        counts.setdefault(month, [0, 0])[upcoming] += count
    events = dict(
        Event.objects.filter(pk__in=ids)
        .annotate(month=TruncMonth("starts_at"))
        .values("month")
        .annotate(count=Count("pk"))
        .values_list("month", "count")
    )
    if not events:
        return None, []
    months = [min(events)]
    while (month := months[-1]) < max(events):
        months.append(month.replace(year=month.year + month.month // 12, month=month.month % 12 + 1))
    months = months[-MONTHS:]
    held = [counts.get(month, (0, 0))[0] for month in months]
    upcoming = [counts.get(month, (0, 0))[1] for month in months]
    names = [date_format(month, "F Y") for month in months]
    held_events = [events.get(month, 0) for month in months]
    top = {"topLeft": 3, "topRight": 3}
    chart = {
        "type": "bar",
        "data": {
            # The year shows under the first month and under each January.
            "labels": [
                [date_format(month, "M"), date_format(month, "Y") if index == 0 or month.month == 1 else ""]
                for index, month in enumerate(months)
            ],
            "datasets": [
                {
                    "label": "Held",
                    "data": held,
                    "backgroundColor": "--color-base-content/25",
                    "borderRadius": [0 if above else top for above in upcoming],
                    "maxBarThickness": 24,
                },
                {
                    "label": "Upcoming",
                    "data": upcoming,
                    "backgroundColor": "--color-primary",
                    "borderRadius": top,
                    # A gap in the card's color parts the two stacked bars.
                    "borderColor": "--color-base-100",
                    "borderWidth": [{"bottom": 2} if below else 0 for below in held],
                    "borderSkipped": False,
                    "maxBarThickness": 24,
                },
            ],
        },
        "options": {
            "scales": {
                "x": {"stacked": True, "grid": {"display": False}, "ticks": {"maxRotation": 0}},
                "y": {"stacked": True, "beginAtZero": True, "ticks": {"maxTicksLimit": 5, "precision": 0}},
            },
            "plugins": {
                "tooltip": {
                    "titles": names,
                    "footers": [f"{count} event{'' if count == 1 else 's'}" for count in held_events],
                }
            },
        },
    }
    table = [
        {"name": name, "registrations": number(a + b), "events": count}
        for name, a, b, count in zip(names, held, upcoming, held_events, strict=True)
    ]
    return chart, table


def event_stats(queryset):
    now = timezone.now()
    ids = queryset.values("pk")
    taken = ~Q(status__in=[Registration.Status.CANCELLED, Registration.Status.WAITLIST])
    events = Event.objects.filter(pk__in=ids).aggregate(
        total=Count("pk"),
        upcoming=Count("pk", filter=Q(starts_at__gte=now)),
    )
    registrations = Registration.objects.filter(event__in=ids).aggregate(
        taken=Count("pk", filter=taken),
        waitlist=Count("pk", filter=Q(status=Registration.Status.WAITLIST)),
        attended=Count("pk", filter=Q(status=Registration.Status.ATTENDED)),
        no_show=Count("pk", filter=Q(status=Registration.Status.NO_SHOW)),
    )
    limited = Event.objects.filter(pk__in=ids, starts_at__gte=now, capacity__isnull=False)
    seats = limited.aggregate(seats=Sum("capacity"))["seats"] or 0
    seats_taken = Registration.objects.filter(taken, event__in=limited).count()
    checked = registrations["attended"] + registrations["no_show"]
    chart, months = by_month(ids, taken, now)
    return {
        "events": number(events["total"]),
        "upcoming": number(events["upcoming"]),
        "taken": number(registrations["taken"]),
        "waitlist": number(registrations["waitlist"]),
        "filled": percent(seats_taken, seats),
        "seats_taken": number(seats_taken),
        "seats": number(seats),
        "attendance": percent(registrations["attended"], checked),
        "no_show": number(registrations["no_show"]),
        "chart": json.dumps(chart) if chart else None,
        "months": months,
    }


def status_counts(event):
    counts = dict(event.registrations.values_list("status").annotate(Count("pk")))
    return {status: counts.get(status, 0) for status in Registration.Status}


def event_figures(event):
    """The figures over an event's fields: seats, wait list, attendance or the time left, and revenue."""
    counts = status_counts(event)
    status = Registration.Status
    taken = counts[status.REGISTERED] + counts[status.ATTENDED] + counts[status.NO_SHOW]
    checked = counts[status.ATTENDED] + counts[status.NO_SHOW]
    upcoming = event.starts_at >= timezone.now()
    return {
        "taken": number(taken),
        "capacity": number(event.capacity) if event.capacity else None,
        "filled": percent(taken, event.capacity),
        "left": number(max(event.capacity - taken, 0)) if event.capacity else None,
        "waitlist": number(counts[status.WAITLIST]),
        "cancelled": number(counts[status.CANCELLED]),
        "upcoming": upcoming,
        "starts_in": timeuntil(event.starts_at, depth=1) if upcoming else None,
        "starts_at": event.starts_at,
        "attendance": percent(counts[status.ATTENDED], checked),
        "no_show": number(counts[status.NO_SHOW]),
        "revenue": number(taken * event.price) if event.price else None,
        "price": number(event.price),
    }


def event_signups(event):
    """Under an event's fields: the registrations by status, and the sign-ups as they came in."""
    counts = status_counts(event)
    total = sum(counts.values())
    statuses = [
        {
            "label": status.label,
            "color": Registration.STATUS_COLORS[status],
            "bar": BARS[Registration.STATUS_COLORS[status]],
            "count": number(counts[status]),
            "share": percent(counts[status], total) or 0,
        }
        for status in Registration.Status
    ]
    days = dict(
        event.registrations.annotate(day=TruncDate("registered_at"))
        .values("day")
        .annotate(count=Count("pk"))
        .values_list("day", "count")
    )
    chart = None
    if days:
        dates = [min(days) + timedelta(days=offset) for offset in range((max(days) - min(days)).days + 1)]
        running, signups = 0, []
        for day in dates:
            running += days.get(day, 0)
            signups.append(running)
        datasets = [
            {
                "label": "Sign-ups",
                "data": signups,
                "borderColor": "--color-primary",
                "backgroundColor": "--color-primary/10",
                "pointBackgroundColor": "--color-primary",
                "fill": True,
            }
        ]
        if event.capacity:
            datasets.append(
                {
                    "label": "Seats",
                    "data": [event.capacity] * len(dates),
                    "borderColor": "--color-base-content/40",
                    "borderDash": [4, 4],
                    "borderWidth": 1.5,
                    "pointHoverRadius": 0,
                }
            )
        chart = {
            "type": "line",
            "data": {"labels": [date_format(day, "M j") for day in dates], "datasets": datasets},
            "options": {
                "scales": {
                    "x": {"grid": {"display": False}, "ticks": {"maxRotation": 0, "maxTicksLimit": 8}},
                    "y": {"beginAtZero": True, "ticks": {"maxTicksLimit": 5, "precision": 0}},
                },
                "plugins": {"tooltip": {"titles": [date_format(day, "l, F j, Y") for day in dates]}},
            },
        }
    return {
        "statuses": statuses,
        "total": number(total),
        "chart": json.dumps(chart) if chart else None,
        "has_seats": bool(event.capacity),
    }
