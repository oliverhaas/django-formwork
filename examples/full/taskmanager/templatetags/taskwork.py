from datetime import datetime, timedelta

from django import template
from django.utils import timezone
from django.utils.timesince import timesince

register = template.Library()


@register.filter
def ago(value: datetime) -> str:
    """The time since ``value`` in its largest unit: 5 minutes ago, 3 days ago."""
    if timezone.now() - value < timedelta(minutes=1):
        return "just now"
    return f"{timesince(value, depth=1)} ago"


@register.filter
def badge(color: str) -> str:
    """Badge classes for a color. Neutral is a ghost badge, as in the admin list."""
    return "badge-ghost" if color == "neutral" else f"badge-soft badge-{color}"
