"""Line Crossing, Human Traffic and Vehicle Traffic analytic workers — stateful per ROI."""
import asyncio
from analytic_workers.base import BaseAnalyticWorker

PERSON_IDS = {0}
VEHICLE_IDS = {2, 3, 5, 7}
ALL_IDS = PERSON_IDS | VEHICLE_IDS | {15, 16, 24, 26, 28}


def _build_cross_lines(config: dict, polygon: list, width: int, height: int):
    """Build TWO supervision LineZones — horizontal (X-axis) + vertical (Y-axis) —
    through the centroid of the polygon.

    This catches vehicles regardless of travel direction:
    - Horizontal line: detects left-right / right-left movement
    - Vertical line:   detects top-bottom / bottom-top movement

    If config has an explicit 'line' key (2-point list) only that single line is
    used — the operator drew a precise line already.
    If the polygon has exactly 2 points it is used as a single explicit line.
    """
    import supervision as sv

    # Case 1: explicit line in config
    explicit = config.get('line') if config else None
    if explicit and len(explicit) >= 2:
        p1 = sv.Point(int(explicit[0][0] * width), int(explicit[0][1] * height))
        p2 = sv.Point(int(explicit[1][0] * width), int(explicit[1][1] * height))
        return [sv.LineZone(start=p1, end=p2)]

    # Case 2: polygon with exactly 2 points — treat as explicit line
    if len(polygon) == 2:
        p1 = sv.Point(int(polygon[0][0] * width), int(polygon[0][1] * height))
        p2 = sv.Point(int(polygon[1][0] * width), int(polygon[1][1] * height))
        return [sv.LineZone(start=p1, end=p2)]

    if len(polygon) < 2:
        return []

    # Case 3: polygon zone — build cross (horizontal + vertical) at centroid
    cx = sum(p[0] for p in polygon) / len(polygon)
    cy = sum(p[1] for p in polygon) / len(polygon)
    x_min = min(p[0] for p in polygon)
    x_max = max(p[0] for p in polygon)
    y_min = min(p[1] for p in polygon)
    y_max = max(p[1] for p in polygon)

    # Horizontal line at cy, spanning full x range of polygon
    h1 = sv.Point(int(x_min * width), int(cy * height))
    h2 = sv.Point(int(x_max * width), int(cy * height))
    # Vertical line at cx, spanning full y range of polygon
    v1 = sv.Point(int(cx * width), int(y_min * height))
    v2 = sv.Point(int(cx * width), int(y_max * height))

    lines = []
    if h1.x != h2.x or h1.y != h2.y:
        lines.append(sv.LineZone(start=h1, end=h2))
    if v1.x != v2.x or v1.y != v2.y:
        lines.append(sv.LineZone(start=v1, end=v2))
    return lines


class _TrafficBaseWorker(BaseAnalyticWorker):
    _class_ids: set
    _event_type: str

    def __init__(self):
        super().__init__()
        # roi_id -> list[sv.LineZone]  (1 or 2 lines per ROI)
        self._line_zones: dict[str, list] = {}

    async def process(self, payload: dict):
        import supervision as sv
        import numpy as np

        camera_id = payload['camera_id']
        tenant_id = payload['tenant_id']
        width = payload['frame_width']
        height = payload['frame_height']
        detections = payload['detections']
        frame_path = payload.get('frame_path', '')

        relevant = self.filter_by_classes(detections, self._class_ids)
        if not relevant:
            return

        # Reconstruct sv.Detections from serialized payload
        xyxy = np.array([[d['x1'], d['y1'], d['x2'], d['y2']] for d in relevant], dtype=np.float32)
        class_id = np.array([d['class_id'] for d in relevant])
        confidence = np.array([d['confidence'] for d in relevant])
        tracker_id = np.array([d.get('tracker_id') or 0 for d in relevant])
        sv_dets = sv.Detections(xyxy=xyxy, class_id=class_id, confidence=confidence, tracker_id=tracker_id)

        for roi in payload['rois']:
            roi_id = str(roi['id'])
            config = roi.get('config') or {}
            polygon = roi.get('polygon', [])

            if roi_id not in self._line_zones:
                zones = _build_cross_lines(config, polygon, width, height)
                if not zones:
                    continue
                self._line_zones[roi_id] = zones
                print(f'[TrafficWorker] roi={roi_id[:8]} zones={len(zones)} '
                      f'frame={width}x{height}', flush=True)

            fired = False
            for lz in self._line_zones[roi_id]:
                crossed_in, crossed_out = lz.trigger(detections=sv_dets)
                if crossed_in.any() or crossed_out.any():
                    fired = True
                    break

            if not fired:
                continue

            # Aggregate counts across all line zones
            total_in = sum(lz.in_count for lz in self._line_zones[roi_id])
            total_out = sum(lz.out_count for lz in self._line_zones[roi_id])

            await self.publish_event(
                camera_id=camera_id, tenant_id=tenant_id, roi_id=roi_id,
                event_type=self._event_type,
                event_data={
                    'count_in': total_in,
                    'count_out': total_out,
                    'total': total_in + total_out,
                },
                frame_path=frame_path,
            )


class LineCrossingWorker(_TrafficBaseWorker):
    queue_name = 'ai.detect.line_crossing'
    _class_ids = ALL_IDS
    _event_type = 'line_crossing'


class HumanTrafficWorker(_TrafficBaseWorker):
    queue_name = 'ai.detect.human_traffic'
    _class_ids = PERSON_IDS
    _event_type = 'human_traffic'


class VehicleTrafficWorker(_TrafficBaseWorker):
    queue_name = 'ai.detect.vehicle_traffic'
    _class_ids = VEHICLE_IDS
    _event_type = 'vehicle_traffic'


# ── Entry points (one main per worker mode) ───────────────────────────────────

WORKER_MAP = {
    'line_crossing': LineCrossingWorker,
    'human_traffic': HumanTrafficWorker,
    'vehicle_traffic': VehicleTrafficWorker,
}

async def main():
    import os
    mode = os.getenv('WORKER_MODE', 'line_crossing')
    cls = WORKER_MAP.get(mode, LineCrossingWorker)
    await cls().consume()

if __name__ == '__main__':
    asyncio.run(main())
