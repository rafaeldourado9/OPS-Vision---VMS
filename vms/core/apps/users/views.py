"""Views para users."""
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from .serializers import UserSerializer


class UserMeView(APIView):
    """Retorna os dados do usuário autenticado.

    GET /api/v1/auth/me/
    """

    def get(self, request: Request) -> Response:
        """Retorna id, username, email e tenant do usuário logado."""
        serializer = UserSerializer(request.user)
        return Response(serializer.data)
