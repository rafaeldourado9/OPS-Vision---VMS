"""MOG2-based motion gate inspired by Viseron's motion_detector.

Decides whether a frame has enough motion to justify sending to GPU workers.
Runs entirely on CPU — negligible cost (~0.5ms per frame at 320x240).

Key differences from the inline MOG2 in old service.py:
- Extracted as a testable, per-camera class
- Viseron-style morphological ops: erode(1) + dilate(4) instead of MORPH_OPEN
- Configurable per camera via ROI config overrides
- Exposes motion_ratio for metrics/monitoring
- Supports polygon masks to restrict detection area
"""

import cv2
import numpy as np

# Defaults tuned for typical surveillance cameras
DEFAULT_THRESHOLD = 25          # MOG2 varThreshold (pixel sensitivity)
DEFAULT_HISTORY = 500           # Background model frame count
DEFAULT_LEARNING_RATE = 0.005   # Adaptation speed (0=frozen, 1=instant)
DEFAULT_AREA_THRESHOLD = 0.001  # 0.1% of frame area = motion
DEFAULT_WARMUP_FRAMES = 30      # Skip N frames while model stabilizes
DEFAULT_RESIZE = (320, 240)     # Downscale for efficiency


class MotionGate:
    """Per-camera motion gate using MOG2 background subtraction.

    Usage:
        gate = MotionGate()
        if gate.detect(frame).has_motion:
            publish_to_yolo(frame)
    """

    __slots__ = (
        '_subtractor', '_learning_rate', '_area_threshold',
        '_warmup_remaining', '_warmup_total', '_resize_dim',
        '_kernel_erode', '_kernel_dilate',
        '_frame_count', '_last_ratio', '_skip_streak',
    )

    def __init__(
        self,
        threshold: int = DEFAULT_THRESHOLD,
        history: int = DEFAULT_HISTORY,
        learning_rate: float = DEFAULT_LEARNING_RATE,
        area_threshold: float = DEFAULT_AREA_THRESHOLD,
        warmup_frames: int = DEFAULT_WARMUP_FRAMES,
        resize_dim: tuple[int, int] = DEFAULT_RESIZE,
    ):
        self._subtractor = cv2.createBackgroundSubtractorMOG2(
            history=history,
            varThreshold=threshold,
            detectShadows=False,
        )
        self._learning_rate = learning_rate
        self._area_threshold = area_threshold
        self._warmup_remaining = warmup_frames
        self._warmup_total = warmup_frames
        self._resize_dim = resize_dim
        self._frame_count = 0
        self._last_ratio = 0.0
        self._skip_streak = 0

        # Viseron-style morphological kernels
        self._kernel_erode = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
        self._kernel_dilate = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (8, 8))

    # ── Public API ────────────────────────────────────────────

    def detect(self, frame: np.ndarray, roi_mask: np.ndarray | None = None) -> 'MotionResult':
        """Evaluate motion in frame. Returns MotionResult with fg_mask and metrics.

        Args:
            frame: BGR frame from camera (any resolution).
            roi_mask: Optional binary mask (same size as frame or resize_dim).
                      255 = include, 0 = exclude. Used to restrict detection
                      to specific ROI polygons.
        """
        if frame is None or frame.size == 0:
            # Corrupted/empty frame — safe default: assume motion
            return MotionResult(
                has_motion=True, motion_ratio=1.0, is_warmup=False,
                fg_mask=None, frame_count=self._frame_count,
            )

        self._frame_count += 1

        # Downscale for efficiency
        small = cv2.resize(frame, self._resize_dim)
        gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY) if len(small.shape) == 3 else small

        # Apply MOG2
        fg_mask = self._subtractor.apply(gray, learningRate=self._learning_rate)

        # Warmup: always pass through while background model stabilizes
        if self._warmup_remaining > 0:
            self._warmup_remaining -= 1
            self._last_ratio = 1.0
            return MotionResult(
                has_motion=True, motion_ratio=1.0, is_warmup=True,
                fg_mask=fg_mask, frame_count=self._frame_count,
            )

        # Viseron-style morphological cleanup:
        # 1. Erode removes small noise pixels
        # 2. Dilate reconnects nearby blobs into solid regions
        fg_mask = cv2.erode(fg_mask, self._kernel_erode, iterations=1)
        fg_mask = cv2.dilate(fg_mask, self._kernel_dilate, iterations=4)

        # Apply ROI mask if provided
        if roi_mask is not None:
            if roi_mask.shape != fg_mask.shape:
                roi_mask = cv2.resize(roi_mask, (fg_mask.shape[1], fg_mask.shape[0]))
            fg_mask = cv2.bitwise_and(fg_mask, roi_mask)

        # Calculate motion ratio
        total_pixels = fg_mask.shape[0] * fg_mask.shape[1]
        if total_pixels == 0:
            return MotionResult(
                has_motion=True, motion_ratio=1.0, is_warmup=False,
                fg_mask=fg_mask, frame_count=self._frame_count,
            )

        motion_pixels = cv2.countNonZero(fg_mask)
        motion_ratio = motion_pixels / total_pixels
        self._last_ratio = motion_ratio

        has_motion = motion_ratio >= self._area_threshold
        if has_motion:
            self._skip_streak = 0
        else:
            self._skip_streak += 1

        return MotionResult(
            has_motion=has_motion,
            motion_ratio=motion_ratio,
            is_warmup=False,
            fg_mask=fg_mask,
            frame_count=self._frame_count,
        )

    def reset(self):
        """Reset background model (call after camera reconnection)."""
        self._subtractor = cv2.createBackgroundSubtractorMOG2(
            history=500, varThreshold=25, detectShadows=False,
        )
        self._frame_count = 0
        self._warmup_remaining = self._warmup_total
        self._last_ratio = 0.0
        self._skip_streak = 0

    # ── Properties for monitoring ─────────────────────────────

    @property
    def frame_count(self) -> int:
        return self._frame_count

    @property
    def last_motion_ratio(self) -> float:
        return self._last_ratio

    @property
    def skip_streak(self) -> int:
        """Consecutive frames with no motion (useful for logging)."""
        return self._skip_streak

    @property
    def is_warmed_up(self) -> bool:
        return self._warmup_remaining == 0


