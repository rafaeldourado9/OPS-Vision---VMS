from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response


@api_view(['GET'])
@permission_classes([AllowAny])
def get_theme(request):
    """GET /api/v1/theme/ - Retorna tema do white label"""
    if hasattr(request, 'theme'):
        return Response(request.theme)
    
    # Fallback se middleware não injetou tema
    return Response({
        'name': 'Sistema',
        'primary_color': '#1E40AF',
        'secondary_color': '#3B82F6',
        'logo_url': None,
        'favicon_url': None,
        'dark_mode_default': False,
        'terms_url': None,
        'privacy_url': None
    })
