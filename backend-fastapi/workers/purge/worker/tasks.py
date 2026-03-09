import asyncio
import os
from datetime import datetime
from pathlib import Path
import httpx
from apscheduler.schedulers.asyncio import AsyncIOScheduler


STORAGE_PATH = os.getenv('STORAGE_PATH', '/app/storage')
DJANGO_URL = os.getenv('DJANGO_INTERNAL_URL', 'http://django:8000')


class PurgeWorker:
    def __init__(self):
        self.http_client = httpx.AsyncClient()
        self.scheduler = AsyncIOScheduler()

    async def purge_expired_segments(self):
        """Remove segmentos expirados"""
        try:
            # Busca segmentos expirados do Django
            response = await self.http_client.get(
                f'{DJANGO_URL}/api/v1/internal/segments/expired/'
            )
            response.raise_for_status()
            
            expired_segments = response.json()
            
            for segment in expired_segments:
                file_path = Path(segment['file_path'])
                
                # Remove arquivo físico
                if file_path.exists():
                    file_path.unlink()
                    print(f'Arquivo removido: {file_path}')
                
                # Remove registro do banco
                await self.http_client.delete(
                    f'{DJANGO_URL}/api/v1/internal/segments/{segment["id"]}/'
                )
                
        except Exception as e:
            print(f'Erro ao purgar segmentos: {e}')

    def start(self):
        """Inicia scheduler para executar diariamente às 3h"""
        self.scheduler.add_job(
            self.purge_expired_segments,
            'cron',
            hour=3,
            minute=0
        )
        self.scheduler.start()


async def main():
    worker = PurgeWorker()
    worker.start()
    
    # Mantém worker rodando
    while True:
        await asyncio.sleep(3600)


if __name__ == '__main__':
    asyncio.run(main())
