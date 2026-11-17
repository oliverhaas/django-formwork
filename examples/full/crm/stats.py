"""The figures in the admin's slots: over the deal list and over a deal's fields."""

import json

from django.db.models import Count, Max, Q, Sum
from django.utils import timezone
from django.utils.formats import date_format
from django.utils.timesince import timesince
from taskmanager.figures import BLANK, amount, bar, day, figure, money, number, percent, plural, step, steps, token

from .models import Deal


def deal_stats(queryset):
    """Over the deal list: the open pipeline, the win rate, and the deals of each stage as a bar."""
    today = timezone.localdate()
    this_month = Q(expected_close__year=today.year, expected_close__month=today.month)
    rows = (
        Deal.objects.filter(pk__in=queryset.values("pk"))
        .values("stage", "currency")
        .annotate(
            count=Count("pk"),
            value=Sum("value"),
            closing=Count("pk", filter=this_month),
            probability=Sum("probability"),
        )
        .order_by()
    )
    counts = dict.fromkeys(Deal.Stage, 0)
    values = {stage: {} for stage in Deal.Stage}
    pipeline = {}
    closing = probability = 0
    for row in rows:
        stage = Deal.Stage(row["stage"])
        counts[stage] += row["count"]
        values[stage][row["currency"]] = row["value"]
        if stage in Deal.OPEN_STAGES:
            pipeline[row["currency"]] = pipeline.get(row["currency"], 0) + row["value"]
            closing += row["closing"]
            probability += row["probability"]
    open_deals = sum(counts[stage] for stage in Deal.OPEN_STAGES)
    won, lost = counts[Deal.Stage.WON], counts[Deal.Stage.LOST]
    win_rate = percent(won, won + lost)
    likely = round(probability / open_deals) if open_deals else None
    sums = money(pipeline)
    worth = {stage: " · ".join(money(values[stage])) for stage in Deal.Stage}
    chart = {
        "type": "bar",
        "data": {
            "labels": [stage.label for stage in Deal.Stage],
            "datasets": [
                {
                    "label": "Deals",
                    "data": list(counts.values()),
                    "backgroundColor": [token(Deal.STAGE_COLORS[stage]) for stage in Deal.Stage],
                    "maxBarThickness": 18,
                }
            ],
        },
        "options": {
            "indexAxis": "y",
            "interaction": {"axis": "y"},
            "scales": {
                "x": {"beginAtZero": True, "ticks": {"maxTicksLimit": 6, "precision": 0}},
                "y": {"grid": {"display": False}},
            },
            "plugins": {"tooltip": {"footers": [worth[stage] or "No value" for stage in Deal.Stage]}},
        },
    }
    return {
        "figures": [
            figure("Open deals", number(open_deals), f"{closing} close this month"),
            figure(
                "Open pipeline",
                sums[0] if sums else BLANK,
                f"plus {' · '.join(sums[1:])}" if sums[1:] else "In one currency" if sums else "No open deals",
            ),
            figure(
                "Win rate",
                BLANK if win_rate is None else f"{win_rate}%",
                f"{number(won)} won, {number(lost)} lost",
                bar(win_rate or 0, "success"),
            ),
            figure(
                "Probability",
                BLANK if likely is None else f"{likely}%",
                "Avg. of open deals",
                bar(likely or 0),
            ),
        ],
        "caption": "Deals by stage",
        "chart": json.dumps(chart) if any(counts.values()) else None,
        "table": {
            "head": ["Stage", "Deals", "Value"],
            "rows": [[stage.label, number(counts[stage]), worth[stage]] for stage in Deal.Stage],
        },
        "empty": "No deals match the filters.",
    }


def deal_steps(deal):
    names = [stage.label for stage in Deal.OPEN_STAGES]
    if deal.stage == Deal.Stage.LOST:
        return [*steps(names, -1), step("Lost", "error", "✕", current=True)]
    names.append(Deal.Stage.WON.label)
    if deal.stage == Deal.Stage.WON:
        return steps(names, len(names) - 1, color="success", closed=True)
    return steps(names, Deal.OPEN_STAGES.index(deal.stage))


def deal_figures(deal):
    """Over a deal's fields: its place in the pipeline, its value, its dates and its activities."""
    today = timezone.localdate()
    is_open = deal.stage in Deal.OPEN_STAGES
    created = timezone.localdate(deal.created_at)
    activities = deal.activities.aggregate(count=Count("pk"), last=Max("occurred_at"))
    if is_open:
        weighted = amount(deal.value * deal.probability / 100, deal.currency)
        value_note = f"{weighted} at {deal.probability}%"
    else:
        value_note = deal.lost_reason or deal.get_stage_display()
    if not is_open and deal.closed_on:
        close = figure("Closed", date_format(deal.closed_on, "M j"), date_format(deal.closed_on, "Y"))
        age = figure(
            "Took", plural(max((deal.closed_on - created).days, 0), "day"), f"Since {date_format(created, 'M j, Y')}"
        )
    else:
        left = (deal.expected_close - today).days if deal.expected_close else None
        if left is None:
            close = figure("Expected close", BLANK, "No date set")
        elif left < 0:
            close = figure("Overdue by", plural(-left, "day"), f"Expected {day(deal.expected_close)}")
        else:
            close = figure("Closes in", plural(left, "day"), date_format(deal.expected_close, "D, M j, Y"))
        age = figure("Age", plural((today - created).days, "day"), f"Since {date_format(created, 'M j, Y')}")
    return {
        "steps": deal_steps(deal),
        "figures": [
            figure("Value", amount(deal.value, deal.currency), value_note),
            close,
            age,
            figure(
                "Activities",
                number(activities["count"]),
                f"Last one {timesince(activities['last'], depth=1)} ago" if activities["last"] else "None logged",
            ),
        ],
    }
