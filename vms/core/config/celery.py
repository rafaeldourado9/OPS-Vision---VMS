"""Configuração Celery para o VMS."""
import os

from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.dev")

app = Celery("vms")
app.config_from_object("django.conf:settings", namespace="CELERY")

# Auto-discover tasks from all installed Django apps
app.autodiscover_tasks()

# Celery Beat Schedule
# Intervalos configuráveis via env (segundos)
_HEALTH_CHECK_INTERVAL = float(os.environ.get("CAMERA_HEALTH_CHECK_INTERVAL", "300"))   # 5 min
_STORAGE_QUOTA_INTERVAL = float(os.environ.get("STORAGE_QUOTA_CHECK_INTERVAL", "3600")) # 1 h
_CLEANUP_INTERVAL = float(os.environ.get("RECORDINGS_CLEANUP_INTERVAL", "3600"))        # 1 h

app.conf.beat_schedule = {
    "camera-health-check": {
        "task": "cameras.health_check_all",
        "schedule": _HEALTH_CHECK_INTERVAL,
    },
    "check-storage-quota": {
        "task": "recordings.check_storage_quota",
        "schedule": _STORAGE_QUOTA_INTERVAL,
    },
    "cleanup-recordings": {
        "task": "recordings.cleanup_task",
        "schedule": _CLEANUP_INTERVAL,
    },
}
