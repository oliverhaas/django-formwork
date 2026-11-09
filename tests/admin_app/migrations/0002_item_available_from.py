from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("admin_app", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="item",
            name="available_from",
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
