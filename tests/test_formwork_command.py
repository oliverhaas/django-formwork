"""Tests for the `manage.py formwork` management command."""

from io import StringIO

import pytest
from django.conf import settings as django_settings
from django.core.management import call_command
from django.core.management.base import CommandError

from django_formwork.management.commands import formwork as formwork_command

SVG = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24"><path d="M0 0h24v24H0z"/></svg>'


@pytest.fixture
def iconx_calls(monkeypatch):
    """Record the call_command invocations the formwork command delegates to iconx."""
    calls = []

    def record(name, *args, **kwargs):
        calls.append((name, *args))

    monkeypatch.setattr(formwork_command, "call_command", record)
    return calls


# ─── output location resolution ─────────────────────────────────────────


@pytest.mark.unit
def test_install_writes_css_into_first_staticfiles_dir(iconx_calls, settings, tmp_path):
    settings.STATICFILES_DIRS = [str(tmp_path / "assets")]
    stdout = StringIO()

    call_command("formwork", "install", stdout=stdout)

    expected = str(tmp_path / "assets" / "iconx" / "icons.css")
    assert iconx_calls == [
        ("iconx", "add", "lucide", "--no-generate"),
        ("iconx", "generate", "--output", expected),
    ]
    assert expected in stdout.getvalue()
    assert "Formwork setup complete." in stdout.getvalue()


@pytest.mark.unit
def test_install_handles_prefixed_staticfiles_dir_tuple(iconx_calls, settings, tmp_path):
    settings.STATICFILES_DIRS = [("prefix", str(tmp_path / "assets"))]

    call_command("formwork", "install", stdout=StringIO())

    expected = str(tmp_path / "assets" / "iconx" / "icons.css")
    assert iconx_calls[1] == ("iconx", "generate", "--output", expected)


@pytest.mark.unit
def test_install_falls_back_to_base_dir_static(iconx_calls, settings, tmp_path, monkeypatch):
    settings.STATICFILES_DIRS = []
    settings.BASE_DIR = tmp_path
    # Record what iconx sees for STATICFILES_DIRS: the command must inject the
    # fallback so `iconx add` knows where to download the SVGs.
    seen_dirs = []

    def record(name, *args, **kwargs):
        seen_dirs.append(list(django_settings.STATICFILES_DIRS))

    monkeypatch.setattr(formwork_command, "call_command", record)
    stdout = StringIO()

    call_command("formwork", "install", stdout=stdout)

    expected = str(tmp_path / "static" / "iconx" / "icons.css")
    assert expected in stdout.getvalue()
    assert seen_dirs == [[str(tmp_path / "static")], [str(tmp_path / "static")]]
    assert "STATICFILES_DIRS is not set" in stdout.getvalue()


@pytest.mark.unit
def test_install_restores_staticfiles_dirs_after_fallback(iconx_calls, settings, tmp_path):
    settings.STATICFILES_DIRS = []
    settings.BASE_DIR = tmp_path

    call_command("formwork", "install", stdout=StringIO())

    assert django_settings.STATICFILES_DIRS == []


@pytest.mark.unit
def test_install_output_option_overrides_css_location(iconx_calls, settings, tmp_path):
    settings.STATICFILES_DIRS = [str(tmp_path / "assets")]
    stdout = StringIO()

    call_command("formwork", "install", "--output", str(tmp_path / "custom"), stdout=stdout)

    expected = str(tmp_path / "custom" / "iconx" / "icons.css")
    assert iconx_calls == [
        ("iconx", "add", "lucide", "--no-generate"),
        ("iconx", "generate", "--output", expected),
    ]
    assert expected in stdout.getvalue()


@pytest.mark.unit
def test_install_without_staticfiles_dirs_or_base_dir_errors(iconx_calls, settings):
    settings.STATICFILES_DIRS = []
    assert not hasattr(django_settings, "BASE_DIR")

    with pytest.raises(CommandError, match="STATICFILES_DIRS"):
        call_command("formwork", "install")

    assert iconx_calls == []


# ─── command surface ────────────────────────────────────────────────────


@pytest.mark.unit
def test_missing_subcommand_errors(iconx_calls):
    with pytest.raises(CommandError, match=r"Usage: manage\.py formwork install"):
        call_command("formwork")

    assert iconx_calls == []


@pytest.mark.unit
def test_install_wraps_iconx_failure_in_command_error(settings, tmp_path, monkeypatch):
    settings.STATICFILES_DIRS = [str(tmp_path)]

    def boom(name, *args, **kwargs):
        raise RuntimeError("network down")

    monkeypatch.setattr(formwork_command, "call_command", boom)

    with pytest.raises(CommandError, match="django-iconx"):
        call_command("formwork", "install")


# ─── end-to-end CSS generation (real iconx generate, download mocked) ───


@pytest.fixture
def static_dir_with_svg(tmp_path, monkeypatch):
    """A static dir pre-seeded with one Lucide-style SVG; `iconx add` is skipped."""
    static_dir = tmp_path / "static"
    (static_dir / "icons" / "lucide").mkdir(parents=True)
    (static_dir / "icons" / "lucide" / "search.svg").write_text(SVG)

    real_call_command = formwork_command.call_command

    def skip_download(name, *args, **kwargs):
        if args and args[0] == "add":
            return None
        return real_call_command(name, *args, **kwargs)

    monkeypatch.setattr(formwork_command, "call_command", skip_download)
    return static_dir


@pytest.mark.integration
def test_install_generates_icons_css_from_svgs(static_dir_with_svg, settings):
    settings.STATICFILES_DIRS = [str(static_dir_with_svg)]

    call_command("formwork", "install", stdout=StringIO())

    css = (static_dir_with_svg / "iconx" / "icons.css").read_text()
    assert ".icon-search" in css
    assert "/static/icons/lucide/search.svg" in css


@pytest.mark.integration
def test_install_is_idempotent(static_dir_with_svg, settings):
    settings.STATICFILES_DIRS = [str(static_dir_with_svg)]
    css_path = static_dir_with_svg / "iconx" / "icons.css"

    call_command("formwork", "install", stdout=StringIO())
    first = css_path.read_text()
    stdout = StringIO()
    call_command("formwork", "install", stdout=stdout)

    assert css_path.read_text() == first
    assert str(css_path) in stdout.getvalue()


@pytest.mark.integration
def test_install_output_option_writes_outside_staticfiles_dirs(static_dir_with_svg, settings, tmp_path):
    settings.STATICFILES_DIRS = [str(static_dir_with_svg)]
    output_dir = tmp_path / "build"

    call_command("formwork", "install", "--output", str(output_dir), stdout=StringIO())

    assert (output_dir / "iconx" / "icons.css").exists()
    assert not (static_dir_with_svg / "iconx" / "icons.css").exists()
