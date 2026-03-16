"""Intrusion detection analytic worker."""
import asyncio
from analytic_workers.base import BaseAnalyticWorker

PERSON_IDS = {0}
VEHICLE_IDS = {2, 3, 5, 7}
_NAME = {0: 'person', 1: 'bicycle', 2: 'car', 3: 'motorcycle', 5: 'bus', 7: 'truck'}


class IntrusionWorker(BaseAnalyticWorker):
    queue_name = 'ai.detect.intrusion'

    async def process(self, payload: dict):
        camera_id = payload['camera_id']
        tenant_id = payload['tenant_id']
        width = payload['frame_width']
        height = payload['frame_height']
        detections = payload['detections']
        frame_path = payload.get('frame_path', '')
        dedup_ttl = int(os.environ.get('DEDUP_TTL_SECONDS', '30'))

        for roi in payload['rois']:
            roi_id = str(roi['id'])
            config = roi.get('config') or {}
            class_filter = config.get('classes', ['person'])
            polygon = roi.get('polygon', [])

            class_ids = {0} if 'person' in class_filter else set()
            for c in class_filter:
                if c in ('car', 'vehicle'):
                    class_ids |= VEHICLE_IDS

            relevant = self.filter_by_classes(detections, class_ids or PERSON_IDS)
            in_zone = self.in_polygon(relevant, polygon, width, height)

            for det in in_zone:
                tid = det.get('tracker_id') or 0
                dedup_key = f'dedup:intrusion:{camera_id}:{roi_id}:{tid}'
                if self.is_dedup(dedup_key):
                    continue
                self.set_dedup(dedup_key, dedup_ttl)

                await self.publish_event(
                    camera_id=camera_id, tenant_id=tenant_id, roi_id=roi_id,
                    event_type='intrusion',
                    event_data={
                        'class': det['class_name'],
                        'confidence': det['confidence'],
                        'track_id': tid,
                    },
                    frame_path=frame_path,
                )


import os

async def main():
    await IntrusionWorker().consume()

if __name__ == '__main__':
    asyncio.run(main())
