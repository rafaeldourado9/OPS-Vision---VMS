"""Object Detection analytic worker."""
import asyncio
import os
from analytic_workers.base import BaseAnalyticWorker

ALL_NAMES = {
    0: 'person', 1: 'bicycle', 2: 'car', 3: 'motorcycle',
    5: 'bus', 7: 'truck', 15: 'cat', 16: 'dog',
    24: 'backpack', 26: 'handbag', 28: 'suitcase',
}
ALL_IDS = set(ALL_NAMES.keys())
DEDUP_TTL = int(os.getenv('DEDUP_TTL_SECONDS', '30'))


class ObjectDetectionWorker(BaseAnalyticWorker):
    queue_name = 'ai.detect.object_detection'

    async def process(self, payload: dict):
        camera_id = payload['camera_id']
        tenant_id = payload['tenant_id']
        width = payload['frame_width']
        height = payload['frame_height']
        detections = payload['detections']
        frame_path = payload.get('frame_path', '')

        for roi in payload['rois']:
            roi_id = str(roi['id'])
            config = roi.get('config') or {}
            class_filter = config.get('classes')
            polygon = roi.get('polygon', [])

            if class_filter:
                name_to_id = {v: k for k, v in ALL_NAMES.items()}
                class_ids = {name_to_id[c] for c in class_filter if c in name_to_id}
            else:
                class_ids = ALL_IDS

            relevant = self.filter_by_classes(detections, class_ids)
            in_zone = self.in_polygon(relevant, polygon, width, height)

            for det in in_zone:
                dedup_key = f'dedup:object:{camera_id}:{roi_id}:{det["class_name"]}'
                if self.is_dedup(dedup_key):
                    continue
                self.set_dedup(dedup_key, DEDUP_TTL)

                await self.publish_event(
                    camera_id=camera_id, tenant_id=tenant_id, roi_id=roi_id,
                    event_type='object_detected',
                    event_data={
                        'class': det['class_name'],
                        'confidence': det['confidence'],
                        'bbox': [det['x1'], det['y1'], det['x2'], det['y2']],
                    },
                    frame_path=frame_path,
                )


async def main():
    await ObjectDetectionWorker().consume()

if __name__ == '__main__':
    asyncio.run(main())
