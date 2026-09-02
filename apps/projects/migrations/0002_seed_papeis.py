from django.db import migrations


PAPEIS = [
    (1, "GESTOR", "Gestor de Projetos"),
    (2, "TESTER", "Tester"),
    (3, "DEV", "Desenvolvedor"),
]


def criar_papeis(apps, schema_editor):
    Papel = apps.get_model("projects", "Papel")

    for papel_id, codigo, nome_exibicao in PAPEIS:
        Papel.objects.update_or_create(
            id=papel_id,
            defaults={
                "codigo": codigo,
                "nome_exibicao": nome_exibicao,
            },
        )


def remover_papeis(apps, schema_editor):
    Papel = apps.get_model("projects", "Papel")
    Papel.objects.filter(codigo__in=[codigo for _, codigo, _ in PAPEIS]).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("projects", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(criar_papeis, remover_papeis),
    ]
