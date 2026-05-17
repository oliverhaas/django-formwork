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
    """Output a ``<script type="module">`` tag for the formwork bundle.

    Loads ``formwork.js`` as an ES module, which in turn imports each
    widget's Alpine.data component from ``formwork/widgets/*.js`` and
    initializes the htmx morph extension, dirty-tracking, and
    native-validation disabling.

    Users who prefer per-form loading via ``{{ form.media }}`` can do that
    instead; in that case they still need ``{% formwork_js %}`` (or an
    equivalent ``<script type="module">`` tag) for the core morph/dirty/
    validation logic.  Duplicate Alpine.data registrations are harmless
    (re-registration is idempotent).

    Usage::

        {% load formwork %}
        {% formwork_js %}
    """
    # SECURITY: safe — URL comes from Django's static file resolver, not user input.
    url = static("formwork/formwork.js")
    return mark_safe(f'<script type="module" src="{url}"></script>')  # noqa: S308
