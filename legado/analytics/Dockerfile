FROM python:3.11-slim

WORKDIR /app

# Dependências do sistema para OpenCV
RUN apt-get update && apt-get install -y \
    libgl1 \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    && rm -rf /var/lib/apt/lists/*

# Atualiza pip
RUN pip install --no-cache-dir --upgrade pip

# Instala numpy primeiro (versão compatível)
RUN pip install --no-cache-dir numpy==1.26.4

# Instala dependências básicas
RUN pip install --no-cache-dir \
    fastapi==0.104.1 \
    uvicorn[standard]==0.24.0 \
    redis==5.0.1 \
    aiohttp==3.9.1 \
    pydantic==2.5.0 \
    pydantic-settings==2.1.0

# Instala OpenCV
RUN pip install --no-cache-dir opencv-python-headless==4.8.1.78

# Instala PyTorch 2.5 (última versão sem weights_only)
RUN pip install --no-cache-dir --timeout=300 \
    torch==2.5.1 torchvision==0.20.1 --index-url https://download.pytorch.org/whl/cpu

# Instala Ultralytics (versão mais recente para suportar YOLOv11)
RUN pip install --no-cache-dir ultralytics>=8.3.0

# Instala fast-plate-ocr
RUN pip install --no-cache-dir fast-plate-ocr[onnx]==1.0.2

# Copia código da aplicação
COPY . .

ENV PYTHONUNBUFFERED=1

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
