"""
FacialAnalyzer — InsightFace buffalo_l for face detection + recognition.

Capabilities:
- Multi-face detection (unlimited simultaneous faces per frame)
- Multi-angle tolerance (yaw ±90°, pitch ±45°) via RetinaFace detector
- Distance-resilient: det_size=640 catches faces from ~15px up
- Per-tenant embedding database with cosine similarity matching
- GPU-accelerated (ONNX Runtime CUDA EP) with CPU fallback
- < 200ms per frame on GPU (detection + N embeddings)
"""

import os
import threading
from pathlib import Path

import cv2
import numpy as np

SIMILARITY_THRESHOLD = float(os.getenv('FACIAL_SIMILARITY_THRESHOLD', '0.5'))
DET_SIZE = int(os.getenv('FACIAL_DET_SIZE', '640'))
DET_THRESH = float(os.getenv('FACIAL_DET_THRESH', '0.3'))
MIN_FACE_PX = int(os.getenv('FACIAL_MIN_FACE_PX', '20'))


class FacialAnalyzer:
    """InsightFace buffalo_l face detection and recognition engine."""

    def __init__(self):
        import insightface
        from insightface.app import FaceAnalysis

        providers = self._get_providers()
        print(f'[FacialAnalyzer] ONNX providers: {providers}', flush=True)

        self._app = FaceAnalysis(
            name='buffalo_l',
            root=os.getenv('INSIGHTFACE_HOME', os.path.expanduser('~/.insightface')),
            providers=providers,
        )
        # det_size=(640,640) gives good accuracy at varying distances
        # Lower det_thresh catches more faces at extreme angles/distances
        self._app.prepare(ctx_id=0, det_size=(DET_SIZE, DET_SIZE), det_thresh=DET_THRESH)

        # Per-tenant embeddings: {tenant_id: [(person_id, name, [emb1, emb2, ...]), ...]}
        self._embeddings: dict[str, list[tuple[str, str, list[np.ndarray]]]] = {}
        self._lock = threading.Lock()

        print(f'[FacialAnalyzer] Pronto (det_size={DET_SIZE}, det_thresh={DET_THRESH}, '
              f'similarity={SIMILARITY_THRESHOLD}, min_face={MIN_FACE_PX}px)', flush=True)

    @staticmethod
    def _get_providers() -> list[str]:
        """Select best available ONNX execution provider."""
        try:
            import onnxruntime as ort
            available = ort.get_available_providers()
            if 'CUDAExecutionProvider' in available:
                return ['CUDAExecutionProvider', 'CPUExecutionProvider']
            if 'TensorrtExecutionProvider' in available:
                return ['TensorrtExecutionProvider', 'CUDAExecutionProvider', 'CPUExecutionProvider']
        except Exception:
            pass
        return ['CPUExecutionProvider']

    def _extract_embedding(self, photo_path: str) -> np.ndarray | None:
        """Extract face embedding from a photo file. Returns None on failure."""
        if not photo_path or not Path(photo_path).exists():
            return None
        img = cv2.imread(photo_path)
        if img is None:
            return None
        faces = self._app.get(img)
        if not faces:
            return None
        best_face = max(faces, key=lambda f: (f.bbox[2] - f.bbox[0]) * (f.bbox[3] - f.bbox[1]))
        return best_face.normed_embedding

    def load_persons(self, persons: list[dict]):
        """
        Load known persons and extract face embeddings from ALL their photos.
        Each person can have: 1 primary photo + N extra_photos (different angles).
        All embeddings are stored per-person; matching uses the best (max similarity).

        Args:
            persons: list of dicts with keys:
                id, name, tenant_id, photo_path,
                extra_photos: [{photo_path, label}, ...]
        """
        # {tenant_id: [(person_id, name, [emb1, emb2, ...]), ...]}
        tenant_map: dict[str, list[tuple[str, str, list[np.ndarray]]]] = {}
        total_embeddings = 0
        skipped = 0

        for p in persons:
            person_id = str(p['id'])
            name = p['name']
            tenant_id = str(p['tenant_id'])

            embeddings = []

            # Primary photo
            emb = self._extract_embedding(p.get('photo_path'))
            if emb is not None:
                embeddings.append(emb)
            else:
                print(f'[FacialAnalyzer] Foto principal sem rosto: {name}', flush=True)

            # Extra photos (different angles)
            for extra in p.get('extra_photos', []):
                extra_path = extra.get('photo_path')
                emb = self._extract_embedding(extra_path)
                if emb is not None:
                    embeddings.append(emb)
                else:
                    label = extra.get('label', 'extra')
                    print(f'[FacialAnalyzer] Foto extra sem rosto: {name} ({label})', flush=True)

            if not embeddings:
                print(f'[FacialAnalyzer] Nenhum embedding para: {name}', flush=True)
                skipped += 1
                continue

            if tenant_id not in tenant_map:
                tenant_map[tenant_id] = []
            tenant_map[tenant_id].append((person_id, name, embeddings))
            total_embeddings += len(embeddings)

        with self._lock:
            self._embeddings = tenant_map

        n_persons = sum(len(v) for v in tenant_map.values())
        print(f'[FacialAnalyzer] Embeddings carregados: {n_persons} pessoas, '
              f'{total_embeddings} fotos, {skipped} ignoradas '
              f'({len(tenant_map)} tenants)', flush=True)

    def analyze(self, frame: np.ndarray, polygon_px: list, tenant_id: str) -> list[dict]:
        """
        Detect and recognize faces in a frame region.

        Args:
            frame: BGR image (full frame from camera)
            polygon_px: ROI polygon in pixel coords [[x,y], ...] — if empty, uses full frame
            tenant_id: tenant for embedding lookup

        Returns:
            List of event dicts:
            {
                'event_type': 'facial_match' | 'facial_unknown',
                'event_data': {'person_id', 'person_name', 'similarity', 'face_bbox'},
                'face_image': cropped face ndarray
            }
        """
        if frame is None or frame.size == 0:
            return []

        # Crop to ROI if polygon provided
        roi_frame, offset_x, offset_y = self._crop_to_roi(frame, polygon_px)
        if roi_frame is None or roi_frame.size == 0:
            return []

        # Detect all faces in ROI
        faces = self._app.get(roi_frame)
        if not faces:
            return []

        # Get tenant embeddings
        with self._lock:
            known = self._embeddings.get(str(tenant_id), [])

        events = []
        for face in faces:
            bbox = face.bbox.astype(int)
            face_w = bbox[2] - bbox[0]
            face_h = bbox[3] - bbox[1]

            # Skip tiny faces (too small for reliable recognition)
            if face_w < MIN_FACE_PX or face_h < MIN_FACE_PX:
                continue

            # Crop face with padding for snapshot
            face_img = self._crop_face(roi_frame, bbox, padding_ratio=0.3)

            embedding = face.normed_embedding  # L2-normalized 512-d vector

            # Absolute bbox in original frame coords
            abs_bbox = [
                int(bbox[0] + offset_x),
                int(bbox[1] + offset_y),
                int(bbox[2] + offset_x),
                int(bbox[3] + offset_y),
            ]

            if not known:
                events.append({
                    'event_type': 'facial_unknown',
                    'event_data': {
                        'person_id': 'unknown',
                        'person_name': 'Desconhecido',
                        'similarity': 0.0,
                        'face_bbox': abs_bbox,
                        'det_score': float(face.det_score),
                    },
                    'face_image': face_img,
                })
                continue

            # Compare against all known persons (multi-embedding per person)
            best_id, best_name, best_sim = self._match_embedding(embedding, known)

            if best_sim >= SIMILARITY_THRESHOLD:
                events.append({
                    'event_type': 'facial_match',
                    'event_data': {
                        'person_id': best_id,
                        'person_name': best_name,
                        'similarity': round(float(best_sim), 4),
                        'face_bbox': abs_bbox,
                        'det_score': float(face.det_score),
                    },
                    'face_image': face_img,
                })
            else:
                events.append({
                    'event_type': 'facial_unknown',
                    'event_data': {
                        'person_id': 'unknown',
                        'person_name': 'Desconhecido',
                        'similarity': round(float(best_sim), 4),
                        'face_bbox': abs_bbox,
                        'det_score': float(face.det_score),
                    },
                    'face_image': face_img,
                })

        return events

    @staticmethod
    def _match_embedding(
        query: np.ndarray,
        known: list[tuple[str, str, list[np.ndarray]]],
    ) -> tuple[str, str, float]:
        """
        Match a face embedding against all known persons.
        Each person may have multiple embeddings (different angles/photos).
        Returns the person with the highest similarity across all their photos.
        """
        best_person_id = ''
        best_person_name = ''
        best_similarity = -1.0

        for person_id, name, embeddings_list in known:
            # Stack all embeddings for this person (M, 512)
            matrix = np.stack(embeddings_list)
            # Cosine similarity with all photos of this person
            sims = matrix @ query  # (M,)
            max_sim = float(np.max(sims))

            if max_sim > best_similarity:
                best_similarity = max_sim
                best_person_id = person_id
                best_person_name = name

        return best_person_id, best_person_name, best_similarity

    @staticmethod
    def _crop_to_roi(
        frame: np.ndarray,
        polygon_px: list,
    ) -> tuple[np.ndarray | None, int, int]:
        """Crop frame to ROI bounding box. Returns (cropped, offset_x, offset_y)."""
        if not polygon_px or len(polygon_px) < 3:
            return frame, 0, 0

        pts = np.array(polygon_px, dtype=np.int32)
        x, y, w, h = cv2.boundingRect(pts)

        if w <= 0 or h <= 0:
            return None, 0, 0

        fh, fw = frame.shape[:2]
        x1 = max(0, x)
        y1 = max(0, y)
        x2 = min(fw, x + w)
        y2 = min(fh, y + h)

        return frame[y1:y2, x1:x2].copy(), x1, y1

    @staticmethod
    def _crop_face(
        image: np.ndarray,
        bbox: np.ndarray,
        padding_ratio: float = 0.3,
    ) -> np.ndarray:
        """Crop face from image with padding for better snapshot quality."""
        h, w = image.shape[:2]
        x1, y1, x2, y2 = bbox
        face_w = x2 - x1
        face_h = y2 - y1

        pad_x = int(face_w * padding_ratio)
        pad_y = int(face_h * padding_ratio)

        cx1 = max(0, x1 - pad_x)
        cy1 = max(0, y1 - pad_y)
        cx2 = min(w, x2 + pad_x)
        cy2 = min(h, y2 + pad_y)

        crop = image[cy1:cy2, cx1:cx2]
        if crop.size == 0:
            return image[max(0, y1):min(h, y2), max(0, x1):min(w, x2)]
        return crop
