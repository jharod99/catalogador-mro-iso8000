from ..state import AgentState, ProductItem
from typing import Dict, Any, List
import json
import os

GOLDEN_RECORD_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "golden_record.json"))

def cache_node(state: AgentState) -> Dict[str, Any]:
    """Nodo Inicial: Busca en la base de datos de cache local (golden_record.json) matches exactos."""
    messages = state.get("messages", [])
    if not messages:
        return {"items": [], "estado_global": "Baja"}
        
    # Obtener última consulta de usuario
    ultimo_mensaje = None
    for m in reversed(messages):
        if m.get("role") == "user":
            ultimo_mensaje = m.get("content", "").strip()
            break
            
    if not ultimo_mensaje:
        return {"items": [], "estado_global": "Baja"}
        
    # Leer golden_record.json
    cache = {}
    if os.path.exists(GOLDEN_RECORD_PATH):
        try:
            with open(GOLDEN_RECORD_PATH, 'r', encoding='utf-8') as f:
                cache = json.load(f)
        except Exception as e:
            print(f"Error cargando golden_record.json: {e}")
            
    # Comparación exacta (después de normalización de espacios y minúsculas)
    normalized_query = ultimo_mensaje.strip().lower()
    
    # Buscar match exacto en la caché
    match_key = None
    for k in cache.keys():
        if k.strip().lower() == normalized_query:
            match_key = k
            break
            
    if match_key:
        cached_record = cache[match_key]
        print(f"[GOLDEN RECORD HIT] Encontrado match exacto en cache para: '{ultimo_mensaje}'")
        
        item = {
            "original_query": ultimo_mensaje,
            "expanded_queries": [],
            "market_context": "Recuperado de Golden Record Cache",
            "candidates": [],
            "best_match": {
                "codigo_producto": cached_record["codigo_unspsc"],
                "metadata": {
                    "nombre_segmento": cached_record.get("nombre_segmento", ""),
                    "nombre_familia": cached_record.get("nombre_familia", ""),
                    "nombre_clase": cached_record.get("nombre_clase", ""),
                    "nombre_producto": cached_record.get("nombre_producto", "")
                },
                "score_percentage": 100.0
            },
            "estado_decision": "Alta",
            "pregunta_aclaratoria": "",
            "one_line_desc": cached_record["descripcion_iso"],
            "sustantivo_principal": cached_record.get("sustantivo_principal", ""),
            "atributos_recolectados": cached_record.get("atributos_recolectados", {}),
            "atributos_faltantes": [],
            "criticidad": "Baja",
            "requiere_busqueda_web": False,
            "requiere_revision_humana": False,
            "categoria_dominio": cached_record.get("categoria_dominio", "GENERAL")
        }
        
        return {"items": [item], "estado_global": "Alta"}
        
    return {"estado_global": "Baja"}

def guardar_en_cache(query: str, item: Dict[str, Any]):
    """Guarda una especificación exitosa en golden_record.json."""
    cache = {}
    if os.path.exists(GOLDEN_RECORD_PATH):
        try:
            with open(GOLDEN_RECORD_PATH, 'r', encoding='utf-8') as f:
                cache = json.load(f)
        except Exception as e:
            print(f"Error leyendo golden_record.json: {e}")
            cache = {}
            
    # Solo si el item tiene best_match y una descripción no vacía
    best_m = item.get("best_match")
    if not best_m or not item.get("one_line_desc"):
        return
        
    meta = best_m.get("metadata", {})
    cache[query] = {
        "codigo_unspsc": best_m.get("codigo_producto"),
        "nombre_producto": meta.get("nombre_producto", ""),
        "nombre_clase": meta.get("nombre_clase", ""),
        "nombre_familia": meta.get("nombre_familia", ""),
        "nombre_segmento": meta.get("nombre_segmento", ""),
        "descripcion_iso": item.get("one_line_desc", ""),
        "sustantivo_principal": item.get("sustantivo_principal", ""),
        "atributos_recolectados": item.get("atributos_recolectados", {}),
        "categoria_dominio": item.get("categoria_dominio", "GENERAL")
    }
    
    try:
        with open(GOLDEN_RECORD_PATH, 'w', encoding='utf-8') as f:
            json.dump(cache, f, ensure_ascii=False, indent=4)
        print(f"[CACHE] Guardado en golden_record.json: '{query}'")
    except Exception as e:
        print(f"Error escribiendo golden_record.json: {e}")

