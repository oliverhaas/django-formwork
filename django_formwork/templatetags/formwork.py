from django import template
from django.templatetags.static import static
from django.utils.html import format_html

register = template.Library()


@register.simple_tag
def formwork_css() -> str:
    """Output a ``<link>`` tag for the formwork bridge CSS.

    Usage::

        {% load formwork %}
        {% formwork_css %}
    """
    return format_html('<link rel="stylesheet" href="{}">', static("formwork/formwork.css"))


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
    return format_html('<script type="module" src="{}"></script>', static("formwork/formwork.js"))


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
    return format_html('<script type="module" src="{}"></script>', static("formwork/formwork-core.js"))


@register.filter
def attr(attrs: dict, key: str) -> str:
    """Look up a widget attr by its literal (possibly hyphenated) key.

    DTL cannot traverse hyphenated keys via dot syntax
    (``widget.attrs.aria-invalid`` is a syntax error) and has no
    subscript form, so this filter bridges the gap for keys like
    ``aria-invalid`` / ``aria-describedby`` that Django writes onto a
    widget's attrs.  Jinja2 templates use native subscription instead.
    """
    return attrs.get(key, "")
