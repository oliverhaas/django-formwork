"""Reset the example database and fill every app with sample data."""

from __future__ import annotations

import random
from importlib import import_module

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.db import transaction

APPS = ["taskmanager", "people", "crm", "billing", "helpdesk", "recruiting", "events", "content"]


class Command(BaseCommand):
    help = "Reset the database and populate every example app with sample data."

    def add_arguments(self, parser):
        parser.add_argument(
            "--scale", type=float, default=1.0, help="Multiply the row counts, e.g. 0.1 for a small set."
        )
        parser.add_argument("--seed", type=int, default=1, help="Random seed, so two runs give the same data.")

    @transaction.atomic
    def handle(self, *args, scale: float, seed: int, **options):  # noqa: ARG002
        modules = [import_module(f"{app}.seed") for app in APPS]
        for module in reversed(modules):
            module.clear()
        rng = random.Random(seed)  # noqa: S311
        for app, module in zip(APPS, modules, strict=True):
            self.stdout.write(f"{app}: {module.seed(rng, scale)}")
        if not User.objects.filter(username="admin").exists():
            User.objects.create_superuser("admin", "admin@example.com", "admin")
        self.stdout.write(self.style.SUCCESS("Done. Log in to /admin/ as admin, password admin."))
