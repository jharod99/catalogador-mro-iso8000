# === Dockerfile de Despliegue para Chatbot UNSPSC / Catalogador MRO ===

# Usamos una imagen de Python oficial delgada (slim) para minimizar el tamaño
FROM python:3.11-slim

# Evitar que Python escriba archivos .pyc en disco
ENV PYTHONDONTWRITEBYTECODE=1
# Evitar que Python guarde en caché las salidas de consola (útil para logs en tiempo real)
ENV PYTHONUNBUFFERED=1

# Configuración del entorno de CPU para prevenir deadlocks en PyTorch y OpenMP
ENV OMP_NUM_THREADS=1
ENV MKL_NUM_THREADS=1
ENV CUDA_VISIBLE_DEVICES=""

# Instalar dependencias del sistema necesarias para construir ciertas extensiones
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Crear directorio de la aplicación
WORKDIR /app

# Copiar el archivo de requerimientos
COPY requirements.txt .

# Optimización crítica: Instalar PyTorch versión CPU primero para evitar descargar las ruedas GPU pesadas (+4GB)
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu && \
    pip install --no-cache-dir -r requirements.txt

# Pre-descargar los modelos de embeddings en la fase de build para evitar descargas en runtime
RUN python -c "from fastembed import TextEmbedding; list(TextEmbedding('sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2').embed(['test']))" || true
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2')" || true

# Copiar el resto del código del proyecto
COPY . .

# Exponer el puerto por defecto de Flask
EXPOSE 5000

# Comando para ejecutar la aplicación usando Gunicorn (servidor WSGI de producción)
# Si prefieres Flask nativo para desarrollo, puedes usar: python app.py
RUN pip install --no-cache-dir gunicorn
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "1", "--threads", "2", "--timeout", "120", "app:app"]
