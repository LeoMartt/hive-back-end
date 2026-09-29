from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("activities", "0003_remove_activity_wbs"),
    ]

    operations = [
        migrations.AddField(
            model_name="activity",
            name="evidencia_aprovacao",
            field=models.JSONField(blank=True, null=True),
        ),
    ]
