"""Abandoned Object analytic worker — stateful."""
import asyncio
import os
import time
from analytic_workers.base import BaseAnalyticWorker

PERSON_IDS = {0}
OBJECT_IDS = {24, 26, 28}
OBJ_NAMES = {24: 'backpack', 26: 'handbag', 28: 'suitcase'}


class AbandonedObjectWorker(BaseAnalyticWorker):
    queue_name = 'ai.detect.abandoned_object'

    def __init__(self):
        super().__init__()
        self._first_seen: dict[str, dict[int, float]] = {}
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
        objects = self.filter_by_classes(detections, OBJECT_IDS)

        for roi in payload['rois']:
            roi_id = str(roi['id'])
            stay_seconds = int(roi.get('config', {}).get('stay_seconds', 30))
            polygon = roi.get('polygon', [])

            persons_in = self.in_polygon(persons, polygon, width, height)
            objects_in = self.in_polygon(objects, polygon, width, height)
            persons_present = len(persons_in) > 0

            first_seen = self._first_seen.setdefault(roi_id, {})
            alerted = self._alerted.setdefault(roi_id, set())
            active: set[int] = set()

            for det in objects_in:
                tid = det.get('tracker_id') or 0
                active.add(tid)
                first_seen.setdefault(tid, now)
                elapsed = now - first_seen[tid]

                if elapsed >= stay_seconds and not persons_present and tid not in alerted:
                    alerted.add(tid)
                    await self.publish_event(
                        camera_id=camera_id, tenant_id=tenant_id, roi_id=roi_id,
                        event_type='abandoned_object',
                        event_data={
                            'class': det['class_name'],
                            'seconds_unattended': round(elapsed),
                            'track_id': tid,
                        },
                        frame_path=frame_path,
                    )

            for tid in list(first_seen):
                if tid not in active:
                    del first_seen[tid]
                    alerted.discard(tid)


async def main():
    await AbandonedObjectWorker().consume()

if __name__ == '__main__':
    asyncio.run(main())
