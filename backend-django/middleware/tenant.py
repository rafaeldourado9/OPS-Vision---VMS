import json
from django.core.cache import cache
from django.http import HttpResponse
from apps.resellers.models import Reseller
from apps.tenants.models import Tenant


class TenantMiddleware:
    """Middleware para resolver tenant e reseller baseado no host"""
    
    def __init__(self, get_response):
        self.get_response = get_response

    # Paths que não precisam de tenant (chamadas internas e endpoints públicos)
    BYPASS_PATHS = ('/api/v1/internal/', '/api/internal/', '/api/v1/auth/', '/api/v1/theme/', '/admin/', '/static/', '/media/')

    def __call__(self, request):
        if any(request.path.startswith(p) for p in self.BYPASS_PATHS):
            request.tenant_id = None
            request.reseller_id = None
            request.tenant = None
            request.reseller = None
            return self.get_response(request)

        host = request.META.get('HTTP_HOST', '').split(':')[0]
        
        # Tenta buscar no Redis primeiro
        cache_key = f'wl:{host}'
        cached_data = cache.get(cache_key)
        
        if cached_data:
            data = json.loads(cached_data)
            request.tenant_id = data['tenant_id']
            request.reseller_id = data['reseller_id']
            request.tenant = type('Tenant', (), data['tenant'])()
            request.reseller = type('Reseller', (), data['reseller'])()
        else:
            # Cache miss: busca no banco
            try:
                # Tenta por custom_domain primeiro
                reseller = Reseller.objects.filter(custom_domain=host, active=True).first()
                
                if not reseller:
                    # Tenta por subdomain
                    subdomain = host.split('.')[0]
                    tenant = Tenant.objects.select_related('reseller').filter(
                        subdomain=subdomain, active=True
                    ).first()
                    
                    if not tenant:
                        return HttpResponse('Tenant não encontrado', status=404)
                    
                    reseller = tenant.reseller
                else:
                    # Se encontrou por custom_domain, pega o primeiro tenant ativo
                    tenant = reseller.tenants.filter(active=True).first()
                    if not tenant:
                        return HttpResponse('Tenant não encontrado', status=404)
                
                # Prepara dados para cache
                cache_data = {
                    'tenant_id': str(tenant.id),
                    'reseller_id': str(reseller.id),
                    'tenant': {
                        'id': str(tenant.id),
                        'name': tenant.name,
                        'subdomain': tenant.subdomain,
                    },
                    'reseller': {
                        'id': str(reseller.id),
                        'name': reseller.name,
                        'slug': reseller.slug,
                        'primary_color': reseller.primary_color,
                        'secondary_color': reseller.secondary_color,
                        'logo_url': reseller.logo_url,
                        'favicon_url': reseller.favicon_url,
                        'dark_mode_default': reseller.dark_mode_default,
                        'terms_url': reseller.terms_url,
                        'privacy_url': reseller.privacy_url,
                    }
                }
                
                # Salva no cache por 5 minutos
                cache.set(cache_key, json.dumps(cache_data), 300)
                
                request.tenant_id = str(tenant.id)
                request.reseller_id = str(reseller.id)
                request.tenant = tenant
                request.reseller = reseller
                
            except Exception as e:
                return HttpResponse(f'Erro ao resolver tenant: {str(e)}', status=500)
        
        response = self.get_response(request)
        return response
