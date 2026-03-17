"""Tests for MotionGate — Viseron-style MOG2 motion detection."""
import numpy as np
import pytest
import time

from worker.motion import MotionGate, MotionResult, detect_motion_in_rois


class TestMotionGateInit:
    def test_default_params(self):
        gate = MotionGate()
        assert gate.frame_count == 0
        assert gate.skip_streak == 0
        assert not gate.is_warmed_up

    def test_custom_params(self):
        gate = MotionGate(
            threshold=30, history=200, learning_rate=0.01,
            area_threshold=0.05, warmup_frames=10, resize_dim=(160, 120),
        )
        assert not gate.is_warmed_up


class TestMotionGateWarmup:
    def test_warmup_always_returns_true(self):
        gate = MotionGate(warmup_frames=5)
        black = np.zeros((480, 640, 3), dtype=np.uint8)
        for _ in range(5):
            result = gate.detect(black)
            assert result.has_motion is True
            assert result.is_warmup is True

    def test_warmup_completes_after_n_frames(self):
        gate = MotionGate(warmup_frames=3)
        frame = np.full((480, 640, 3), 128, dtype=np.uint8)
        for _ in range(3):
            gate.detect(frame)
        assert gate.is_warmed_up
        result = gate.detect(frame)
        assert result.is_warmup is False

    def test_frame_count_increments(self):
        gate = MotionGate(warmup_frames=2)
        frame = np.zeros((100, 100, 3), dtype=np.uint8)
        gate.detect(frame)
        gate.detect(frame)
        gate.detect(frame)
        assert gate.frame_count == 3


class TestMotionGateDetection:
    def test_static_scene_no_motion(self):
        """After warmup, a static scene should produce no motion."""
        gate = MotionGate(warmup_frames=5, area_threshold=0.001)
        static = np.full((480, 640, 3), 128, dtype=np.uint8)

        # Warmup + build background model
        for _ in range(40):
            gate.detect(static)

        result = gate.detect(static)
        assert result.has_motion is False
        assert result.motion_ratio < 0.001

    def test_significant_motion_detected(self):
        """A large change in the scene should be detected."""
        gate = MotionGate(warmup_frames=5, area_threshold=0.001)
        bg = np.full((480, 640, 3), 128, dtype=np.uint8)

        # Build background model
        for _ in range(40):
            gate.detect(bg)

        # Introduce motion (large white rectangle)
        motion = bg.copy()
        motion[100:350, 100:500] = 255
        result = gate.detect(motion)
        assert result.has_motion is True
        assert result.motion_ratio > 0.001

    def test_small_noise_ignored(self):
        """Tiny noise (1-2 pixels) should be filtered by morphological ops."""
        gate = MotionGate(warmup_frames=5, area_threshold=0.01)
        bg = np.full((480, 640, 3), 128, dtype=np.uint8)

        for _ in range(40):
            gate.detect(bg)

        # Add salt-and-pepper noise (very sparse)
        noisy = bg.copy()
        rng = np.random.default_rng(42)
        noise_mask = rng.random(bg.shape[:2]) > 0.999  # 0.1% of pixels
        noisy[noise_mask] = 255
        result = gate.detect(noisy)
        # Morphological erode should remove these tiny spots
        assert result.motion_ratio < 0.01

    def test_skip_streak_tracks_consecutive_no_motion(self):
        gate = MotionGate(warmup_frames=2, area_threshold=0.5)
        frame = np.full((100, 100, 3), 128, dtype=np.uint8)

        # Warmup
        for _ in range(30):
            gate.detect(frame)

        # More static frames
        gate.detect(frame)
        gate.detect(frame)
        gate.detect(frame)
        assert gate.skip_streak >= 1


class TestMotionGateReset:
    def test_reset_clears_state(self):
        gate = MotionGate(warmup_frames=5)
        frame = np.zeros((100, 100, 3), dtype=np.uint8)

        for _ in range(10):
            gate.detect(frame)

        assert gate.frame_count == 10
        assert gate.is_warmed_up

        gate.reset()
        assert gate.frame_count == 0
        assert not gate.is_warmed_up
        assert gate.skip_streak == 0

    def test_reset_restarts_warmup(self):
        gate = MotionGate(warmup_frames=3)
        frame = np.zeros((100, 100, 3), dtype=np.uint8)

        for _ in range(5):
            gate.detect(frame)
        assert gate.is_warmed_up

        gate.reset()
        result = gate.detect(frame)
        assert result.is_warmup is True


