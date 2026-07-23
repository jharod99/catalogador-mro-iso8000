import os
os.environ["CUDA_VISIBLE_DEVICES"] = ""  # Force CPU to prevent CUDA conflicts
os.environ["OMP_NUM_THREADS"] = "1"      # Prevent thread thrashing/hanging on CPU
os.environ["MKL_NUM_THREADS"] = "1"      # Prevent MKL thread thrashing
os.environ["TQDM_DISABLE"] = "1"         # Disable tqdm progress bars to prevent Windows redirect errors

import torch
torch.set_num_threads(1)                 # Prevent PyTorch thread deadlock

from flask import Flask, render_template, request, jsonify, session
import uuid
import logging
from core.graph import clasificar_con_agente
from database import clear_chat_history
from dotenv import load_dotenv

load_dotenv()

import sys

# Configurar logging hacia stdout
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.secret_key = os.environ.get('FLASK_SECRET_KEY', 'unspsc_secret_key_123_dev')
app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 0

@app.after_request
def add_header(response):
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, post-check=0, pre-check=0, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '-1'
    return response

import threading
import warnings
warnings.filterwarnings("ignore")

# Pre-cargar el modelo FAISS en hilo secundario
from core.rag.faiss_engine import get_chatbot

def _preload_brain():
    try:
        logger.info("[STARTUP] Pre-cargando cerebro FAISS en hilo secundario...")
        get_chatbot()
        logger.info("[STARTUP] Cerebro FAISS cargado y listo para consultas.")
    except Exception as e_precarga:
        logger.error(f"[STARTUP] Error pre-cargando cerebro FAISS: {e_precarga}")

threading.Thread(target=_preload_brain, daemon=True).start()

@app.route('/')
def home():
    """Ruta principal para cargar la interfaz web."""
    return render_template('index.html')


@app.route('/api/classify', methods=['POST'])
def classify():
    """
    Endpoint principal para clasificar cualquier producto de forma directa y limpia.
    """
    data = request.get_json()
    if not data or 'query' not in data:
        return jsonify({
            'status': 'error',
            'mensaje': 'Falta el parámetro "query" en la solicitud.'
        }), 400

    query = data['query'].strip()
    if not query:
        return jsonify({
            'status': 'error',
            'mensaje': 'La consulta no puede estar vacía.'
        }), 400

    if 'session_id' not in session:
        session['session_id'] = str(uuid.uuid4())
    session_id = session['session_id']

    # Si se solicita reset explícito
    if data.get('reset_session'):
        clear_chat_history(session_id)
        return jsonify({'status': 'ok', 'mensaje': 'Sesión reiniciada.'})

    try:
        # Enviar únicamente el mensaje actual a LangGraph para cero contaminación de tokens
        messages = [{"role": "user", "content": query}]

        logger.info(f"[CLASSIFY API] Procesando consulta: '{query}'")

        # Ejecutar el agente
        resultado = clasificar_con_agente(messages)

        return jsonify(resultado)

    except Exception as e:
        import traceback
        tb = traceback.format_exc()
        logger.error(f"Error en classify endpoint: {e}\n{tb}")
        return jsonify({
            'status': 'error',
            'mensaje': f'Error interno al procesar la consulta: {str(e)}'
        }), 500


if __name__ == '__main__':
    # Ejecutar en puerto local 5050
    app.run(debug=False, host='127.0.0.1', port=5050, threaded=False)
