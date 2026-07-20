@echo off
SETLOCAL EnableDelayedExpansion

echo ===================================================
echo   Iniciando Chat Bot UNSPSC - Configuracion y Ejecucion
echo ===================================================

:: Cambiar al directorio del script
cd /d "%~dp0"

:: Evitar bloqueos de hilos en PyTorch/OpenMP (critico en Windows)
SET OMP_NUM_THREADS=1
SET MKL_NUM_THREADS=1
SET CUDA_VISIBLE_DEVICES=

:: Verificar si Python esta instalado
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python no esta instalado o no se encuentra en el PATH.
    echo Por favor, instala Python y agregalo al PATH antes de continuar.
    pause
    exit /b 1
)

:: Crear venv si no existe
if not exist venv (
    echo [INFO] Creando entorno virtual (venv)...
    python -m venv venv
    if !errorlevel! neq 0 (
        echo [ERROR] No se pudo crear el entorno virtual.
        pause
        exit /b 1
    )
)

:: Activar entorno virtual e instalar dependencias
echo [INFO] Activando entorno virtual...
call venv\Scripts\activate

echo [INFO] Verificando e instalando dependencias (requirements.txt)...
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
if !errorlevel! neq 0 (
    echo [ERROR] Fallo la instalacion de las dependencias.
    pause
    exit /b 1
)

:: Verificar si la base de datos y FAISS estan listos
if not exist data\index.faiss (
    echo [WARNING] No se encontro el indice de FAISS en data\index.faiss.
    echo [INFO] Ejecutando ingesta de datos inicial (esto puede tomar unos minutos)...
    python ingesta_datos.py
    if !errorlevel! neq 0 (
        echo [ERROR] Fallo la ingesta de datos inicial.
        pause
        exit /b 1
    )
)

:: Ejecutar servidor Flask
echo [INFO] Iniciando el servidor principal del Chat Bot UNSPSC...
echo La aplicacion estara disponible en http://127.0.0.1:5000
python app.py

pause
