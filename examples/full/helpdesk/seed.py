from __future__ import annotations

import random
from datetime import timedelta

from crm.models import Contact
from django.utils import timezone
from taskmanager import sample_data as fake
from taskmanager.models import Member

from .models import CannedResponse, Reply, Ticket

SUBJECTS = [
    "Can't log in after the password reset",
    "CSV export times out",
    "Invoice address is wrong",
    "Webhook stopped firing",
    "Please add a user to our account",
    "Question about the SSO setup",
    "API rate limit reached",
    "Feature request: dark mode",
    "Data import failed halfway",
    "Charged twice this month",
    "Reports show the wrong time zone",
    "Permission error on the dashboard",
]

CANNED = [
    (
        "Password reset",
        "reset",
        "You can reset your password from the login page. The link in the email stays valid for one hour.",
    ),
    (
        "Known incident",
        "incident",
        "We know about this problem and are working on a fix. You can follow the progress on our status page.",
    ),
    (
        "Feature request logged",
        "feature",
        "Thanks for the idea. We have added it to our feature requests and will let you know when it ships.",
    ),
    (
        "SSO documentation",
        "sso",
        "Our single sign-on guide covers Okta, Azure AD and Google Workspace. The link is below.",
    ),
    (
        "Invoice copy",
        "invoice",
        "You can download every invoice under Settings, Billing. A copy is attached to this reply.",
    ),
    (
        "Closing ticket",
        "closing",
        "We are closing this ticket for now. Just reply to this email if anything else comes up.",
    ),
]


def clear() -> None:
    Reply.objects.all().delete()
    Ticket.objects.all().delete()
    CannedResponse.objects.all().delete()


def seed(rng: random.Random, scale: float) -> str:
    agents = list(Member.objects.filter(employee__department__code="CS")) or list(Member.objects.all())
    requesters = list(Contact.objects.only("pk"))

    now = timezone.now()
    tickets = []
    for _ in range(fake.scaled(1100, scale)):
        opened_at = fake.moment(rng, 365)
        age = now - opened_at
        if age < timedelta(days=2):
            status = rng.choice([Ticket.Status.NEW, Ticket.Status.OPEN, Ticket.Status.WAITING])
        elif age < timedelta(days=14):
            status = rng.choices(list(Ticket.Status), weights=[1, 4, 3, 6, 1])[0]
        else:
            status = rng.choices(list(Ticket.Status), weights=[0, 1, 1, 4, 12])[0]
        responded = status != Ticket.Status.NEW
        solved = status in (Ticket.Status.SOLVED, Ticket.Status.CLOSED)
        tickets.append(
            Ticket(
                subject=rng.choice(SUBJECTS),
                requester=rng.choice(requesters),
                assignee=rng.choice(agents) if responded or rng.random() < 0.3 else None,
                status=status,
                priority=rng.choices(list(Ticket.Priority), weights=[3, 10, 3, 1])[0],
                channel=rng.choices(list(Ticket.Channel), weights=[8, 5, 2, 3])[0],
                opened_at=opened_at,
                first_response_at=min(now, opened_at + timedelta(minutes=rng.randint(5, 1500))) if responded else None,
                solved_at=min(now, opened_at + timedelta(hours=rng.randint(2, 200))) if solved else None,
                time_spent=timedelta(minutes=rng.choice([5, 10, 15, 30, 45, 90])) if responded else None,
                satisfaction=rng.choices([1, 2, 3, 4, 5], weights=[1, 1, 2, 5, 8])[0]
                if solved and rng.random() < 0.5
                else None,
            )
        )
    Ticket.objects.bulk_create(tickets)

    replies = []
    for ticket in tickets:
        moment = ticket.opened_at
        replies.append(Reply(ticket=ticket, body=fake.paragraphs(rng, 1), created_at=moment))
        if ticket.first_response_at is None:
            continue
        for index in range(rng.randint(1, 5)):
            moment = ticket.first_response_at if index == 0 else min(now, moment + timedelta(hours=rng.randint(1, 30)))
            from_agent = index % 2 == 0
            replies.append(
                Reply(
                    ticket=ticket,
                    author=ticket.assignee if from_agent else None,
                    body=fake.paragraphs(rng, 1),
                    is_internal=from_agent and rng.random() < 0.15,
                    created_at=moment,
                )
            )
    Reply.objects.bulk_create(replies)

    CannedResponse.objects.bulk_create(
        CannedResponse(title=title, shortcut=shortcut, body=body, times_used=rng.randint(0, 400))
        for title, shortcut, body in CANNED
    )
    return f"{len(tickets)} tickets, {len(replies)} replies, {len(CANNED)} canned responses"
