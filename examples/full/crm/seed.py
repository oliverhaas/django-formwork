from __future__ import annotations

import random
from datetime import timedelta

from taskmanager import sample_data as fake
from taskmanager.models import Member

from .models import Activity, Company, Contact, Deal

TITLES = [
    "CEO",
    "CTO",
    "Head of Operations",
    "Procurement lead",
    "IT manager",
    "Finance director",
    "Office manager",
    "",
]
DEAL_KINDS = ["Annual licence", "Pilot", "Expansion", "Renewal", "Onboarding package", "Support upgrade"]
SUBJECTS = {
    Activity.Kind.CALL: ["Discovery call", "Pricing questions", "Follow-up call", "Renewal check-in"],
    Activity.Kind.EMAIL: [
        "Sent proposal",
        "Shared case study",
        "Answered security questionnaire",
        "Sent contract draft",
    ],
    Activity.Kind.MEETING: ["Onsite demo", "Quarterly review", "Kickoff meeting", "Workshop with IT"],
    Activity.Kind.NOTE: [
        "Budget approved for Q3",
        "Champion changed roles",
        "Competitor in the room",
        "Waiting for legal",
    ],
}


def clear() -> None:
    Activity.objects.all().delete()
    Deal.objects.all().delete()
    Contact.objects.all().delete()
    Company.objects.all().delete()


def seed(rng: random.Random, scale: float) -> str:
    managers = list(Member.objects.filter(employee__department__code__in=["SAL", "CS"])) or list(Member.objects.all())

    names: set[str] = set()
    while len(names) < fake.scaled(80, scale):
        names.add(fake.company_name(rng))
    companies = []
    for name in sorted(names):
        companies.append(
            Company(
                name=name,
                website=f"https://{name.split()[0].lower()}{rng.randint(1, 99)}.example" if rng.random() < 0.85 else "",
                industry=rng.choice(list(Company.Industry)),
                size=rng.choices(list(Company.Size), weights=[3, 5, 4, 2, 1])[0],
                country=rng.choice(list(fake.CITIES)),
                account_manager=rng.choice(managers) if rng.random() < 0.9 else None,
                annual_revenue=fake.money(rng, 2e5, 9e7) if rng.random() < 0.7 else None,
                created_at=fake.moment(rng, 1100),
                notes=fake.paragraphs(rng, 1) if rng.random() < 0.3 else "",
            )
        )
    Company.objects.bulk_create(companies)
    companies = list(Company.objects.all())

    contacts = []
    emails: set[str] = set()
    for company in companies:
        domain = company.name.split()[0].lower()
        for index in range(rng.randint(1, 6)):
            first, last = fake.person(rng)
            email = f"{first}.{last}@{domain}.example".lower()
            if email in emails:
                continue
            emails.add(email)
            contacts.append(
                Contact(
                    company=company,
                    first_name=first,
                    last_name=last,
                    email=email,
                    phone=f"+49 30 {rng.randint(1000000, 9999999)}" if rng.random() < 0.6 else "",
                    job_title=rng.choice(TITLES),
                    is_primary=index == 0,
                    newsletter=rng.random() < 0.4,
                    last_contacted=fake.moment(rng, 200) if rng.random() < 0.7 else None,
                )
            )
    Contact.objects.bulk_create(contacts)
    contacts_by_company: dict[int, list[Contact]] = {}
    for contact in Contact.objects.all():
        contacts_by_company.setdefault(contact.company_id, []).append(contact)

    deals = []
    for _ in range(fake.scaled(320, scale)):
        company = rng.choice(companies)
        stage = rng.choices(list(Deal.Stage), weights=[5, 4, 3, 2, 4, 3])[0]
        closed = stage in (Deal.Stage.WON, Deal.Stage.LOST)
        expected_close = fake.day(rng, 120, 180)
        deals.append(
            Deal(
                name=f"{company.name.split()[0]} {rng.choice(DEAL_KINDS).lower()}",
                company=company,
                contact=rng.choice(contacts_by_company.get(company.pk, [None])),
                owner=company.account_manager or rng.choice(managers),
                stage=stage,
                value=fake.money(rng, 1_500, 240_000),
                currency=rng.choices(["EUR", "USD", "GBP"], weights=[6, 3, 1])[0],
                probability={"lead": 10, "qualified": 25, "proposal": 50, "negotiation": 75, "won": 100, "lost": 0}[
                    stage
                ],
                expected_close=expected_close,
                closed_on=expected_close - timedelta(days=rng.randint(0, 20)) if closed else None,
                lost_reason=rng.choice(["Budget", "Went with a competitor", "No decision", "Timing"])
                if stage == Deal.Stage.LOST
                else "",
                created_at=fake.moment(rng, 400),
            )
        )
    Deal.objects.bulk_create(deals)
    deals = list(Deal.objects.all())

    activities = []
    for _ in range(fake.scaled(900, scale)):
        deal = rng.choice(deals)
        kind = rng.choice(list(Activity.Kind))
        activities.append(
            Activity(
                company_id=deal.company_id,
                deal=deal if rng.random() < 0.8 else None,
                contact=deal.contact,
                kind=kind,
                subject=rng.choice(SUBJECTS[kind]),
                body=fake.paragraphs(rng, 1) if rng.random() < 0.5 else "",
                occurred_at=fake.moment(rng, 300),
                duration=timedelta(minutes=rng.choice([15, 30, 45, 60, 90])) if kind in ("call", "meeting") else None,
                logged_by=deal.owner,
            )
        )
    Activity.objects.bulk_create(activities)
    return f"{len(companies)} companies, {len(contacts)} contacts, {len(deals)} deals, {len(activities)} activities"
