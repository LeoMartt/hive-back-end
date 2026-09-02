import uuid

from django.contrib.auth.models import AbstractUser
from django.db import models


class Usuario(AbstractUser):
    """Identidade do usuário: perfil + vínculo com o Microsoft Entra ID.

    Não guarda papel (Gestor de Projetos / Tester / Desenvolvedor) nem vínculo com
    projeto — isso é responsabilidade de `apps.projects.Membership`.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    email = models.EmailField("e-mail", unique=True)

    entra_object_id = models.UUIDField(
        "ID do objeto no Entra ID",
        unique=True,
        null=True,
        blank=True,
        help_text="Claim 'oid' do Access Token emitido pelo Microsoft Entra ID. "
        "Nulo para contas locais (ex.: superusuário de admin criado em dev).",
    )
    iniciais = models.CharField("iniciais", max_length=4, blank=True, default="")

    def __str__(self) -> str:
        return self.email or self.username
