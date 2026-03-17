FROM python:3.10-slim

# 1. Instala as dependências do sistema para OpenCV e vídeo
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    ffmpeg \
    libsm6 \
    libxext6 \
    libgl1 \
    libglib2.0-0 && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# 2. Define o diretório de trabalho
WORKDIR /app

# 3. Copia os ficheiros de requisitos e a biblioteca local primeiro
COPY requirements.txt .
COPY fast-plate-ocr-master ./fast-plate-ocr-master

# 4. Instala as dependências Python
RUN pip install --no-cache-dir -r requirements.txt

# --- CORREÇÃO AQUI ---
# 5. Copia o resto do código da aplicação e o modelo de forma seletiva
COPY api_client.py .
COPY detection.py .
COPY main.py .
COPY yolov8n.pt . 

# 6. Cria a pasta para guardar as imagens capturadas
RUN mkdir -p /app/captures

# 7. Comando para executar a aplicação
CMD ["python", "main.py"]