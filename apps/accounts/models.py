from django.contrib.auth.models import AbstractUser
from django.db import models


class Usuario(AbstractUser):
    """Identidade do usuário: perfil + vínculo com o Microsoft Entra ID.

    Não guarda papel (Gestor de Projetos / Tester / Desenvolvedor) nem vínculo com
    projeto — isso é responsabilidade de `apps.projects.Membership`.
    """

    entra_object_id = models.CharField(
        "ID do objeto no Entra ID",
        max_length=36,
        unique=True,
        null=True,
        blank=True,
        help_text="Claim 'oid' do Access Token emitido pelo Microsoft Entra ID. "
        "Nulo para contas locais (ex.: superusuário de admin criado em dev).",
    )

    def __str__(self) -> str:
        return self.email or self.username
