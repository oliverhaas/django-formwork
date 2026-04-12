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
    # SECURITY: safe — URL comes from Django's static file resolver, not user input.
    url = static("formwork/formwork.css")
    return mark_safe(f'<link rel="stylesheet" href="{url}">')  # noqa: S308


@register.simple_tag
def formwork_js() -> str:
    """Output a ``<script>`` tag for the formwork idiomorph helper.

    Usage::

        {% load formwork %}
        {% formwork_js %}
    """
    # SECURITY: safe — URL comes from Django's static file resolver, not user input.
    url = static("formwork/formwork.js")
    return mark_safe(f'<script src="{url}"></script>')  # noqa: S308
