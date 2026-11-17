"""The figures in the admin's slots: over the ticket list and over a ticket's fields."""

import json
from datetime import timedelta

from django.db.models import Avg, Count, F, Q
from django.db.models.functions import TruncWeek
from django.utils import timezone
from django.utils.formats import date_format
from taskmanager.figures import BLANK, bar, figure, legend, number, percent, plural, span

from .models import Ticket

# A longer range shows its last weeks.
WEEKS = 26

TARGET = span(Ticket.FIRST_RESPONSE_TARGET)


def by_week(tickets, field):
    rows = (
        tickets.filter(**{f"{field}__isnull": False})
        .annotate(week=TruncWeek(field))
        .values("week")
        .annotate(count=Count("pk"))
        .values_list("week", "count")
    )
    return {timezone.localdate(week): count for week, count in rows}


def ticket_stats(queryset):
    """Over the ticket list: the open tickets and the service figures, and the tickets of each week."""
    tickets = Ticket.objects.filter(pk__in=queryset.values("pk")).order_by()
    in_time = Q(first_response_at__lte=F("opened_at") + Ticket.FIRST_RESPONSE_TARGET)
    counts = tickets.aggregate(
        open=Count("pk", filter=Q(status__in=Ticket.OPEN_STATUSES)),
        waiting=Count("pk", filter=Q(status=Ticket.Status.WAITING)),
        answered=Count("first_response_at"),
        in_time=Count("pk", filter=in_time),
        solved=Count("solved_at"),
        time_to_solve=Avg(F("solved_at") - F("opened_at")),
        rating=Avg("satisfaction"),
        ratings=Count("satisfaction"),
    )
    answered = percent(counts["in_time"], counts["answered"])
    rating = counts["rating"]
    opened, solved = by_week(tickets, "opened_at"), by_week(tickets, "solved_at")
    chart, rows = None, []
    if opened:
        first, last = min(opened), max([*opened, *solved])
        weeks = [first + timedelta(weeks=index) for index in range((last - first).days // 7 + 1)][-WEEKS:]
        lines = [("Opened", opened, "--color-primary"), ("Solved", solved, "--color-success")]
        chart = {
            "type": "line",
            "data": {
                "labels": [date_format(week, "M j") for week in weeks],
                "datasets": [
                    {
                        "label": label,
                        "data": [counts_by_week.get(week, 0) for week in weeks],
                        "borderColor": color,
                        "pointBackgroundColor": color,
                        # One week alone has no line, so it shows its points.
                        "pointRadius": 0 if len(weeks) > 1 else 3,
                    }
                    for label, counts_by_week, color in lines
                ],
            },
            "options": {
                "scales": {
                    "x": {"grid": {"display": False}, "ticks": {"maxRotation": 0, "maxTicksLimit": 7}},
                    "y": {"beginAtZero": True, "ticks": {"maxTicksLimit": 5, "precision": 0}},
                },
                "plugins": {"tooltip": {"titles": [f"Week of {date_format(week, 'F j, Y')}" for week in weeks]}},
            },
        }
        rows = [
            [date_format(week, "F j, Y"), number(opened.get(week, 0)), number(solved.get(week, 0))] for week in weeks
        ]
    return {
        "figures": [
            figure("Open tickets", number(counts["open"]), f"{number(counts['waiting'])} waiting on requester"),
            figure(
                "Time to solve",
                span(counts["time_to_solve"]) if counts["time_to_solve"] else BLANK,
                f"Average of {number(counts['solved'])} solved",
            ),
            figure(
                "First response",
                BLANK if answered is None else f"{answered}%",
                f"Within {TARGET}",
                bar(answered or 0),
            ),
            figure(
                "Satisfaction",
                f"{rating:.1f}" if rating else BLANK,
                plural(counts["ratings"], "rating"),
                bar(round(rating * 20) if rating else 0, "success"),
                of="5" if rating else None,
            ),
        ],
        "caption": "Tickets by week",
        "legend": legend(("Opened", "--color-primary"), ("Solved", "--color-success"), line=True),
        "chart": json.dumps(chart) if chart else None,
        "table": {"head": ["Week of", "Opened", "Solved"], "rows": rows},
        "empty": "No tickets match the filters.",
    }


RATING_COLORS = {1: "error", 2: "error", 3: "warning", 4: "success", 5: "success"}


def ticket_figures(ticket):
    """Over a ticket's fields: how fast the first response and the solution came, the replies and the rating."""
    now = timezone.now()
    replies = ticket.replies.aggregate(
        public=Count("pk", filter=Q(is_internal=False)), internal=Count("pk", filter=Q(is_internal=True))
    )
    # The bar of the first response fills as the target runs out.
    answered = ticket.first_response_at is not None
    waited = (ticket.first_response_at or now) - ticket.opened_at
    late = waited > Ticket.FIRST_RESPONSE_TARGET
    if answered or ticket.status in Ticket.OPEN_STATUSES:
        note = f"Over the target of {TARGET}" if late else f"Within the target of {TARGET}"
        response = figure(
            "First response",
            span(waited) if answered else BLANK,
            note if answered or late else f"{span(Ticket.FIRST_RESPONSE_TARGET - waited)} left of the target",
            bar(
                min(round(100 * waited / Ticket.FIRST_RESPONSE_TARGET), 100),
                "error" if late else "success" if answered else "primary",
            ),
        )
    else:
        response = figure("First response", BLANK, "Closed without a response", bar(0))
    if ticket.solved_at:
        solution = figure(
            "Time to solve",
            span(ticket.solved_at - ticket.opened_at),
            f"Solved {date_format(timezone.localtime(ticket.solved_at), 'M j, H:i')}",
        )
    else:
        solution = figure(
            "Open for",
            span(now - ticket.opened_at),
            f"Since {date_format(timezone.localtime(ticket.opened_at), 'M j, H:i')}",
        )
    rating = ticket.satisfaction
    return {
        "figures": [
            response,
            solution,
            figure("Replies", number(replies["public"]), plural(replies["internal"], "internal note")),
            figure(
                "Satisfaction",
                rating or BLANK,
                "Rated by the requester" if rating else "No rating yet",
                bar(rating * 20 if rating else 0, RATING_COLORS.get(rating, "primary")),
                of="5" if rating else None,
            ),
        ],
    }
