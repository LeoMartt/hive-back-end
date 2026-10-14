from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("activities", "0004_activity_evidencia_aprovacao")]

    operations = [
        migrations.AddField(
            model_name="activity",
            name="historico_status",
            field=models.JSONField(default=list, blank=True),
        ),
    ]
