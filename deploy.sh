#!/bin/bash
# === Script de Despliegue Automatizado para Chatbot UNSPSC / Catalogador MRO ===

echo "============================================================"
echo "    Iniciando Despliegue del Chatbot UNSPSC con Docker      "
echo "============================================================"

# Verificar si Docker está instalado
if ! [ -x "$(command -v docker)" ]; then
  echo 'Error: docker no está instalado. Instálalo para continuar.' >&2
  exit 1
fi

# Verificar si Docker Compose está instalado
if ! [ -x "$(command -v docker-compose)" ]; then
  echo 'Error: docker-compose no está instalado. Instálalo para continuar.' >&2
  exit 1
fi

# 1. Asegurar la existencia del archivo de base de datos vacío o carpeta de datos
echo "[PASO 1/3] Configurando directorios locales..."
mkdir -p data

# Inicializar golden_record.json si no existe
if [ ! -f golden_record.json ]; then
  echo "{}" > golden_record.json
fi

# 2. Construir la imagen de Docker
echo "[PASO 2/3] Construyendo imagen optimizada para CPU (esto puede tardar unos minutos)..."
docker-compose build

# 3. Levantar los servicios en segundo plano (detached mode)
echo "[PASO 3/3] Levantando contenedor de producción..."
docker-compose up -d

echo "============================================================"
echo "    ¡Despliegue Completo!                                  "
echo "    Servidor disponible en: http://localhost:5000         "
echo "============================================================"
