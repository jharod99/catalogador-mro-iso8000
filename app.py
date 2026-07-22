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
from scripts_legacy.generador_descripciones import mejorar_descripcion
from database import get_chat_history, add_message_to_history, clear_chat_history
from dotenv import load_dotenv

load_dotenv()

import sys

# Configurar logging hacia stdout para contenedores de producción (Render)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.secret_key = os.environ.get('FLASK_SECRET_KEY', 'unspsc_secret_key_123_dev')

# Pre-cargar el modelo de lenguaje y cerebro FAISS en el inicio del servidor
from core.rag.faiss_engine import get_chatbot
try:
    logger.info("Pre-cargando modelo y cerebro FAISS en el inicio del servidor...")
    get_chatbot()
    logger.info("Cerebro FAISS pre-cargado exitosamente.")
except Exception as e_precarga:
    logger.error(f"Error pre-cargando cerebro FAISS: {e_precarga}")

@app.route('/')
def home():
    """Ruta principal para cargar la interfaz web."""
    return render_template('index.html')


@app.route('/api/classify', methods=['POST'])
def classify():
    """
    Endpoint de la API para recibir consultas del usuario y clasificarlas
    usando LangGraph + RAG multi-ítem con cascada de LLMs.
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

    # Cargar o inicializar session_id en cookies
    if 'session_id' not in session:
        session['session_id'] = str(uuid.uuid4())
    
    session_id = session['session_id']

    # Limpiar sesión si se solicita explícitamente
    if data.get('reset_session'):
        clear_chat_history(session_id)
        return jsonify({'status': 'ok', 'mensaje': 'Sesión reiniciada.'})

    try:
        # 1. Guardar mensaje del usuario en la base de datos
        add_message_to_history(session_id, 'user', query)
        
        # 2. Obtener historial completo desde SQLite
        messages = get_chat_history(session_id)

        logger.info(f"[SESSION] Turno actual, mensajes en historial persistente: {len(messages)}")

        # Ejecutar el agente multi-modelo con cascada de fallbacks
        resultado = clasificar_con_agente(messages)

        estado = resultado.get('estado', '')

        # 3. Guardar respuesta del bot en el historial
        if estado in ('Ambig\u00fcedad', 'Baja'):
            bot_msg = resultado.get('mensaje', 'Necesito más detalles.')
            add_message_to_history(session_id, 'assistant', bot_msg)
            logger.info("[SESSION] Agregado mensaje del bot al historial (Esperando aclaración).")
        elif estado == 'Alta':
            items_names = [(i.get('best_match') or {}).get('nombre_producto', i.get('one_line_desc', 'Producto')) for i in resultado.get('items', [])]
            bot_msg = "Clasificación exitosa: " + ", ".join(items_names)
            add_message_to_history(session_id, 'assistant', bot_msg)
        else:
            bot_msg = resultado.get('mensaje', 'Error procesando la solicitud.')
            add_message_to_history(session_id, 'assistant', bot_msg)

        return jsonify(resultado)

    except Exception as e:
        import traceback
        tb = traceback.format_exc()
        logger.error(f"Error en classify endpoint: {e}\n{tb}")
        return jsonify({
            'status': 'error',
            'mensaje': f'Error interno al procesar la consulta: {str(e)}'
        }), 500


@app.route('/api/improve_description', methods=['POST'])
def improve_description():
    """
    Endpoint para generar una descripción técnica comercial detallada
    a partir del texto crudo y la categoría UNSPSC asignada.
    """
    data = request.get_json()
    if not data or 'query' not in data or 'clase_unspsc' not in data:
        return jsonify({'status': 'error', 'mensaje': 'Datos incompletos.'}), 400

    try:
        descripcion = mejorar_descripcion(data['query'], data['clase_unspsc'])
        return jsonify({'status': 'success', 'descripcion': descripcion})
    except Exception as e:
        return jsonify({'status': 'error', 'mensaje': str(e)}), 500


if __name__ == '__main__':
    # Ejecutar en puerto local 5000
    app.run(debug=False, host='127.0.0.1', port=5000, threaded=False)