class MotionResult:
    """Result of motion detection for a single frame."""

    __slots__ = ('has_motion', 'motion_ratio', 'is_warmup', 'fg_mask', 'frame_count')

    def __init__(
        self,
        has_motion: bool,
        motion_ratio: float,
        is_warmup: bool,
        fg_mask: np.ndarray | None,
        frame_count: int,
    ):
        self.has_motion = has_motion
        self.motion_ratio = motion_ratio
        self.is_warmup = is_warmup
        self.fg_mask = fg_mask
        self.frame_count = frame_count


def detect_motion_in_rois(
    fg_mask: np.ndarray,
    rois: list[dict],
    mask_width: int,
    mask_height: int,
    area_threshold: float = 0.5,
    always_on_types: set[str] | None = None,
) -> tuple[bool, list[dict]]:
    """Check which ROIs have motion inside their polygons.

    Uses the fg_mask from MotionGate.detect() and checks each ROI polygon
    for sufficient motion.

    Args:
        fg_mask: Foreground mask from MOG2 (any resolution).
        rois: List of ROI dicts with 'polygon' (normalized 0-1) and 'ia_type'.
        mask_width: Width of fg_mask.
        mask_height: Height of fg_mask.
        area_threshold: Min % of ROI area with motion pixels (0-100).
        always_on_types: ia_types that bypass motion filter (e.g. {'heatmap'}).

    Returns:
        (has_any_motion, triggered_rois) — the subset of ROIs with motion.
    """
    if always_on_types is None:
        always_on_types = {'heatmap'}

    triggered = []
    for roi in rois:
        ia_type = roi.get('ia_type', '')

        # Always-on analytics bypass motion filter
        if ia_type in always_on_types:
            triggered.append(roi)
            continue

        polygon = roi.get('polygon', [])
        if not polygon or len(polygon) < 3:
            # Empty polygon or line-type ROIs (vehicle_traffic, line_crossing,
            # human_traffic) use a 2-point line — no area to check, always trigger.
            triggered.append(roi)
            continue

        # Convert normalized coords to mask-space pixel coords
        pts = np.array(
            [[int(x * mask_width), int(y * mask_height)] for x, y in polygon],
            dtype=np.int32,
        )

        # Create binary mask for this ROI
        roi_mask = np.zeros(fg_mask.shape[:2], dtype=np.uint8)
        cv2.fillPoly(roi_mask, [pts], 255)

        # Count motion pixels inside
        motion_pixels = cv2.countNonZero(cv2.bitwise_and(fg_mask, roi_mask))
        roi_area = cv2.countNonZero(roi_mask)
        if roi_area == 0:
            continue

        motion_pct = (motion_pixels / roi_area) * 100
        if motion_pct >= area_threshold:
            triggered.append(roi)

    return len(triggered) > 0, triggered