class TestMotionGateEdgeCases:
    def test_empty_frame_returns_motion(self):
        """Corrupted/empty frames should default to has_motion=True (safe)."""
        gate = MotionGate()
        empty = np.zeros((0, 0, 3), dtype=np.uint8)
        result = gate.detect(empty)
        assert result.has_motion is True

    def test_none_frame_returns_motion(self):
        gate = MotionGate()
        result = gate.detect(None)
        assert result.has_motion is True

    def test_grayscale_frame_accepted(self):
        gate = MotionGate(warmup_frames=2)
        gray = np.full((480, 640), 128, dtype=np.uint8)
        result = gate.detect(gray)
        assert result.has_motion is True  # warmup

    def test_roi_mask_restricts_detection(self):
        """Motion outside the ROI mask should be ignored."""
        gate = MotionGate(warmup_frames=5, area_threshold=0.01)
        bg = np.full((480, 640, 3), 128, dtype=np.uint8)

        # Mask: only bottom half is active
        mask = np.zeros((480, 640), dtype=np.uint8)
        mask[240:, :] = 255

        for _ in range(40):
            gate.detect(bg, roi_mask=mask)

        # Motion only in top half (should be masked out)
        motion = bg.copy()
        motion[0:100, :] = 255
        result = gate.detect(motion, roi_mask=mask)
        assert result.has_motion is False


class TestMotionGatePerformance:
    def test_detection_under_5ms(self):
        """MOG2 at 320x240 should process in under 5ms."""
        gate = MotionGate(warmup_frames=5)
        frame = np.random.randint(0, 255, (1080, 1920, 3), dtype=np.uint8)

        # Warmup
        for _ in range(10):
            gate.detect(frame)

        # Measure
        iterations = 100
        start = time.perf_counter()
        for _ in range(iterations):
            gate.detect(frame)
        elapsed_per_frame = (time.perf_counter() - start) / iterations

        assert elapsed_per_frame < 0.005, f'Too slow: {elapsed_per_frame*1000:.1f}ms'


class TestDetectMotionInROIs:
    """Tests for the per-ROI polygon motion check."""

    def _make_fg_mask(self, w: int, h: int, motion_rect=None) -> np.ndarray:
        mask = np.zeros((h, w), dtype=np.uint8)
        if motion_rect:
            x1, y1, x2, y2 = motion_rect
            mask[y1:y2, x1:x2] = 255
        return mask

    def test_always_on_types_bypass_motion(self):
        fg_mask = np.zeros((100, 100), dtype=np.uint8)  # No motion at all
        rois = [{'ia_type': 'heatmap', 'polygon': [[0, 0], [1, 0], [1, 1], [0, 1]]}]
        has_motion, triggered = detect_motion_in_rois(fg_mask, rois, 100, 100)
        assert has_motion is True
        assert len(triggered) == 1

    def test_no_polygon_passes_through(self):
        fg_mask = np.zeros((100, 100), dtype=np.uint8)
        rois = [{'ia_type': 'crowd', 'polygon': []}]
        has_motion, triggered = detect_motion_in_rois(fg_mask, rois, 100, 100)
        assert has_motion is True
        assert len(triggered) == 1

    def test_motion_inside_roi_triggers(self):
        # Motion in center
        fg_mask = self._make_fg_mask(100, 100, motion_rect=(30, 30, 70, 70))
        # ROI covering center area (normalized coords)
        rois = [{'ia_type': 'intrusion', 'polygon': [[0.2, 0.2], [0.8, 0.2], [0.8, 0.8], [0.2, 0.8]]}]
        has_motion, triggered = detect_motion_in_rois(
            fg_mask, rois, 100, 100, area_threshold=0.1,
        )
        assert has_motion is True
        assert len(triggered) == 1

    def test_motion_outside_roi_does_not_trigger(self):
        # Motion in top-left corner
        fg_mask = self._make_fg_mask(100, 100, motion_rect=(0, 0, 10, 10))
        # ROI in bottom-right
        rois = [{'ia_type': 'intrusion', 'polygon': [[0.7, 0.7], [1.0, 0.7], [1.0, 1.0], [0.7, 1.0]]}]
        has_motion, triggered = detect_motion_in_rois(
            fg_mask, rois, 100, 100, area_threshold=0.1,
        )
        assert has_motion is False
        assert len(triggered) == 0

    def test_multiple_rois_partial_trigger(self):
        # Motion in left half
        fg_mask = self._make_fg_mask(100, 100, motion_rect=(0, 0, 50, 100))
        rois = [
            {'ia_type': 'crowd', 'polygon': [[0, 0], [0.4, 0], [0.4, 1], [0, 1]]},      # Left → motion
            {'ia_type': 'intrusion', 'polygon': [[0.7, 0], [1, 0], [1, 1], [0.7, 1]]},   # Right → no motion
        ]
        has_motion, triggered = detect_motion_in_rois(
            fg_mask, rois, 100, 100, area_threshold=1.0,
        )
        assert has_motion is True
        assert len(triggered) == 1
        assert triggered[0]['ia_type'] == 'crowd'

    def test_empty_rois_returns_false(self):
        fg_mask = np.zeros((100, 100), dtype=np.uint8)
        has_motion, triggered = detect_motion_in_rois(fg_mask, [], 100, 100)
        assert has_motion is False
        assert triggered == []

    def test_custom_always_on_types(self):
        fg_mask = np.zeros((100, 100), dtype=np.uint8)
        rois = [{'ia_type': 'custom_always', 'polygon': [[0, 0], [1, 0], [1, 1], [0, 1]]}]
        has_motion, triggered = detect_motion_in_rois(
            fg_mask, rois, 100, 100, always_on_types={'custom_always'},
        )
        assert has_motion is True
