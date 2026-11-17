"""The figures over the event list: counts, two rates and the registrations by month."""

from math import ceil, floor, log10

from django.db.models import BooleanField, Count, ExpressionWrapper, Q, Sum
from django.db.models.functions import TruncMonth
from django.utils import timezone
from django.utils.formats import date_format, number_format

from .models import Event, Registration

# A longer range shows its last months.
MONTHS = 24


def number(value):
    return number_format(value, force_grouping=True)


def percent(part, whole):
    return round(100 * part / whole) if whole else None


def axis(top):
    """Round steps from 0 up to at least ``top``: 0, 500, 1,000, 1,500."""
    if top <= 0:
        return [0, 1]
    rough = top / 4
    magnitude = 10 ** floor(log10(rough)) if rough >= 1 else 1
    step = next(m * magnitude for m in (1, 2, 5, 10) if m * magnitude >= rough)
    return [step * i for i in range(ceil(top / step) + 1)]


def by_month(ids, taken, now):
    """A column per month of the events' start, the registrations of held and upcoming events stacked."""
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
        return [], [0, 1]
    months = [min(events)]
    while (month := months[-1]) < max(events):
        months.append(month.replace(year=month.year + month.month // 12, month=month.month % 12 + 1))
    months = months[-MONTHS:]
    ticks = axis(max(sum(counts.get(month, (0, 0))) for month in months))
    columns = []
    for index, month in enumerate(months):
        held, upcoming = counts.get(month, (0, 0))
        total = held + upcoming
        columns.append(
            {
                "held": 100 * held / ticks[-1],
                "upcoming": 100 * upcoming / ticks[-1],
                "label": date_format(month, "M"),
                "year": date_format(month, "Y") if index == 0 or month.month == 1 else "",
                # A phone has room for every third month's name.
                "minor": index % 3 != 0,
                "late": index >= len(months) / 2,
                "name": date_format(month, "F Y"),
                "registrations": number(total),
                "events": events.get(month, 0),
            }
        )
    return columns, ticks


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
    columns, ticks = by_month(ids, taken, now)
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
        "columns": columns,
        "ticks": [{"label": number(tick), "at": 100 * tick / ticks[-1]} for tick in ticks],
    }
