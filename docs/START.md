  ---
  Guia de Setup Inicial

  1. Migrations (já estão aplicadas, mas se precisar)

  # Gerar novas migrations (se mudou models)
  docker exec infra-django-1 python manage.py makemigrations

  # Aplicar migrations
  docker exec infra-django-1 python manage.py migrate

  2. Criar superuser

  docker exec -it infra-django-1 python manage.py createsuperuser

  Vai pedir só email e senha (não pede username, o modelo usa email como login).

  3. Criar hierarquia de tenant (pela shell ou admin)

  A hierarquia é: Reseller → License → Tenant → User

  docker exec -it infra-django-1 python manage.py shell

  Dentro da shell:

  from apps.resellers.models import Reseller
  from apps.franchise.models import License
  from apps.tenants.models import Tenant
  from datetime import date

  # 1. Reseller (revenda white label)
  reseller = Reseller.objects.create(
      name='Minha Revenda',
      slug='minha-revenda',
      custom_domain='172.18.0.12',  # IP/domínio que o browser acessa
  )

  # 2. License (define limite de câmeras)
  license = License.objects.create(
      reseller=reseller,
      max_cameras=50,
      valid_until=date(2027, 12, 31),
  )

  # 3. Tenant (instância/cidade)
  tenant = Tenant.objects.create(
      reseller=reseller,
      license=license,
      name='Cidade Teste',
      subdomain='cidade-teste',
  )

  print(f'Reseller: {reseller.id}')
  print(f'Tenant:   {tenant.id}')

  4. Associar superuser ao tenant (opcional)

  from apps.auth_app.models import User

  user = User.objects.get(email='seu@email.com')
  user.tenant = tenant
  user.save()

  5. Acessar admin

  Abra http://172.18.0.12/admin/ e logue com o superuser.

  De lá dá pra criar/editar tudo: Resellers, Licenses, Tenants, Cameras, ROIs.

  ---
  Nota: O custom_domain do Reseller precisa bater com o Host header do browser. Se acessa via 172.18.0.12, o custom_domain deve ser 172.18.0.12. O middleware TenantMiddleware resolve o tenant por esse campo.
