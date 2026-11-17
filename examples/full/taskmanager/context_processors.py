"""Template context processors for the example."""

from __future__ import annotations

from django.utils.functional import SimpleLazyObject

from .models import Profile

DAISYUI_THEMES = [
    "cupcake",
    "light",
    "dark",
    "emerald",
    "corporate",
    "synthwave",
    "retro",
    "valentine",
    "garden",
    "forest",
    "aqua",
    "pastel",
    "fantasy",
    "dracula",
    "autumn",
    "business",
    "lemonade",
    "night",
    "coffee",
    "winter",
    "nord",
    "sunset",
]


def nav(request) -> dict[str, object]:
    """Expose the current nav section, the theme list and the member you are to all templates."""
    path = request.path
    if path.startswith("/tasks"):
        section = "board"
    elif path.startswith("/wizard"):
        section = "wizard"
    elif path.startswith("/settings"):
        section = "settings"
    else:
        section = "dashboard"
    return {
        "nav_section": section,
        "theme_names": DAISYUI_THEMES,
        "profile": SimpleLazyObject(Profile.load),
    }
