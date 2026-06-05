FROM python:3.10-slim

# Installation des dépendances système pour l'OCR, la caméra et Flask
RUN apt-get update && apt-get install -y \
    tesseract-ocr \
    tesseract-ocr-fra \
    tesseract-ocr-ara \
    libgl1-mesa-glx \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copie des fichiers requis
COPY ml/requirements.txt /app/requirements.txt

# Installation des bibliothèques Python
RUN pip install --no-cache-dir -r requirements.txt

# Remplacer opencv-python par la version headless pour éviter les erreurs d'interface sur serveur
RUN pip uninstall -y opencv-python && pip install opencv-python-headless

# Copie de tout le reste
COPY . /app/

# Ajustement pour Hugging Face (Le port officiel HF Space est 7860)
RUN sed -i 's/port=5000/port=7860/g' /app/ml/predict_api.py

WORKDIR /app/ml

EXPOSE 7860

CMD ["python", "predict_api.py"]