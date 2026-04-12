"""Management command for django-formwork setup tasks."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

from django.core.management import call_command
from django.core.management.base import BaseCommand

if TYPE_CHECKING:
    from argparse import ArgumentParser

# iconx CSS is generated into formwork's static directory so that
# formwork.css can import it with a stable relative path.
_ICONS_OUTPUT = str(Path(__file__).resolve().parent.parent.parent / "static" / "iconx" / "icons.css")


class Command(BaseCommand):
    help = "Set up django-formwork dependencies."

    def add_arguments(self, parser: ArgumentParser) -> None:
        subparsers = parser.add_subparsers(dest="subcommand")
        subparsers.add_parser("install", help="Install required icon sets (lucide via django-iconx).")

    def handle(self, **options: Any) -> None:
        subcommand = options.get("subcommand")
        if subcommand == "install":
            self._install()
        else:
            self.stderr.write("Usage: manage.py formwork install")

    def _install(self) -> None:
        self.stdout.write("Installing Lucide icons via django-iconx...")
        call_command("iconx", "add", "lucide")
        call_command("iconx", "generate", "--output", _ICONS_OUTPUT)
        self.stdout.write(self.style.SUCCESS(f"Icons CSS written to {_ICONS_OUTPUT}"))
        self.stdout.write(self.style.SUCCESS("Formwork setup complete."))
