"""Names, text and dates that the seed modules of the example apps share."""

from __future__ import annotations

import random
from datetime import date, datetime, timedelta
from decimal import Decimal

from django.utils import timezone

FIRST_NAMES = [
    "Ada", "Alma", "Amara", "Anton", "Aris", "Bea", "Bruno", "Carla", "Cyril", "Dana",
    "Elif", "Emil", "Esme", "Felix", "Freya", "Gus", "Hana", "Ines", "Ivo", "Jonas",
    "Juno", "Kaito", "Lea", "Leon", "Lina", "Luca", "Maja", "Malik", "Nadia", "Nils",
    "Noor", "Olga", "Omar", "Pia", "Quinn", "Rafael", "Rosa", "Sami", "Tara", "Theo",
    "Uma", "Vera", "Wim", "Yara", "Zoe",
]  # fmt: skip

LAST_NAMES = [
    "Abe", "Alvarez", "Bauer", "Berg", "Brandt", "Costa", "Dahl", "Diallo", "Eriksen", "Ferreira",
    "Fischer", "Garcia", "Haas", "Holm", "Ibrahim", "Jansen", "Kaya", "Keller", "Kowalski", "Lang",
    "Lindqvist", "Moreau", "Mueller", "Nakamura", "Novak", "Okafor", "Ortiz", "Park", "Petrov", "Quist",
    "Rossi", "Sato", "Schmidt", "Silva", "Sorensen", "Tanaka", "Urban", "Vogel", "Weber", "Yilmaz",
]  # fmt: skip

COMPANY_WORDS = [
    "Alder", "Apex", "Arbor", "Atlas", "Beacon", "Birch", "Bright", "Cedar", "Cinder", "Cobalt",
    "Copper", "Crest", "Delta", "Ember", "Fern", "Flint", "Granite", "Harbor", "Helix", "Indigo",
    "Juniper", "Kestrel", "Lumen", "Maple", "Meridian", "Nimbus", "Northwind", "Onyx", "Orbit", "Pine",
    "Quartz", "Ridge", "Sable", "Signal", "Summit", "Tandem", "Tide", "Vector", "Willow", "Zephyr",
]  # fmt: skip

COMPANY_SUFFIXES = [
    "Labs",
    "Systems",
    "Works",
    "Group",
    "Analytics",
    "Health",
    "Robotics",
    "Studio",
    "Partners",
    "Foods",
]

CITIES = {
    "de": ["Berlin", "Hamburg", "Munich", "Cologne", "Leipzig"],
    "gb": ["London", "Leeds", "Bristol", "Glasgow"],
    "fr": ["Paris", "Lyon", "Nantes", "Lille"],
    "nl": ["Amsterdam", "Utrecht", "Rotterdam"],
    "se": ["Stockholm", "Malmo", "Uppsala"],
    "es": ["Madrid", "Valencia", "Seville"],
    "it": ["Milan", "Turin", "Bologna"],
    "pl": ["Warsaw", "Krakow", "Gdansk"],
    "us": ["Austin", "Denver", "Portland", "Chicago", "Boston"],
    "ca": ["Toronto", "Montreal", "Vancouver"],
    "jp": ["Tokyo", "Osaka", "Fukuoka"],
    "au": ["Sydney", "Melbourne", "Brisbane"],
}

STREETS = ["Main Street", "Station Road", "Harbour Way", "Linden Allee", "Park Lane", "Mill Road", "Canal Street"]

WORDS = [
    "account",
    "billing",
    "customer",
    "dashboard",
    "export",
    "feature",
    "import",
    "invoice",
    "latency",
    "login",
    "migration",
    "mobile",
    "notification",
    "onboarding",
    "payment",
    "performance",
    "permission",
    "release",
    "report",
    "review",
    "search",
    "settings",
    "signup",
    "status",
    "subscription",
    "sync",
    "team",
    "timeout",
    "upload",
    "user",
    "webhook",
    "workspace",
]


def person(rng: random.Random) -> tuple[str, str]:
    return rng.choice(FIRST_NAMES), rng.choice(LAST_NAMES)


def company_name(rng: random.Random) -> str:
    return f"{rng.choice(COMPANY_WORDS)} {rng.choice(COMPANY_SUFFIXES)}"


def address(rng: random.Random, country: str) -> str:
    return f"{rng.randint(1, 180)} {rng.choice(STREETS)}\n{rng.randint(10000, 99999)} {rng.choice(CITIES[country])}"


def sentence(rng: random.Random, words: int = 8) -> str:
    text = " ".join(rng.choice(WORDS) for _ in range(words))
    return f"{text[:1].upper()}{text[1:]}."


def paragraphs(rng: random.Random, count: int = 2) -> str:
    return "\n\n".join(
        " ".join(sentence(rng, rng.randint(6, 14)) for _ in range(rng.randint(2, 5))) for _ in range(count)
    )


def moment(rng: random.Random, days_back: int, days_ahead: int = 0) -> datetime:
    """A time between `days_back` days ago and `days_ahead` days from now."""
    seconds = rng.randint(-days_back * 86400, days_ahead * 86400)
    return timezone.now() + timedelta(seconds=seconds)


def day(rng: random.Random, days_back: int, days_ahead: int = 0) -> date:
    return timezone.localdate() + timedelta(days=rng.randint(-days_back, days_ahead))


def money(rng: random.Random, low: float, high: float) -> Decimal:
    return Decimal(f"{rng.uniform(low, high):.2f}")


def scaled(count: int, scale: float) -> int:
    return max(1, round(count * scale))
