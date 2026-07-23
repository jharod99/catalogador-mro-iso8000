import os
import sqlite3
import logging
from typing import List, Dict, Any

logger = logging.getLogger(__name__)

# Ruta de la base de datos centralizada
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "app_data.db")

def init_db():
    """Inicializa la base de datos y crea las tablas necesarias."""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # 1. Tabla de caché para búsquedas de DuckDuckGo
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS ddg_cache (
            query TEXT PRIMARY KEY,
            response TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # 2. Tabla de historial de chat persistente
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS chat_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT,
            role TEXT,
            content TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    conn.commit()
    conn.close()
    logger.info("Base de datos SQLite inicializada correctamente.")

# --- Métodos de caché de búsquedas ---
def get_cached_search(query: str) -> Any:
    """Recupera la respuesta almacenada en caché para una búsqueda."""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT response FROM ddg_cache WHERE query = ?", (query.strip().lower(),))
        row = cursor.fetchone()
        conn.close()
        return row[0] if row else None
    except Exception as e:
        logger.error(f"[DB] Error leyendo caché: {e}")
        return None

def set_cached_search(query: str, response: str):
    """Guarda la respuesta de una búsqueda en la caché."""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute(
            "INSERT OR REPLACE INTO ddg_cache (query, response, timestamp) VALUES (?, ?, CURRENT_TIMESTAMP)",
            (query.strip().lower(), response)
        )
        conn.commit()
        conn.close()
    except Exception as e:
        logger.error(f"[DB] Error guardando en caché: {e}")

# --- Métodos de historial de conversación ---
def get_chat_history(session_id: str, limit: int = 6) -> List[Dict[str, str]]:
    """Recupera los últimos mensajes de conversación para una sesión en orden cronológico."""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT role, content FROM (SELECT id, role, content FROM chat_history WHERE session_id = ? ORDER BY id DESC LIMIT ?) ORDER BY id ASC",
            (session_id, limit)
        )
        rows = cursor.fetchall()
        conn.close()
        return [{"role": row[0], "content": row[1]} for row in rows]
    except Exception as e:
        logger.error(f"[DB] Error leyendo historial: {e}")
        return []

def add_message_to_history(session_id: str, role: str, content: str):
    """Añade un mensaje (usuario o asistente) al historial persistente."""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO chat_history (session_id, role, content) VALUES (?, ?, ?)",
            (session_id, role, content)
        )
        conn.commit()
        conn.close()
    except Exception as e:
        logger.error(f"[DB] Error guardando mensaje: {e}")

def clear_chat_history(session_id: str):
    """Limpia el historial de chat para una sesión."""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM chat_history WHERE session_id = ?", (session_id,))
        conn.commit()
        conn.close()
    except Exception as e:
        logger.error(f"[DB] Error borrando historial: {e}")

# Inicialización automática al importar
init_db()
