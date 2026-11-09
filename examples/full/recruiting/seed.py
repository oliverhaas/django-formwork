from __future__ import annotations

import random
from datetime import timedelta

from django.utils import timezone
from people.models import Department, Employee
from taskmanager import sample_data as fake
from taskmanager.models import Member

from .models import Application, Candidate, Interview, Opening

OPENINGS = {
    "ENG": [
        "Senior backend engineer",
        "Frontend engineer",
        "Site reliability engineer",
        "Engineering manager",
        "Data engineer",
    ],
    "DES": ["Product designer", "UX researcher", "Design systems lead"],
    "SAL": ["Account executive", "Sales development rep", "Solutions engineer"],
    "CS": ["Support agent", "Customer success manager", "Technical support lead"],
    "FIN": ["Financial analyst", "Payroll specialist"],
    "PPL": ["Recruiter", "People partner"],
    "OPS": ["Office manager", "IT administrator", "Workplace coordinator"],
}
QUESTIONS = [
    "Why do you want to join us?",
    "What is your notice period?",
    "Do you need a visa to work here?",
    "Which time zone do you work from?",
    "What are your salary expectations?",
]
REJECTIONS = [
    "Not enough experience",
    "Salary expectations too high",
    "Withdrew",
    "Position filled",
    "No show",
    "Location",
]


def clear() -> None:
    Interview.objects.all().delete()
    Application.objects.all().delete()
    Candidate.objects.all().delete()
    Opening.objects.all().delete()


def seed(rng: random.Random, scale: float) -> str:
    departments = {department.code: department for department in Department.objects.all()}
    members = list(Member.objects.all())
    recruiters = list(Member.objects.filter(employee__department__code="PPL")) or members

    openings = []
    for code, titles in OPENINGS.items():
        for title in titles:
            for _ in range(fake.scaled(rng.randint(1, 2), scale)):
                salary_min = rng.randrange(40_000, 110_000, 5_000)
                openings.append(
                    Opening(
                        title=title,
                        department=departments[code],
                        hiring_manager=rng.choice(members),
                        status=rng.choices(list(Opening.Status), weights=[2, 10, 2, 4, 3])[0],
                        workplace=rng.choice(list(Opening.Workplace)),
                        employment_type=rng.choices(list(Employee.Type), weights=[12, 2, 2, 1])[0],
                        headcount=rng.choices([1, 2, 3], weights=[8, 2, 1])[0],
                        salary_min=salary_min,
                        salary_max=salary_min + rng.randrange(10_000, 40_000, 5_000),
                        opened_on=fake.day(rng, 240),
                        description=fake.paragraphs(rng, 3),
                        screening_questions=rng.sample(QUESTIONS, rng.randint(0, 3)),
                    )
                )
    for opening in openings:
        if rng.random() < 0.6:
            opening.closes_on = opening.opened_on + timedelta(days=rng.choice([30, 45, 60, 90]))
    Opening.objects.bulk_create(openings)

    emails: set[str] = set()
    candidates = []
    while len(candidates) < fake.scaled(900, scale):
        first, last = fake.person(rng)
        email = f"{first}.{last}{rng.randint(1, 999)}@mail.example".lower()
        if email in emails:
            continue
        emails.add(email)
        country = rng.choice(list(fake.CITIES))
        source = rng.choices(list(Candidate.Source), weights=[2, 8, 6, 3, 1])[0]
        candidates.append(
            Candidate(
                first_name=first,
                last_name=last,
                email=email,
                phone=f"+{rng.randint(1, 49)} {rng.randint(100, 999)} {rng.randint(100000, 9999999)}"
                if rng.random() < 0.7
                else "",
                city=rng.choice(fake.CITIES[country]),
                country=country,
                profile_url=f"https://profiles.example/{first}-{last}".lower() if rng.random() < 0.6 else "",
                source=source,
                referred_by=rng.choice(members) if source == Candidate.Source.REFERRAL else None,
                resume=f"resumes/{first}-{last}.pdf".lower() if rng.random() < 0.8 else "",
                created_at=fake.moment(rng, 240),
            )
        )
    Candidate.objects.bulk_create(candidates)

    now = timezone.now()
    applications = []
    for candidate in candidates:
        for opening in rng.sample(openings, rng.choices([1, 2, 3], weights=[10, 3, 1])[0]):
            applied_at = max(candidate.created_at, fake.moment(rng, 200))
            stage = rng.choices(list(Application.Stage), weights=[10, 6, 5, 2, 1, 12])[0]
            applications.append(
                Application(
                    candidate=candidate,
                    opening=opening,
                    stage=stage,
                    owner=rng.choice(recruiters),
                    applied_at=applied_at,
                    moved_at=applied_at
                    if stage == Application.Stage.APPLIED
                    else applied_at + (now - applied_at) * rng.random(),
                    rating=rng.randint(1, 5) if stage != Application.Stage.APPLIED and rng.random() < 0.7 else None,
                    rejection_reason=rng.choice(REJECTIONS) if stage == Application.Stage.REJECTED else "",
                )
            )
    Application.objects.bulk_create(applications)

    rounds = {
        Application.Stage.SCREEN: 1,
        Application.Stage.INTERVIEW: 2,
        Application.Stage.OFFER: 3,
        Application.Stage.HIRED: 4,
    }
    interviews = []
    for application in applications:
        scheduled_at = application.applied_at
        for kind in list(Interview.Kind)[: rounds.get(application.stage, 0)]:
            scheduled_at += timedelta(days=rng.randint(2, 9), hours=rng.randint(0, 6))
            done = scheduled_at < now
            interviews.append(
                Interview(
                    application=application,
                    kind=kind,
                    interviewer=rng.choice(members),
                    scheduled_at=scheduled_at,
                    duration=timedelta(minutes=rng.choice([30, 45, 60, 90])),
                    score=rng.randint(2, 5) if done and rng.random() < 0.85 else None,
                    feedback=fake.paragraphs(rng, 1) if done else "",
                )
            )
    Interview.objects.bulk_create(interviews)
    return f"{len(openings)} openings, {len(candidates)} candidates, {len(applications)} applications, {len(interviews)} interviews"
