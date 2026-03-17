"""Loitering (Perambulação) analytic worker — stateful by camera+roi."""
import asyncio
import os
import time
from analytic_workers.base import BaseAnalyticWorker

PERSON_IDS = {0}
DEDUP_TTL = int(os.getenv('DEDUP_TTL_SECONDS', '30'))


class LoiteringWorker(BaseAnalyticWorker):
    queue_name = 'ai.detect.loitering'

    def __init__(self):
        super().__init__()
        # {roi_id: {tracker_id: first_seen_ts}}
        self._first_seen: dict[str, dict[int, float]] = {}
        # {roi_id: set(alerted tracker_ids)}
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
            max_seconds = int(roi.get('config', {}).get('max_seconds', 30))
            polygon = roi.get('polygon', [])

            in_zone = self.in_polygon(persons, polygon, width, height)

            first_seen = self._first_seen.setdefault(roi_id, {})
            alerted = self._alerted.setdefault(roi_id, set())
            active: set[int] = set()

            for det in in_zone:
                tid = det.get('tracker_id') or 0
                active.add(tid)
                first_seen.setdefault(tid, now)
                elapsed = now - first_seen[tid]

                if elapsed >= max_seconds and tid not in alerted:
                    alerted.add(tid)
                    await self.publish_event(
                        camera_id=camera_id, tenant_id=tenant_id, roi_id=roi_id,
                        event_type='loitering',
                        event_data={'seconds_in_zone': round(elapsed), 'track_id': tid},
                        frame_path=frame_path,
                    )

            # Cleanup tracks that left the zone
            for tid in list(first_seen):
                if tid not in active:
                    del first_seen[tid]
                    alerted.discard(tid)


async def main():
    await LoiteringWorker().consume()

if __name__ == '__main__':
    asyncio.run(main())
