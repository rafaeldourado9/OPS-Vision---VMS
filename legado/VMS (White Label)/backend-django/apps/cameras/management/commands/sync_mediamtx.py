"""
Sincroniza câmeras com o MediaMTX:
  - Registra todos os paths RTSP ativos no MediaMTX
  - Atualiza status online/offline com base nos paths ativos

Uso: python manage.py sync_mediamtx [--watch]
"""
import time
import httpx
import logging
from django.core.management.base import BaseCommand
from django.utils import timezone
from apps.cameras.models import Camera

logger = logging.getLogger(__name__)
MEDIAMTX_API = "http://mediamtx:9997/v3"
MEDIAMTX_AUTH = ("mediamtx_api_user", "GtV!sionMed1aMTX$2025")


def register_all_cameras():
    cameras = Camera.objects.filter(stream_protocol='rtsp').exclude(stream_url='')
    for camera in cameras:
        path_name = f"live/{camera.tenant_id}/{camera.id}"
        try:
            r = httpx.post(
                f"{MEDIAMTX_API}/config/paths/add/{path_name}",
                json={"source": camera.stream_url, "sourceOnDemand": False},
                auth=MEDIAMTX_AUTH,
                timeout=5,
            )
            if r.status_code in (200, 201):
                logger.info(f"Registered: {path_name}")
            elif r.status_code == 400 and 'already exists' in r.text:
                pass  # já existe, ok
            else:
                logger.warning(f"Failed to register {path_name}: {r.status_code}")
        except Exception as e:
            logger.warning(f"MediaMTX unreachable: {e}")
            return False
    return True


def sync_status():
    try:
        r = httpx.get(f"{MEDIAMTX_API}/paths/list", auth=MEDIAMTX_AUTH, timeout=5)
        if r.status_code != 200:
            return
        data = r.json()
        active_paths = {item['name'] for item in data.get('items', []) if item.get('ready')}

        cameras = Camera.objects.all()
        for camera in cameras:
            path_name = f"live/{camera.tenant_id}/{camera.id}"
            is_online = path_name in active_paths
            if camera.online != is_online:
                camera.online = is_online
                camera.last_seen = timezone.now() if is_online else camera.last_seen
                camera.save(update_fields=['online', 'last_seen'])
                logger.info(f"Camera {camera.name}: {'online' if is_online else 'offline'}")
    except Exception as e:
        logger.warning(f"Status sync error: {e}")


class Command(BaseCommand):
    help = 'Sincroniza câmeras com MediaMTX'

    def add_arguments(self, parser):
        parser.add_argument('--watch', action='store_true', help='Monitorar continuamente (intervalo 10s)')

    def handle(self, *args, **options):
        self.stdout.write('Registrando câmeras no MediaMTX...')
        registered = register_all_cameras()
        if registered:
            self.stdout.write(self.style.SUCCESS('Câmeras registradas.'))
        else:
            self.stdout.write(self.style.WARNING('MediaMTX indisponível.'))

        if options['watch']:
            self.stdout.write('Monitorando status (Ctrl+C para parar)...')
            while True:
                time.sleep(10)
                sync_status()
