from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("e2e", "0010_dirtyuniquepair"),
    ]

    operations = [
        migrations.CreateModel(
            name="SearchOption",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("kind", models.CharField(max_length=20)),
                ("code", models.CharField(max_length=10)),
                ("name", models.CharField(max_length=100)),
                ("icon", models.CharField(blank=True, default="", max_length=20)),
                ("description", models.CharField(blank=True, default="", max_length=100)),
            ],
            options={
                "ordering": ["pk"],
                "constraints": [models.UniqueConstraint(fields=("kind", "code"), name="uq_search_option_kind_code")],
            },
        ),
    ]
