"""Queue (Fila) analytic worker — stateful."""
import asyncio
import time
from analytic_workers.base import BaseAnalyticWorker

PERSON_IDS = {0}


class QueueWorker(BaseAnalyticWorker):
    queue_name = 'ai.detect.queue'

    def __init__(self):
        super().__init__()
        self._seen: dict[str, dict[int, float]] = {}
        self._alerted: dict[str, set] = {}

    async def process(self, payload: dict):
        camera_id = payload['camera_id']
        tenant_id = payload['tenant_id']
        width = payload['frame_width']
        height = payload['frame_height']
        detections = payload['detections']
        frame_path = payload.get('frame_path', '')
        now = time.time()

        persons = self.filter_by_classes(detections, PERSON_IDS)

        for roi in payload['rois']:
            roi_id = str(roi['id'])
            config = roi.get('config', {})
            threshold = int(config.get('threshold', 5))
            alert_after = int(config.get('alert_after_seconds', 60))
            polygon = roi.get('polygon', [])

            in_zone = self.in_polygon(persons, polygon, width, height)
            seen = self._seen.setdefault(roi_id, {})
            alerted = self._alerted.setdefault(roi_id, set())
            active: set[int] = set()

            for det in in_zone:
                tid = det.get('tracker_id') or 0
                active.add(tid)
                seen.setdefault(tid, now)

            for tid in list(seen):
                if tid not in active:
                    del seen[tid]
                    alerted.discard(tid)

            if len(seen) < threshold:
                continue

            long_waiters = [t for t, ts in seen.items() if (now - ts) >= alert_after and t not in alerted]
            if not long_waiters:
                continue

            for t in long_waiters:
                alerted.add(t)

            avg_wait = round(sum(now - ts for ts in seen.values()) / len(seen))
            await self.publish_event(
                camera_id=camera_id, tenant_id=tenant_id, roi_id=roi_id,
                event_type='queue_alert',
                event_data={'count': len(seen), 'threshold': threshold, 'avg_wait_seconds': avg_wait},
                frame_path=frame_path,
            )


async def main():
    await QueueWorker().consume()

if __name__ == '__main__':
    asyncio.run(main())
