"""Heatmap analytic worker — accumulates person centroids in Redis."""
import asyncio
import json
import os
from analytic_workers.base import BaseAnalyticWorker

PERSON_IDS = {0}
HEATMAP_MAX_POINTS = int(os.getenv('HEATMAP_MAX_POINTS', '10000'))
HEATMAP_UPDATE_FRAMES = int(os.getenv('HEATMAP_UPDATE_FRAMES', '30'))
HEATMAP_SIGMA = int(os.getenv('HEATMAP_SIGMA', '40'))
STORAGE_PATH = os.getenv('STORAGE_PATH', '/app/storage')


class HeatmapWorker(BaseAnalyticWorker):
    queue_name = 'ai.detect.heatmap'

    def __init__(self):
        super().__init__()
        self._frame_counts: dict[str, int] = {}

    async def process(self, payload: dict):
        camera_id = payload['camera_id']
        width = payload['frame_width']
        height = payload['frame_height']
        detections = payload['detections']

        persons = self.filter_by_classes(detections, PERSON_IDS)

        for roi in payload['rois']:
            polygon = roi.get('polygon', [])
            in_zone = self.in_polygon(persons, polygon, width, height)

            redis_key = f'heatmap:points:{camera_id}'
            for det in in_zone:
                cx = ((det['x1'] + det['x2']) / 2) / width
                cy = ((det['y1'] + det['y2']) / 2) / height
                self.redis.lpush(redis_key, json.dumps([round(cx, 4), round(cy, 4)]))
            self.redis.ltrim(redis_key, 0, HEATMAP_MAX_POINTS - 1)
            self.redis.expire(redis_key, 86400)

        count = self._frame_counts.get(camera_id, 0) + 1
        self._frame_counts[camera_id] = count
        if count % HEATMAP_UPDATE_FRAMES == 0:
            import asyncio as _asyncio
            loop = _asyncio.get_event_loop()
            await loop.run_in_executor(None, self._generate_heatmap, camera_id)

    def _generate_heatmap(self, camera_id: str):
        import cv2
        import numpy as np
        from pathlib import Path

        raw = self.redis.lrange(f'heatmap:points:{camera_id}', 0, -1)
        if not raw:
            return
        centroids = []
        for r in raw:
            try:
                centroids.append(json.loads(r))
            except Exception:
                continue
        if not centroids:
            return

        out_w, out_h = 1280, 720
        acc = np.zeros((out_h, out_w), dtype=np.float32)
        for cx, cy in centroids:
            x, y = int(cx * out_w), int(cy * out_h)
            if 0 <= x < out_w and 0 <= y < out_h:
                acc[y, x] += 1.0
        ksize = (int(6 * HEATMAP_SIGMA + 1) | 1)
        blurred = cv2.GaussianBlur(acc, (ksize, ksize), HEATMAP_SIGMA)
        if blurred.max() > 0:
            blurred /= blurred.max()
        img = cv2.applyColorMap((blurred * 255).astype(np.uint8), cv2.COLORMAP_JET)
        out_dir = Path(STORAGE_PATH) / 'heatmaps'
        out_dir.mkdir(parents=True, exist_ok=True)
        cv2.imwrite(str(out_dir / f'{camera_id}.jpg'), img)


async def main():
    await HeatmapWorker().consume()

if __name__ == '__main__':
    asyncio.run(main())
