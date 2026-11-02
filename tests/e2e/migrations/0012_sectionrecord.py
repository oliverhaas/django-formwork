from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("e2e", "0011_searchoption"),
    ]

    operations = [
        migrations.CreateModel(
            name="SectionRecord",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=100)),
                ("city", models.CharField(blank=True, default="", max_length=10)),
                ("note", models.CharField(blank=True, default="", max_length=100)),
                ("color", models.CharField(max_length=20)),
            ],
        ),
    ]
