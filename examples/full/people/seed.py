from __future__ import annotations

import random
from datetime import time, timedelta

from taskmanager import sample_data as fake
from taskmanager.models import Member

from .models import Department, Employee, Equipment, TimeOff

DEPARTMENTS = [
    ("Engineering", "ENG", ["Backend engineer", "Frontend engineer", "Platform engineer", "Engineering manager"]),
    ("Design", "DES", ["Product designer", "UX researcher", "Brand designer"]),
    ("Sales", "SAL", ["Account executive", "Sales development rep", "Sales manager"]),
    ("Customer success", "CS", ["Support agent", "Customer success manager", "Support lead"]),
    ("Finance", "FIN", ["Accountant", "Controller", "Payroll specialist"]),
    ("People", "PPL", ["Recruiter", "People partner"]),
    ("Operations", "OPS", ["IT administrator", "Workplace coordinator", "Office manager"]),
]

EQUIPMENT = {
    Equipment.Kind.LAPTOP: ["ThinkPad T14", "MacBook Pro 14", "Framework 13", "Dell Latitude 7440"],
    Equipment.Kind.MONITOR: ["Dell U2723QE", "LG 27UK850", "BenQ PD2705U"],
    Equipment.Kind.PHONE: ["Pixel 9", "iPhone 16", "Fairphone 5"],
    Equipment.Kind.HEADSET: ["Jabra Evolve2 65", "Poly Voyager 4320"],
    Equipment.Kind.DOCK: ["CalDigit TS4", "Lenovo USB-C Dock"],
}


def clear() -> None:
    Equipment.objects.all().delete()
    TimeOff.objects.all().delete()
    Employee.objects.all().delete()
    Department.objects.all().delete()


def seed(rng: random.Random, scale: float) -> str:
    departments = [
        Department.objects.create(
            name=name,
            code=code,
            standup_time=time(9 + rng.randint(0, 1), rng.choice([0, 15, 30])),
            budget=fake.money(rng, 80_000, 900_000),
        )
        for name, code, _ in DEPARTMENTS
    ]
    titles = {department.pk: entry[2] for department, entry in zip(departments, DEPARTMENTS, strict=True)}

    existing = set(Member.objects.values_list("email", flat=True))
    new_members = []
    for _ in range(fake.scaled(48, scale)):
        first, last = fake.person(rng)
        email = f"{first}.{last}@taskwork.example".lower()
        if email not in existing:
            existing.add(email)
            new_members.append(Member(name=f"{first} {last}", email=email))
    Member.objects.bulk_create(new_members)

    employees = []
    for member in Member.objects.order_by("pk"):
        department = rng.choice(departments)
        employees.append(
            Employee(
                member=member,
                department=department,
                job_title=rng.choice(titles[department.pk]),
                employment_type=rng.choices(list(Employee.Type), weights=[12, 3, 2, 1])[0],
                start_date=fake.day(rng, 2400, -30),
                end_date=fake.day(rng, 60, 200) if rng.random() < 0.06 else None,
                weekly_hours=rng.choice([40, 40, 40, 32, 30, 20]),
                remote=rng.random() < 0.35,
            )
        )
    Employee.objects.bulk_create(employees)
    employees = list(Employee.objects.select_related("department"))

    by_department: dict[int, list[Employee]] = {}
    for employee in employees:
        by_department.setdefault(employee.department_id, []).append(employee)
    for department in departments:
        staff = by_department.get(department.pk, [])
        if not staff:
            continue
        lead = staff[0]
        department.head_id = lead.member_id
        department.save(update_fields=["head"])
        for employee in staff[1:]:
            employee.manager = lead
    Employee.objects.bulk_update(employees, ["manager"])

    requests = []
    for _ in range(fake.scaled(160, scale)):
        starts_on = fake.day(rng, 200, 120)
        requests.append(
            TimeOff(
                employee=rng.choice(employees),
                kind=rng.choices(list(TimeOff.Kind), weights=[10, 4, 1, 2, 1])[0],
                status=rng.choices(list(TimeOff.Status), weights=[3, 10, 1])[0],
                starts_on=starts_on,
                ends_on=starts_on + timedelta(days=rng.randint(0, 14)),
                note=fake.sentence(rng) if rng.random() < 0.3 else "",
            )
        )
    TimeOff.objects.bulk_create(requests)

    items = []
    for number in range(1, fake.scaled(140, scale) + 1):
        kind = rng.choice(list(EQUIPMENT))
        purchased_on = fake.day(rng, 1500, -10)
        items.append(
            Equipment(
                asset_tag=f"EQ-{number:05d}",
                kind=kind,
                model_name=rng.choice(EQUIPMENT[kind]),
                serial_number=f"{rng.randint(10**9, 10**10 - 1)}",
                assigned_to=rng.choice(employees) if rng.random() < 0.8 else None,
                purchased_on=purchased_on,
                purchase_price=fake.money(rng, 40, 2600),
                warranty_until=purchased_on + timedelta(days=rng.choice([365, 730, 1095]))
                if rng.random() < 0.9
                else None,
                retired=rng.random() < 0.08,
            )
        )
    Equipment.objects.bulk_create(items)
    return f"{len(departments)} departments, {len(employees)} employees, {len(requests)} time off requests, {len(items)} equipment"
