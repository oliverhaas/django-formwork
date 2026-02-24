from django import template
from django.templatetags.static import static
from django.utils.safestring import mark_safe

register = template.Library()


@register.simple_tag
def formwork_css() -> str:
    """Output a ``<link>`` tag for the formwork bridge CSS.

    Usage::

        {% load formwork %}
        {% formwork_css %}
    """
    url = static("formwork/formwork.css")
    return mark_safe(f'<link rel="stylesheet" href="{url}">')  # noqa: S308
