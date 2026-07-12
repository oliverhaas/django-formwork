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
    # SECURITY: safe. URL comes from Django's static file resolver, not user input.
    url = static("formwork/formwork.css")
    return mark_safe(f'<link rel="stylesheet" href="{url}">')  # noqa: S308


@register.simple_tag
def formwork_js() -> str:
    """Output a ``<script type="module">`` tag for the formwork bundle.

    Loads ``formwork.js`` as an ES module, which imports the page-global
    core (htmx morph extension, dirty-tracking, native-validation
    disabling) and each widget's Alpine.data component from
    ``formwork/widgets/*.js``.

    For per-form loading via ``{{ form.media }}``, use
    ``{% formwork_core_js %}`` instead, which loads only the page-global
    core; widget JS is then included automatically per form via
    Django's Media plumbing.

    Usage::

        {% load formwork %}
        {% formwork_js %}
    """
    # SECURITY: safe. URL comes from Django's static file resolver, not user input.
    url = static("formwork/formwork.js")
    return mark_safe(f'<script type="module" src="{url}"></script>')  # noqa: S308


@register.simple_tag
def formwork_core_js() -> str:
    """Output a ``<script type="module">`` tag for the formwork core only.

    Loads ``formwork-core.js``: the page-global htmx morph extension,
    dirty-tracking, and native-validation disabling.  Use together with
    ``{{ form.media }}`` to load per-widget Alpine code on a per-form
    basis instead of via the full bundle.

    ``{% formwork_js %}`` already imports the core, so combining both
    tags is safe but redundant (ES module dedup by URL means the core
    only executes once).

    Usage::

        {% load formwork %}
        {% formwork_core_js %}
        {{ form.media }}
    """
    # SECURITY: safe. URL comes from Django's static file resolver, not user input.
    url = static("formwork/formwork-core.js")
    return mark_safe(f'<script type="module" src="{url}"></script>')  # noqa: S308
