import os
import requests
import logging
from typing import List, Dict, Any

class APIClient:
    def __init__(self, base_url: str):
        self.base_url = base_url
        self.logger = logging.getLogger(__name__)
        self.api_key = os.getenv("ADMIN_API_KEY")
        if not self.api_key:
            self.logger.error("A variável de ambiente ADMIN_API_KEY não está definida.")
            raise ValueError("Chave de API não encontrada.")
        self.headers = {"X-API-Key": self.api_key}

    def check_api_health(self) -> bool:
        try:
            response = requests.get(f"{self.base_url}/api/health")
            if response.status_code == 200:
                self.logger.info("API do backend está disponível!")
                return True
        except requests.exceptions.RequestException as e:
            self.logger.error(f"Não foi possível conectar à API do backend: {e}")
        return False

    def get_cameras_from_api(self) -> List[Dict[str, Any]]:
        internal_cameras_url = f"{self.base_url}/api/v1/internal/cameras"
        self.logger.info(f"A buscar câmaras do endpoint interno: {internal_cameras_url}")
        
        try:
            response = requests.get(internal_cameras_url, headers=self.headers)
            if response.status_code == 200:
                return response.json()
            elif response.status_code == 403:
                self.logger.error("Erro de autenticação (403 Forbidden). Verifique se a ADMIN_API_KEY está correta e corresponde entre o .env do backend e o docker-compose do ai-processor.")
            else:
                self.logger.error(f"Erro ao buscar câmaras. Status: {response.status_code}, Resposta: {response.text}")
        except requests.exceptions.RequestException as e:
            self.logger.error(f"Erro de conexão ao buscar câmaras: {e}")
        return []

    def send_sighting_to_api(self, plate: str, image_filename: str, camera_id: int):
        # --- CORREÇÃO APLICADA AQUI ---
        # O URL foi alterado para apontar para o endpoint interno correto.
        sighting_url = f"{self.base_url}/api/v1/internal/sightings"
        
        # O backend não espera um ficheiro, apenas os dados em JSON.
        # Se precisar de enviar a imagem, o backend teria de ser ajustado para recebê-la.
        # Por agora, vamos enviar apenas os dados que o backend espera.
        data = {
            "license_plate": plate,
            "camera_id": camera_id,
            "image_path": os.path.basename(image_filename) # Enviamos o caminho da imagem como texto
        }
        
        try:
            # Enviamos os dados como JSON
            response = requests.post(sighting_url, json=data, headers=self.headers)
            if response.status_code == 201:
                self.logger.info(f"Avistamento da placa {plate} enviado com sucesso.")
            else:
                self.logger.error(f"Falha ao enviar avistamento. Status: {response.status_code}, Resposta: {response.text}")
        except requests.exceptions.RequestException as e:
            self.logger.error(f"Erro de conexão ao enviar avistamento: {e}")