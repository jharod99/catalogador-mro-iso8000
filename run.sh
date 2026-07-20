#!/bin/bash
set -e

echo "==================================================="
echo "  Iniciando Chat Bot UNSPSC - Configuracion y Ejecucion"
echo "==================================================="

# Cambiar al directorio del script
cd "$(dirname "$0")"

# Verificar si Python esta instalado
if ! command -v python3 &> /dev/null; then
    echo "[ERROR] Python 3 no esta instalado o no se encuentra en el PATH."
    exit 1
fi

# Crear venv si no existe
if [ ! -d "venv" ]; then
    echo "[INFO] Creando entorno virtual (venv)..."
    python3 -m venv venv
fi

# Activar entorno virtual e instalar dependencias
echo "[INFO] Activando entorno virtual..."
source venv/bin/activate

echo "[INFO] Verificando e instalando dependencias (requirements.txt)..."
python3 -m pip install --upgrade pip
python3 -m pip install -r requirements.txt

# Verificar si la base de datos y FAISS estan listos
if [ ! -f "data/index.faiss" ]; then
    echo "[WARNING] No se encontro el indice de FAISS en data/index.faiss."
    echo "[INFO] Ejecutando ingesta de datos inicial (esto puede tomar unos minutos)..."
    python3 ingesta_datos.py
fi

# Ejecutar servidor Flask
echo "[INFO] Iniciando el servidor principal del Chat Bot UNSPSC..."
echo "La aplicacion estara disponible en http://127.0.0.1:5000"
python3 app.py
