import logging
import time
from threading import Thread
import cv2

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

from api_client import APIClient
from detection import PlateDetector

API_BASE_URL = "http://gt-vision-backend:8000"

def process_camera_stream(camera_info: dict, detector: PlateDetector, api_client: APIClient):
    rtsp_url = camera_info.get("rtsp_url")
    camera_id = camera_info.get("id")
    camera_name = camera_info.get("name", f"Câmera {camera_id}")
    
    logging.info(f"Iniciando processamento para a câmera: {camera_name} ({rtsp_url})")
    
    cap = cv2.VideoCapture(rtsp_url)
    if not cap.isOpened():
        logging.error(f"Não foi possível abrir o stream de vídeo para a câmera {camera_name}.")
        return

    while True:
        ret, frame = cap.read()
        if not ret:
            logging.warning(f"Stream da câmera {camera_name} terminou. Tentando reconectar em 10 segundos.")
            cap.release()
            time.sleep(10)
            cap = cv2.VideoCapture(rtsp_url)
            if not cap.isOpened():
                logging.error(f"Falha ao reconectar à câmera {camera_name}. Encerrando thread.")
                break
            continue

        try:
            detections = detector.detect_and_recognize(frame, camera_id)
            for detection in detections:
                plate_text = detection.get("plate")
                image_path = detection.get("image_path")
                if plate_text and image_path:
                    logging.info(f"Placa detectada pela câmera {camera_name}: {plate_text}")
                    api_client.send_sighting_to_api(
                        plate=plate_text,
                        image_filename=image_path,
                        camera_id=camera_id
                    )
        except Exception as e:
            logging.error(f"Erro durante o processamento do frame da câmera {camera_name}: {e}")

    cap.release()
    logging.info(f"Processamento para a câmera {camera_name} encerrado.")

def main():
    logging.info("Iniciando o serviço AI-Processor...")
    logging.info("Pipeline: COCO (vehicles) → YOUR yolov8n.pt (plates) → OCR")
    
    api_client = APIClient(base_url=API_BASE_URL)
    plate_detector = PlateDetector(
        vehicle_model_path="yolov8n-coco.pt",     # Will download COCO pretrained
        plate_model_path="yolov8n.pt"             # YOUR trained model (already exists)
    )

    while not api_client.check_api_health():
        logging.info("Aguardando a API do backend... tentando novamente em 5 segundos.")
        time.sleep(5)
        
    logging.info("Backend API está disponível. Buscando câmaras...")
    
    cameras = api_client.get_cameras_from_api()

    if not cameras:
        logging.warning("Nenhuma câmera encontrada para processar. O serviço vai terminar.")
        return

    threads = []
    for camera in cameras:
        if camera.get("is_active"):
            thread = Thread(target=process_camera_stream, args=(camera, plate_detector, api_client))
            threads.append(thread)
            thread.start()
        else:
            logging.info(f"Câmera '{camera.get('name')}' está inativa e não será processada.")

    for thread in threads:
        thread.join()

if __name__ == "__main__":
    main()