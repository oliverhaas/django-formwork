"""Management command for django-formwork setup tasks."""

from __future__ import annotations

import contextlib
from pathlib import Path
from typing import TYPE_CHECKING, Any

from django.conf import settings
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.test.utils import override_settings

if TYPE_CHECKING:
    from argparse import ArgumentParser


def _resolve_static_dir() -> Path | None:
    """Resolve the project static directory for generated icon files.

    First entry of STATICFILES_DIRS if set, else BASE_DIR/static, else None.
    """
    static_dirs = getattr(settings, "STATICFILES_DIRS", [])
    if static_dirs:
        first = static_dirs[0]
        # Django allows STATICFILES_DIRS entries to be (prefix, path) tuples.
        if isinstance(first, (list, tuple)):
            first = first[1]
        return Path(first)
    base_dir = getattr(settings, "BASE_DIR", None)
    if base_dir is not None:
        return Path(base_dir) / "static"
    return None


class Command(BaseCommand):
    help = "Set up django-formwork dependencies."

    def add_arguments(self, parser: ArgumentParser) -> None:
        subparsers = parser.add_subparsers(dest="subcommand")
        install = subparsers.add_parser("install", help="Install required icon sets (lucide via django-iconx).")
        install.add_argument(
            "--output",
            help=(
                "Directory to write the generated icon CSS into (as iconx/icons.css). "
                "Defaults to the first STATICFILES_DIRS entry, or BASE_DIR/static if "
                "STATICFILES_DIRS is not set."
            ),
        )

    def handle(self, **options: Any) -> None:
        if options.get("subcommand") != "install":
            raise CommandError("Usage: manage.py formwork install")
        self._install(output=options.get("output"))

    def _install(self, output: str | None) -> None:
        # The icon SVGs are downloaded by `iconx add` into the first
        # STATICFILES_DIRS entry; the generated CSS goes into the project
        # static dir (or --output) so installs into read-only site-packages
        # (containers, system pip, Nix) keep working.
        static_dir = _resolve_static_dir()
        if static_dir is None:
            raise CommandError(
                "Cannot resolve a static directory for the icon files. "
                "Define STATICFILES_DIRS (or BASE_DIR) in your settings.",
            )
        css_dir = Path(output) if output else static_dir
        css_path = css_dir / "iconx" / "icons.css"

        self.stdout.write("Installing Lucide icons via django-iconx...")
        with contextlib.ExitStack() as stack:
            if not getattr(settings, "STATICFILES_DIRS", []):
                # iconx requires STATICFILES_DIRS to know where to download the
                # SVGs; inject the BASE_DIR/static fallback for the duration.
                stack.enter_context(override_settings(STATICFILES_DIRS=[str(static_dir)]))
                self.stdout.write(
                    self.style.WARNING(
                        f"STATICFILES_DIRS is not set; using {static_dir}. Add it to "
                        "STATICFILES_DIRS so Django can serve the downloaded icons.",
                    ),
                )
            try:
                call_command("iconx", "add", "lucide", "--no-generate")
                call_command("iconx", "generate", "--output", str(css_path))
            except Exception as exc:
                raise CommandError(
                    f"Icon generation via django-iconx failed: {exc}. "
                    "Ensure django-iconx is installed and in INSTALLED_APPS.",
                ) from exc
        self.stdout.write(self.style.SUCCESS(f"Icons CSS written to {css_path}"))
        self.stdout.write(self.style.SUCCESS("Formwork setup complete."))
