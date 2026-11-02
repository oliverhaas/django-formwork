"""Section forms: forms on one page that each save their own fields of one row.

Each ``<form data-section-form>`` posts its name through ``{% formwork_section "name" %}``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from django.core.exceptions import BadRequest

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping

    from django.forms import BaseForm
    from django.http import HttpRequest

__all__ = ["SECTION_INPUT_NAME", "section_forms"]

#: Hidden input that names the section a post saves.
SECTION_INPUT_NAME = "_formwork_section"


def section_forms[F: BaseForm](
    request: HttpRequest, sections: Mapping[str, Callable[..., F]], /, **kwargs: Any
) -> dict[str, F]:
    """Build every section's form, bound only for the section a POST names.

    ``kwargs`` go to each form (``instance=``).  A POST naming no known section raises ``BadRequest``.
    """
    posted = None
    if request.method == "POST":
        posted = request.POST.get(SECTION_INPUT_NAME)
        if posted not in sections:
            msg = f"The post names no known section: {posted!r}."
            raise BadRequest(msg)
    return {
        name: form_class(data=request.POST, files=request.FILES, **kwargs) if name == posted else form_class(**kwargs)
        for name, form_class in sections.items()
    }
