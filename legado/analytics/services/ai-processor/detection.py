import cv2
import os
import logging
from ultralytics import YOLO
from fast_plate_ocr.inference.plate_recognizer import LicensePlateRecognizer
import numpy as np

class PlateDetector:
    def __init__(self, vehicle_model_path: str, plate_model_path: str):
        # Stage 1: Vehicle detection (download COCO model)
        self.vehicle_model = YOLO(vehicle_model_path)  # Will auto-download from ultralytics
        # Stage 2: Plate detection (YOUR trained model)
        self.plate_model = YOLO(plate_model_path)  # yolov8n.pt = your custom model
        # Stage 3: OCR
        self.plate_recognizer = LicensePlateRecognizer(hub_ocr_model="cct-xs-v1-global-model")
        self.logger = logging.getLogger(__name__)
        self.logger.info(f"Vehicle detector (COCO): {vehicle_model_path}")
        self.logger.info(f"Plate detector (CUSTOM): {plate_model_path}")
        self.captures_dir = "/app/captures"
        os.makedirs(self.captures_dir, exist_ok=True)

    def detect_and_recognize(self, frame: np.ndarray, camera_id: int) -> list:
        detections = []
        
        # Stage 1: Detect vehicles (car=2, motorcycle=3, bus=5, truck=7)
        vehicle_results = self.vehicle_model(frame, classes=[2, 3, 5, 7], conf=0.4, verbose=False)
        
        plate_crops = []
        for result in vehicle_results:
            for box in result.boxes:
                x1, y1, x2, y2 = map(int, box.xyxy[0])
                vehicle_crop = frame[y1:y2, x1:x2]
                
                # Stage 2: Detect plates using YOUR trained model
                plate_results = self.plate_model(vehicle_crop, conf=0.5, verbose=False)
                
                for plate_result in plate_results:
                    for plate_box in plate_result.boxes:
                        px1, py1, px2, py2 = map(int, plate_box.xyxy[0])
                        plate_crop = vehicle_crop[py1:py2, px1:px2]
                        if plate_crop.size > 0:
                            plate_crops.append(plate_crop)
        
        if not plate_crops:
            return detections

        try:
            # Stage 3: OCR on detected plates
            recognized_plates_text = self.plate_recognizer.run(plate_crops)
            
            for i, plate_text in enumerate(recognized_plates_text):
                if plate_text:
                    plate_text_clean = plate_text.replace('_', '')
                    if len(plate_text_clean) >= 6:  # Filter valid plates
                        image_filename = f"capture_{camera_id}_{plate_text_clean}_{cv2.getTickCount()}.jpg"
                        image_path = os.path.join(self.captures_dir, image_filename)
                        cv2.imwrite(image_path, plate_crops[i])
                        detections.append({
                            "plate": plate_text_clean,
                            "image_path": image_path
                        })
        except Exception as e:
            self.logger.error(f"Erro ao reconhecer matrículas: {e}")

        return detections