import django.db.models.deletion
import pgtrigger.compiler
import pgtrigger.migrations
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("history_app", "0001_initial"),
        ("pghistory", "0007_auto_20250421_0444"),
    ]

    operations = [
        migrations.CreateModel(
            name="Memo",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("text", models.CharField(max_length=100)),
            ],
        ),
        migrations.CreateModel(
            name="MemoEvent",
            fields=[
                ("pgh_id", models.AutoField(primary_key=True, serialize=False)),
                ("pgh_created_at", models.DateTimeField(auto_now_add=True)),
                ("pgh_label", models.TextField(help_text="The event label.")),
                ("id", models.BigIntegerField()),
                ("text", models.CharField(max_length=100)),
            ],
            options={
                "abstract": False,
            },
        ),
        pgtrigger.migrations.AddTrigger(
            model_name="memo",
            trigger=pgtrigger.compiler.Trigger(
                name="snapshot_insert",
                sql=pgtrigger.compiler.UpsertTriggerSql(
                    func='INSERT INTO "history_app_memoevent" ("id", "pgh_context_id", "pgh_created_at", "pgh_label", "pgh_obj_id", "text") VALUES (NEW."id", _pgh_attach_context(), NOW(), \'snapshot\', NEW."id", NEW."text"); RETURN NULL;',
                    hash="d723b5b18f466097f375bc5602a7ba2127c41909",
                    operation="INSERT",
                    pgid="pgtrigger_snapshot_insert_cbe0d",
                    table="history_app_memo",
                    when="AFTER",
                ),
            ),
        ),
        pgtrigger.migrations.AddTrigger(
            model_name="memo",
            trigger=pgtrigger.compiler.Trigger(
                name="snapshot_update",
                sql=pgtrigger.compiler.UpsertTriggerSql(
                    condition="WHEN (OLD.* IS DISTINCT FROM NEW.*)",
                    func='INSERT INTO "history_app_memoevent" ("id", "pgh_context_id", "pgh_created_at", "pgh_label", "pgh_obj_id", "text") VALUES (NEW."id", _pgh_attach_context(), NOW(), \'snapshot\', NEW."id", NEW."text"); RETURN NULL;',
                    hash="6654ea26f129676b18c284130c36687329a2a67a",
                    operation="UPDATE",
                    pgid="pgtrigger_snapshot_update_2cddc",
                    table="history_app_memo",
                    when="AFTER",
                ),
            ),
        ),
        migrations.AddField(
            model_name="memoevent",
            name="pgh_context",
            field=models.ForeignKey(
                db_constraint=False,
                null=True,
                on_delete=django.db.models.deletion.DO_NOTHING,
                related_name="+",
                to="pghistory.context",
            ),
        ),
        migrations.AddField(
            model_name="memoevent",
            name="pgh_obj",
            field=models.ForeignKey(
                db_constraint=False,
                on_delete=django.db.models.deletion.DO_NOTHING,
                related_name="events",
                to="history_app.memo",
            ),
        ),
    ]
