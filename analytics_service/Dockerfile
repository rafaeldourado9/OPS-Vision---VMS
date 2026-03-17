FROM python:3.12-slim

WORKDIR /app

# Dependências de sistema para OpenCV + compilação de extensões C++ (insightface)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 \
    libglib2.0-0 \
    libgomp1 \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Deps pesadas em layers separadas — cada layer fica em cache independente.
# Se o download cair no meio, só redownloada a layer que falhou.

# 1. numpy + opencv (base para todos os plugins)
RUN pip install --no-cache-dir "numpy>=1.26" "opencv-python-headless>=4.10"

# 2. onnxruntime (inferência CPU — ~180 MB)
RUN pip install --no-cache-dir "onnxruntime>=1.18"

# 3. ultralytics (puxa torch — pacote mais pesado)
RUN pip install --no-cache-dir "ultralytics>=8.3"

# 4. insightface (compilação C++ — demorado)
RUN pip install --no-cache-dir "insightface>=0.7"

# 5. fast-plate-ocr (puxa polars ~47 MB — era o que quebrava)
RUN pip install --no-cache-dir "fast-plate-ocr>=0.2"

# 6. Deps leves (fastapi, uvicorn, aiohttp, redis, supervision)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copia código do serviço
COPY . .

RUN mkdir -p /recordings/snapshots

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8002"]
