from rest_framework.generics import RetrieveAPIView

from .serializers import UsuarioSerializer


class MeView(RetrieveAPIView):
    """Retorna o usuário autenticado — smoke test da integração com o Entra ID."""

    serializer_class = UsuarioSerializer

    def get_object(self):
        return self.request.user
