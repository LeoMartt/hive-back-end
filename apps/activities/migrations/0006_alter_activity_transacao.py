from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("activities", "0005_activity_historico_status")]

    operations = [
        migrations.AlterField(
            model_name="activity",
            name="transacao",
            field=models.CharField(max_length=1000, blank=True, default=""),
        ),
    ]
