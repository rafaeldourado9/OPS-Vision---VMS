"""Crowd detection analytic worker."""
import asyncio
import os
from analytic_workers.base import BaseAnalyticWorker

PERSON_IDS = {0}


class CrowdWorker(BaseAnalyticWorker):
    queue_name = 'ai.detect.crowd'

    async def process(self, payload: dict):
        camera_id = payload['camera_id']
        tenant_id = payload['tenant_id']
        width = payload['frame_width']
        height = payload['frame_height']
        detections = payload['detections']
        frame_path = payload.get('frame_path', '')

        persons = self.filter_by_classes(detections, PERSON_IDS)

        for roi in payload['rois']:
            roi_id = str(roi['id'])
            threshold = int(roi.get('config', {}).get('threshold', 2))
            polygon = roi.get('polygon', [])

            in_zone = self.in_polygon(persons, polygon, width, height)
            count = len(in_zone)

            if count < threshold:
                continue

            dedup_key = f'dedup:crowd:{camera_id}:{roi_id}:{count}'
            if self.is_dedup(dedup_key):
                continue
            self.set_dedup(dedup_key, 15)

            await self.publish_event(
                camera_id=camera_id, tenant_id=tenant_id, roi_id=roi_id,
                event_type='crowd',
                event_data={'count': count, 'threshold': threshold},
                frame_path=frame_path,
            )


async def main():
    await CrowdWorker().consume()

if __name__ == '__main__':
    asyncio.run(main())
