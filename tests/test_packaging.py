import os
import subprocess
import sys
from pathlib import Path

import pytest


@pytest.mark.unit
def test_py_typed_marker_exists():
    """py.typed marker file exists for PEP 561 compliance."""
    marker = Path(__file__).parent.parent / "django_formwork" / "py.typed"
    assert marker.exists()


# ---------------------------------------------------------------------------
# Top-level import surface (lazy re-exports via module __getattr__)
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_all_public_names_resolve_from_top_level():
    """Every name in __all__ resolves from the package root."""
    import django_formwork

    for name in django_formwork.__all__:
        assert getattr(django_formwork, name) is not None


@pytest.mark.unit
def test_all_matches_lazy_export_map():
    """__all__ and the lazy _EXPORTS map stay in sync."""
    import django_formwork

    assert set(django_formwork.__all__) == {"__version__", *django_formwork._EXPORTS}


@pytest.mark.unit
def test_top_level_names_match_submodule_objects():
    """Lazy re-exports are the same objects as their submodule originals."""
    import django_formwork
    from django_formwork import forms, formsets, models, renderers, views

    assert django_formwork.FormworkForm is forms.FormworkForm
    assert django_formwork.FormworkModelForm is forms.FormworkModelForm
    assert django_formwork.FormworkModel is models.FormworkModel
    assert django_formwork.FormworkRenderer is renderers.FormworkRenderer
    assert django_formwork.FormworkBaseModelFormSet is formsets.FormworkBaseModelFormSet
    assert django_formwork.formwork_modelformset_factory is formsets.formwork_modelformset_factory
    assert django_formwork.FormworkSearchView is views.FormworkSearchView
    assert django_formwork.FormworkValidateView is views.FormworkValidateView


@pytest.mark.unit
def test_async_mixins_resolve_from_top_level():
    from django_formwork import AsyncFormMixin, AsyncModelFormMixin, async_forms

    assert AsyncFormMixin is async_forms.AsyncFormMixin
    assert AsyncModelFormMixin is async_forms.AsyncModelFormMixin


@pytest.mark.unit
def test_unknown_attribute_raises_attribute_error():
    import django_formwork

    with pytest.raises(AttributeError, match="does_not_exist"):
        django_formwork.does_not_exist  # noqa: B018


@pytest.mark.unit
def test_dir_lists_lazy_exports():
    """dir() advertises the lazy names even before first access."""
    import django_formwork

    listing = dir(django_formwork)
    assert "FormworkModel" in listing
    assert "FormworkForm" in listing
    assert "formwork_inlineformset_factory" in listing


@pytest.mark.unit
def test_form_renderer_setting_path_resolves():
    """FORM_RENDERER = "django_formwork.FormworkRenderer" works via import_string."""
    from django.utils.module_loading import import_string

    from django_formwork.renderers import FormworkRenderer

    assert import_string("django_formwork.FormworkRenderer") is FormworkRenderer


@pytest.mark.unit
def test_import_without_django_setup():
    """`import django_formwork` succeeds in a subprocess with no
    DJANGO_SETTINGS_MODULE (lazy exports keep FormworkModel out of import time).
    """
    env = {k: v for k, v in os.environ.items() if k != "DJANGO_SETTINGS_MODULE"}
    result = subprocess.run(
        [sys.executable, "-c", "import django_formwork; print(django_formwork.__version__)"],
        capture_output=True,
        text=True,
        env=env,
        cwd=Path(__file__).parent.parent,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip()
