"""Convert Task.assignee from a free-text name to a Member foreign key."""

import django.db.models.deletion
from django.db import migrations, models


def assignee_strings_to_members(apps, schema_editor):
    Member = apps.get_model("taskmanager", "Member")
    Task = apps.get_model("taskmanager", "Task")
    # order_by() clears Task.Meta.ordering; a leftover ORDER BY column would
    # sneak into the DISTINCT and yield duplicate names.
    names = Task.objects.exclude(assignee="").order_by().values_list("assignee", flat=True).distinct()
    for name in names:
        base = name.split()[0].lower()
        email, counter = f"{base}@example.com", 2
        while Member.objects.filter(email=email).exists():
            email, counter = f"{base}{counter}@example.com", counter + 1
        member = Member.objects.create(name=name, email=email)
        Task.objects.filter(assignee=name).update(assignee_member=member)


def members_back_to_strings(apps, schema_editor):
    Member = apps.get_model("taskmanager", "Member")
    Task = apps.get_model("taskmanager", "Task")
    for member in Member.objects.all():
        Task.objects.filter(assignee_member=member).update(assignee=member.name)


class Migration(migrations.Migration):
    dependencies = [
        ("taskmanager", "0002_profile"),
    ]

    operations = [
        migrations.CreateModel(
            name="Member",
            fields=[
                (
                    "id",
                    models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID"),
                ),
                ("name", models.CharField(max_length=100)),
                ("email", models.EmailField(max_length=254, unique=True)),
            ],
            options={"ordering": ["name"]},
        ),
        migrations.AddField(
            model_name="task",
            name="assignee_member",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="tasks",
                to="taskmanager.member",
            ),
        ),
        migrations.RunPython(assignee_strings_to_members, members_back_to_strings),
        migrations.RemoveField(model_name="task", name="assignee"),
        migrations.RenameField(model_name="task", old_name="assignee_member", new_name="assignee"),
    ]
