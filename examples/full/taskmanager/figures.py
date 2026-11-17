"""What the admin's slots share: number formats, the tiles of a card and the colors of a chart.

templates/charts/ has the templates: stats.html for a list, figures.html for a change page.
"""

from datetime import timedelta

from django.utils import timezone
from django.utils.formats import date_format, number_format

# A longer range shows its last months.
MONTHS = 24

# Whole class names, so Tailwind finds them.
BARS = {
    "primary": "progress-primary",
    "info": "progress-info",
    "warning": "progress-warning",
    "success": "progress-success",
    "error": "progress-error",
    "neutral": "",
}
STEPS = {"primary": "step-primary", "success": "step-success", "error": "step-error", "neutral": ""}

SYMBOLS = {"EUR": "€", "USD": "$", "GBP": "£"}

# The value of a figure that has none.
BLANK = "\N{EN DASH}"


def number(value):
    return number_format(value, force_grouping=True)


def percent(part, whole):
    return round(100 * part / whole) if whole else None


def compact(value, digits=3):
    """A large number in a few digits: 14.2M, 310k."""
    value = float(value)
    for limit, suffix in ((1_000_000, "M"), (1_000, "k")):
        if abs(value) >= limit:
            return f"{float(f'{value / limit:.{digits}g}'):g}{suffix}"
    return f"{value:.0f}"


def money(amounts):
    """The sums of a ``{currency: amount}`` dict in short, the largest first: ["€14.2M", "$7.1M"].

    The first one is the value of a tile and the others go into its note, so they have a digit less.
    """
    ranked = sorted((item for item in amounts.items() if item[1]), key=lambda item: -item[1])
    return [
        f"{SYMBOLS.get(currency, f'{currency} ')}{compact(amount, 2 if index else 3)}"
        for index, (currency, amount) in enumerate(ranked)
    ]


def amount(value, currency):
    """One amount in full, without its cents: €12,431."""
    return f"{SYMBOLS.get(currency, f'{currency} ')}{number(round(value))}"


def span(delta):
    """A duration in its largest unit: 12 days, 3.5 days, 5 hours, 40 min."""
    if delta >= timedelta(days=10):
        return f"{delta / timedelta(days=1):.0f} days"
    if delta >= timedelta(days=2):
        return f"{delta / timedelta(days=1):.1f}".removesuffix(".0") + " days"
    if delta >= timedelta(hours=1):
        return plural(round(delta / timedelta(hours=1)), "hour")
    return f"{max(delta / timedelta(minutes=1), 0):.0f} min"


def day(value):
    """A date in short. The year shows when it is not this one: Oct 15, Oct 15, 2025."""
    return date_format(value, "M j" if value.year == timezone.localdate().year else "M j, Y")


def plural(count, noun):
    """A count with its noun: 1 day, 2,400 days."""
    return f"{number(count)} {noun}{'' if count == 1 else 's'}"


def bar(share, color="primary"):
    """The bar under a figure's value, filled to ``share`` percent."""
    return {"share": share, "class": BARS[color]}


def figure(label, value, note, bar=None, *, of=None):
    """A tile of a card. ``of`` is the whole that the value is a part of, as in 4 / 5."""
    return {"label": label, "value": value, "note": note, "bar": bar, "of": of}


def step(label, color="neutral", mark="", *, current=False):
    """A step of a pipeline. ``mark`` shows in the step's circle in place of its number."""
    return {"label": label, "class": STEPS[color], "mark": mark, "current": current}


def steps(names, current, *, color="primary", closed=False):
    """The steps of a pipeline over a card's tiles. Those up to ``current``, an index, are in ``color``.

    A step that is over has a tick. In a closed pipeline, that includes the current step.
    """
    return [
        step(
            name,
            color if index <= current else "neutral",
            "✓" if index < current or (closed and index == current) else "",
            current=index == current,
        )
        for index, name in enumerate(names)
    ]


def token(color):
    """The chart color of a badge color."""
    return "--color-base-content/25" if color == "neutral" else f"--color-{color}"


def legend(*entries, line=False):
    """The legend of a chart from ``(label, chart color)``, with the color as CSS."""
    items = []
    for label, color in entries:
        name, _, alpha = color.partition("/")
        css = f"color-mix(in oklab, var({name}) {alpha}%, transparent)" if alpha else f"var({name})"
        items.append({"label": label, "css": css, "line": line})
    return items


def months_between(first, last):
    """Each month's first day from ``first`` to ``last``, the last ``MONTHS`` of them."""
    months = [first]
    while (month := months[-1]) < last:
        months.append(month.replace(year=month.year + month.month // 12, month=month.month % 12 + 1))
    return months[-MONTHS:]


def month_labels(months):
    """The axis labels of months. The year shows under the first month and under each January."""
    return [
        [date_format(month, "M"), date_format(month, "Y") if index == 0 or month.month == 1 else ""]
        for index, month in enumerate(months)
    ]


def stacked(*series):
    """The datasets of stacked columns from ``(label, data, chart color)``, the bottom one first.

    The top segment of a column is round, and a gap in the card's color parts two segments.
    """
    top = {"topLeft": 3, "topRight": 3}
    columns = list(zip(*(data for _, data, _ in series), strict=True))
    return [
        {
            "label": label,
            "data": data,
            "backgroundColor": color,
            "borderRadius": [0 if any(column[index + 1 :]) else top for column in columns],
            "borderColor": "--color-base-100",
            "borderWidth": [{"bottom": 2} if any(column[:index]) else 0 for column in columns],
            "borderSkipped": False,
            "maxBarThickness": 24,
        }
        for index, (label, data, color) in enumerate(series)
    ]
