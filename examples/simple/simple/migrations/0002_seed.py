"""Seed a few people and one legacy ticket for the cookbook example."""

from django.db import migrations

PEOPLE = [
    ("Ada Lovelace", "ada@example.com"),
    ("Alan Turing", "alan@example.com"),
    ("Grace Hopper", "grace@example.com"),
    ("Katherine Johnson", "katherine@example.com"),
    ("Dennis Ritchie", "dennis@example.com"),
    ("Barbara Liskov", "barbara@example.com"),
]


def seed(apps, schema_editor):  # noqa: ARG001
    Person = apps.get_model("simple", "Person")
    Ticket = apps.get_model("simple", "Ticket")
    people = [Person.objects.create(name=n, email=e) for n, e in PEOPLE]
    # A ticket whose title would fail today's validator. Saved directly
    # (no full_clean), so it lands in the DB as legacy data. The cookbook's
    # edit step shows validate_dirty_only leaving it untouched.
    Ticket.objects.create(
        title="LEGACY",
        assignee=people[0],
        priority="high",
        description="An older ticket whose title predates current validation.",
    )


def unseed(apps, schema_editor):  # noqa: ARG001
    apps.get_model("simple", "Ticket").objects.all().delete()
    apps.get_model("simple", "Person").objects.all().delete()


class Migration(migrations.Migration):
    dependencies = [("simple", "0001_initial")]
    operations = [migrations.RunPython(seed, unseed)]
