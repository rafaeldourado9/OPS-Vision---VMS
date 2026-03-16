from datetime import date, timedelta

from django.core.management.base import BaseCommand

from apps.auth_app.models import User
from apps.franchise.models import License
from apps.resellers.models import Reseller
from apps.tenants.models import Tenant


LICENSE_TIERS = [
    {'name': 'Starter', 'max_cameras': 100},
    {'name': 'Business', 'max_cameras': 300},
    {'name': 'Enterprise', 'max_cameras': 500},
]


class Command(BaseCommand):
    help = 'Cria Reseller + 3 Licencas (100/300/500) + Tenant + Superuser'

    def add_arguments(self, parser):
        parser.add_argument('--reseller', default='GTVision', help='Nome do reseller')
        parser.add_argument('--slug', default='gtvision', help='Slug do reseller')
        parser.add_argument('--domain', default='localhost', help='custom_domain (IP ou dominio que o browser acessa)')
        parser.add_argument('--tenant', default='Cidade Teste', help='Nome do tenant')
        parser.add_argument('--subdomain', default='localhost', help='Subdomain do tenant')
        parser.add_argument('--license', type=int, default=500, choices=[100, 300, 500],
                            help='Licenca ativa para o tenant (100, 300 ou 500 cameras)')
        parser.add_argument('--license-days', type=int, default=365, help='Dias de validade')
        parser.add_argument('--email', default='admin@gtvision.com', help='Email do superuser')
        parser.add_argument('--password', default='Admin123!', help='Senha do superuser')

    def handle(self, **options):
        valid_until = date.today() + timedelta(days=options['license_days'])
        active_tier = options['license']

        # ── Reseller ─────────────────────────────────────────────
        reseller = Reseller.objects.filter(slug=options['slug']).first() \
            or Reseller.objects.filter(custom_domain=options['domain']).first()
        if reseller:
            reseller.slug = options['slug']
            reseller.custom_domain = options['domain']
            reseller.name = options['reseller']
            reseller.save(update_fields=['slug', 'custom_domain', 'name'])
            self.stdout.write(f'  Existente Reseller: {reseller.name}')
        else:
            reseller = Reseller.objects.create(
                name=options['reseller'],
                slug=options['slug'],
                custom_domain=options['domain'],
            )
            self.stdout.write(f'  Criado Reseller: {reseller.name}')

        # ── 3 Licencas ───────────────────────────────────────────
        active_license = None
        self.stdout.write('')
        for tier in LICENSE_TIERS:
            is_active = tier['max_cameras'] == active_tier
            license_obj, created = License.objects.update_or_create(
                reseller=reseller,
                max_cameras=tier['max_cameras'],
                defaults={
                    'valid_until': valid_until,
                    'active': is_active,
                },
            )
            marker = ' << ATIVA' if is_active else ''
            status = 'Criada' if created else 'Atualizada'
            self.stdout.write(
                f'  {status} Licenca {tier["name"]}: '
                f'{tier["max_cameras"]} cameras (valida ate {valid_until}){marker}'
            )
            if is_active:
                active_license = license_obj

        # ── Tenant ────────────────────────────────────────────────
        self.stdout.write('')
        tenant = Tenant.objects.filter(subdomain=options['subdomain']).first()
        if tenant:
            tenant.reseller = reseller
            tenant.license = active_license
            tenant.name = options['tenant']
            tenant.save(update_fields=['reseller', 'license', 'name'])
            self.stdout.write(f'  Existente Tenant: {tenant.name} (licenca atualizada)')
        else:
            tenant = Tenant.objects.create(
                reseller=reseller,
                license=active_license,
                name=options['tenant'],
                subdomain=options['subdomain'],
            )
            self.stdout.write(f'  Criado Tenant: {tenant.name} (subdomain={tenant.subdomain})')

        # ── Superuser ─────────────────────────────────────────────
        self.stdout.write('')
        email = options['email']
        if User.objects.filter(email=email).exists():
            user = User.objects.get(email=email)
            user.tenant = tenant
            user.save(update_fields=['tenant'])
            self.stdout.write(f'  Existente User: {email} (vinculado ao tenant)')
        else:
            user = User.objects.create_superuser(email=email, password=options['password'])
            user.tenant = tenant
            user.save(update_fields=['tenant'])
            self.stdout.write(f'  Criado Superuser: {email} / {options["password"]}')

        # ── Resumo ────────────────────────────────────────────────
        self.stdout.write(self.style.SUCCESS(f'''
========================================
  Setup completo!
========================================
  Reseller:  {reseller.name} (ID: {reseller.id})
  Tenant:    {tenant.name} (ID: {tenant.id})
  Licenca:   {active_license.max_cameras} cameras ate {active_license.valid_until}
  Usuario:   {email}
  Acesse:    http://{reseller.custom_domain}
========================================'''))
