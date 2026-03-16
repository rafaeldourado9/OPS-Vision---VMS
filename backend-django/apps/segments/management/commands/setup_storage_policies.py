"""Cria políticas de storage padrão para todos os tenants que não têm."""

from django.core.management.base import BaseCommand
from apps.tenants.models import Tenant
from apps.segments.models import StoragePolicy


DEFAULT_POLICIES = [
    # Recordings: hot (7d SSD) → cold (30d HDD) → delete
    {'category': 'recordings', 'tier_order': 0, 'path': '/app/storage',
     'max_age_hours': 168, 'max_size_gb': 500},
    {'category': 'recordings', 'tier_order': 1, 'path': '/app/storage/cold',
     'max_age_hours': 720, 'max_size_gb': 2000},
    # Snapshots: 7d
    {'category': 'snapshots', 'tier_order': 0, 'path': '/app/storage',
     'max_age_hours': 168, 'max_size_gb': 50},
    # Heatmaps: 30d
    {'category': 'heatmaps', 'tier_order': 0, 'path': '/app/storage',
     'max_age_hours': 720, 'max_size_gb': 10},
    # Clips: 90d
    {'category': 'clips', 'tier_order': 0, 'path': '/app/storage',
     'max_age_hours': 2160, 'max_size_gb': 100},
]


class Command(BaseCommand):
    help = 'Cria políticas de storage padrão para tenants sem configuração'

    def handle(self, *args, **options):
        tenants = Tenant.objects.filter(active=True)
        created_count = 0

        for tenant in tenants:
            existing = StoragePolicy.objects.filter(tenant=tenant).exists()
            if existing:
                self.stdout.write(f'  {tenant.name}: já tem policies, pulando')
                continue

            for policy_data in DEFAULT_POLICIES:
                StoragePolicy.objects.create(tenant=tenant, **policy_data)
                created_count += 1

            self.stdout.write(self.style.SUCCESS(
                f'  {tenant.name}: {len(DEFAULT_POLICIES)} policies criadas'
            ))

        self.stdout.write(self.style.SUCCESS(
            f'\nTotal: {created_count} policies criadas'
        ))
