"""
AI-Processor Service - ALPR com YOLOv8n + fast-plate-ocr
"""
import logging
import json
import hashlib
from typing import Dict, Any, Optional, Set
from pathlib import Path
from datetime import datetime
import numpy as np
import cv2

from services import AIServiceInterface

logger = logging.getLogger(__name__)


class AIProcessorService(AIServiceInterface):
    """Serviço ALPR usando YOLOv8n + fast-plate-ocr"""
    
    def __init__(self):
        self._model = None
        self._ocr = None
        self._config = {}
        self._initialized = False
        self._snapshots_dir = Path(__file__).parent / "snapshots"
        self._prev_frames = {}  # Store previous frame per camera for motion detection
    
    @property
    def service_name(self) -> str:
        return "ai-processor"
    
    @property
    def version(self) -> str:
        return "1.0.0"
    
    def _normalize_plate(self, text: str) -> str:
        return text.upper().replace(' ', '').replace('-', '').replace('_', '')
    
    def _generate_vehicle_id(self, plate: str) -> str:
        return hashlib.md5(plate.encode()).hexdigest()[:12]
    
    async def initialize(self, config: Dict[str, Any]) -> None:
        try:
            from ultralytics import YOLO
            from fast_plate_ocr.inference.plate_recognizer import LicensePlateRecognizer
            
            self._config = config
            model_path = '/app/services/yolov8n.pt'
            
            logger.info(f"Loading YOLO model {model_path}...")
            self._model = YOLO(model_path)
            logger.info(f"Model classes: {self._model.names}")
            
            logger.info("Loading fast-plate-ocr...")
            self._ocr = LicensePlateRecognizer(hub_ocr_model="cct-xs-v1-global-model")
            
            self._snapshots_dir.mkdir(parents=True, exist_ok=True)
            self._initialized = True
            
            logger.info(f"{self.service_name} v{self.version} initialized")
            
        except Exception as e:
            logger.error(f"Error initializing {self.service_name}: {e}")
            raise
    
    async def process_frame(
        self, 
        frame: np.ndarray, 
        metadata: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        if not self._initialized:
            return None
        
        try:
            camera_id = metadata['camera_id'].split('_')[-1]
            confidence_threshold = self._config.get('confidence_threshold', 0.3)
            
            # Motion detection
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            gray = cv2.GaussianBlur(gray, (21, 21), 0)
            
            if camera_id not in self._prev_frames:
                self._prev_frames[camera_id] = gray
                return None
            
            frame_delta = cv2.absdiff(self._prev_frames[camera_id], gray)
            thresh = cv2.threshold(frame_delta, 25, 255, cv2.THRESH_BINARY)[1]
            motion_pixels = cv2.countNonZero(thresh)
            motion_percent = (motion_pixels / (frame.shape[0] * frame.shape[1])) * 100
            
            self._prev_frames[camera_id] = gray
            
            # Only process if motion > 1%
            if motion_percent < 1.0:
                return None
            
            logger.info(f"[{camera_id}] Motion detected: {motion_percent:.2f}%")
            
            # Detecta placas (classe 0)
            results = self._model(frame, conf=confidence_threshold, classes=[0], verbose=False)
            
            plate_crops = []
            bboxes = []
            
            for result in results:
                for box in result.boxes:
                    x1, y1, x2, y2 = map(int, box.xyxy[0])
                    crop = frame[y1:y2, x1:x2]
                    plate_crops.append(crop)
                    bboxes.append({'x1': x1, 'y1': y1, 'x2': x2, 'y2': y2})
            
            if not plate_crops:
                return None
            
            # OCR
            recognized_plates = self._ocr.run(plate_crops)
            
            for i, plate_text in enumerate(recognized_plates):
                if not plate_text:
                    continue
                
                plate_text = self._normalize_plate(plate_text)
                
                if len(plate_text) < 6:
                    continue
                
                vehicle_id = self._generate_vehicle_id(plate_text)
                
                # Estrutura de diretórios
                camera_dir = self._snapshots_dir / camera_id
                vehicle_dir = camera_dir / plate_text
                vehicle_dir.mkdir(parents=True, exist_ok=True)
                
                # Foto completa
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                photo_path = vehicle_dir / f"{plate_text}_{timestamp}.jpg"
                cv2.imwrite(str(photo_path), frame)
                
                # Recorte da placa
                plate_path = vehicle_dir / f"{plate_text}_plate.jpg"
                cv2.imwrite(str(plate_path), plate_crops[i])
                
                # JSON
                vehicle_data = {
                    'vehicle_id': vehicle_id,
                    'plate': plate_text,
                    'camera_id': camera_id,
                    'timestamp': datetime.now().isoformat(),
                    'confidence': confidence_threshold,
                    'detection_class': 'license_plate',
                    'model': 'yolov8n',
                    'brand': 'N/A',
                    'bbox': bboxes[i],
                    'photo': str(photo_path.name),
                    'plate_snapshot': str(plate_path.name)
                }
                
                json_path = vehicle_dir / f"{plate_text}_data.json"
                with open(json_path, 'w', encoding='utf-8') as f:
                    json.dump(vehicle_data, f, indent=2, ensure_ascii=False)
                
                logger.info(f"[{camera_id}] Plate: {plate_text}")
                
                return {
                    'service': self.service_name,
                    'vehicle_id': vehicle_id,
                    'plate': plate_text,
                    'camera_id': camera_id
                }
            
            return None
            
        except Exception as e:
            logger.error(f"Error processing frame: {e}")
            return None
    
    async def health_check(self) -> Dict[str, Any]:
        return {
            'status': 'healthy' if self._initialized else 'unhealthy',
            'details': {
                'model_loaded': self._model is not None,
                'ocr_loaded': self._ocr is not None
            }
        }
    
    async def shutdown(self) -> None:
        self._model = None
        self._ocr = None
        self._initialized = False
        logger.info(f"{self.service_name} shutdown")
