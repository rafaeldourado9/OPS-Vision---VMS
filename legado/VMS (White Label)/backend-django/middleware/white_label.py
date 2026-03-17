class WhiteLabelMiddleware:
    """Middleware para injetar tema do white label"""
    
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if getattr(request, 'reseller', None) is not None:
            request.theme = {
                'name': request.reseller.name,
                'primary_color': request.reseller.primary_color,
                'secondary_color': request.reseller.secondary_color,
                'logo_url': request.reseller.logo_url,
                'favicon_url': request.reseller.favicon_url,
                'dark_mode_default': request.reseller.dark_mode_default,
                'terms_url': request.reseller.terms_url,
                'privacy_url': request.reseller.privacy_url,
            }
        
        response = self.get_response(request)
        return response
