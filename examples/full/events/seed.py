from __future__ import annotations

import random
from datetime import timedelta
from decimal import Decimal

from crm.models import Contact
from django.utils import timezone
from django.utils.text import slugify
from taskmanager import sample_data as fake
from taskmanager.models import Member

from .models import Event, Registration, Venue

VENUES = [
    ("Online", True, "", "", None),
    ("Kraftwerk Hall", False, "Berlin", "de", 600),
    ("The Foundry", False, "London", "gb", 250),
    ("Canal House", False, "Amsterdam", "nl", 120),
    ("Atelier Nord", False, "Paris", "fr", 80),
    ("Harbour Loft", False, "Hamburg", "de", 60),
    ("Riverside Center", False, "Austin", "us", 900),
    ("Meeting room 3", False, "Berlin", "de", 18),
]
TOPICS = [
    "Getting started with",
    "Advanced reporting in",
    "Scaling your team with",
    "What's new in",
    "Office hours:",
    "Admin deep dive:",
    "Security review of",
    "Migrating your data to",
]
PRODUCT_NAMES = ["Taskwork", "Taskwork API", "Taskwork for teams", "the Taskwork mobile app"]
PRICES = {
    Event.Kind.WEBINAR: [0],
    Event.Kind.MEETUP: [0],
    Event.Kind.WORKSHOP: [0, 49, 99, 149],
    Event.Kind.CONFERENCE: [199, 349, 499],
}
DIETARY = ["Vegetarian", "Vegan", "No nuts", "Gluten free", "Halal"]


def clear() -> None:
    Registration.objects.all().delete()
    Event.objects.all().delete()
    Venue.objects.all().delete()


def seed(rng: random.Random, scale: float) -> str:
    venues = Venue.objects.bulk_create(
        Venue(
            name=name,
            is_virtual=virtual,
            city=city,
            country=country.upper(),
            address=fake.address(rng, country) if country else "",
            url="https://live.taskwork.example" if virtual else "",
            capacity=capacity,
        )
        for name, virtual, city, country, capacity in VENUES
    )
    online, physical = venues[0], venues[1:]
    hosts = list(Member.objects.all())
    contacts = list(Contact.objects.only("pk"))

    now = timezone.now()
    events = []
    slugs: set[str] = set()
    for _ in range(fake.scaled(120, scale)):
        kind = rng.choices(list(Event.Kind), weights=[8, 4, 3, 1])[0]
        title = f"{rng.choice(TOPICS)} {rng.choice(PRODUCT_NAMES)}"
        starts_at = fake.moment(rng, 400, 120).replace(minute=0, second=0, microsecond=0)
        hours = {Event.Kind.WEBINAR: 1, Event.Kind.MEETUP: 3, Event.Kind.WORKSHOP: 6, Event.Kind.CONFERENCE: 30}[kind]
        venue = online if kind == Event.Kind.WEBINAR else rng.choice(physical)
        slug = slugify(f"{title} {starts_at:%Y-%m-%d}")
        if slug in slugs:
            continue
        slugs.add(slug)
        events.append(
            Event(
                title=title,
                slug=slug,
                kind=kind,
                venue=venue,
                host=rng.choice(hosts),
                starts_at=starts_at,
                ends_at=starts_at + timedelta(hours=hours),
                capacity=venue.capacity if venue.capacity and rng.random() < 0.8 else None,
                price=Decimal(rng.choice(PRICES[kind])),
                is_published=starts_at < now or rng.random() < 0.7,
                description=fake.paragraphs(rng, 2),
            )
        )
    Event.objects.bulk_create(events)

    registrations = []
    for event in events:
        limit = event.capacity or 300
        wanted = min(len(contacts), rng.randint(limit // 4, limit + limit // 5))
        past = event.starts_at < now
        for index, contact in enumerate(rng.sample(contacts, wanted)):
            registered_at = min(now, event.starts_at - timedelta(days=rng.randint(0, 40), hours=rng.randint(0, 23)))
            if index >= limit:
                status = Registration.Status.WAITLIST
            elif rng.random() < 0.08:
                status = Registration.Status.CANCELLED
            elif past:
                status = rng.choices([Registration.Status.ATTENDED, Registration.Status.NO_SHOW], weights=[4, 1])[0]
            else:
                status = Registration.Status.REGISTERED
            attended = status == Registration.Status.ATTENDED
            registrations.append(
                Registration(
                    event=event,
                    contact=contact,
                    status=status,
                    registered_at=registered_at,
                    checked_in_at=event.starts_at + timedelta(minutes=rng.randint(-30, 45)) if attended else None,
                    dietary_needs=rng.choice(DIETARY)
                    if event.kind != Event.Kind.WEBINAR and rng.random() < 0.15
                    else "",
                )
            )
    Registration.objects.bulk_create(registrations)
    return f"{len(venues)} venues, {len(events)} events, {len(registrations)} registrations"
