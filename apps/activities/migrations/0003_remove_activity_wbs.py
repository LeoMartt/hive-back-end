from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("activities", "0002_remove_em_execucao_status"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="activity",
            name="wbs",
        ),
    ]
