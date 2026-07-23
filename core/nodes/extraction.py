from ..state import AgentState, ProductItem
import json
import re
import unicodedata
import logging
from typing import Dict, Any, List
from ..models import llamar_llm_con_fallback
from ..prompts.templates import get_extractor_prompt

logger = logging.getLogger(__name__)

MATRIZ_ATRIBUTOS_MRO = {}

def limpiar_consulta(texto):
    """Limpia el texto de una consulta para búsqueda léxica."""
    texto = texto.lower()
    texto = re.sub(r'[^a-z0-9áéíóúüñ\s]', ' ', texto)
    texto = re.sub(r'\s+', ' ', texto).strip()
    return texto

def extractor_node(state: AgentState) -> Dict[str, Any]:
    """Nodo 1: Extrae el producto o consulta de entrada."""
    messages = state.get("messages", [])
    if not messages:
        return {"items": []}
    
    ultimo_mensaje = messages[-1]["content"] if messages else ""

    # Detectar si la entrada ya es una aclaración unificada (contiene 'destinado a:' o 'para:')
    es_aclaracion = "destinado a:" in ultimo_mensaje.lower() or "para:" in ultimo_mensaje.lower()

    if es_aclaracion:
        cleaned_full = limpiar_consulta(ultimo_mensaje)
        
        # Separar el producto base de la aclaración de industria
        partes = re.split(r'destinado a:|para:', ultimo_mensaje, flags=re.IGNORECASE)
        prod_base = partes[0].strip() if len(partes) > 0 else ultimo_mensaje
        industria_aclarada = partes[1].strip() if len(partes) > 1 else ""

        prod_base_clean = limpiar_consulta(prod_base)
        ind_clean = limpiar_consulta(industria_aclarada)

        # Extraer sustantivo principal implícito del producto base
        words = prod_base_clean.split()
        sust_raw = words[0].upper() if words else "PRODUCTO"
        for w in words:
            if len(w) > 3 and w not in ["sistema", "equipo", "unidad", "parte", "para", "destinado"]:
                sust_raw = w.upper()
                break

        # Construir consultas expandidas totalmente dinámicas sin harcodeo
        combined_query = f"{prod_base_clean} {ind_clean}".strip()
        expanded = list(set([combined_query, prod_base_clean, cleaned_full]))

        logger.info(f"[EXTRACTOR DYNAMIC BYPASS] Producto Base: '{prod_base}', Industria: '{industria_aclarada}', Sustantivo: '{sust_raw}'")

        return {
            "items": [{
                "original_query": ultimo_mensaje,
                "expanded_queries": expanded,
                "market_context": "",
                "candidates": [],
                "best_match": None,
                "estado_decision": "Baja",
                "pregunta_aclaratoria": "",
                "one_line_desc": "",
                "sustantivo_principal": sust_raw,
                "requiere_busqueda_web": False,
                "requiere_revision_humana": False,
                "categoria_dominio": "GENERAL",
                "contexto_resuelto": True,
                "atributos_recolectados": {},
                "atributos_faltantes": [],
                "criticidad": "Baja"
            }]
        }
    
    # Formatear historial
    chat_history = ""
    for m in messages:
        chat_history += f"{m['role'].capitalize()}: {m['content']}\n"

    llaves_matriz = ", ".join([f'"{k}"' for k in MATRIZ_ATRIBUTOS_MRO.keys()])
    prompt = get_extractor_prompt(chat_history, llaves_matriz)
    
    items_extraidos = []
    try:
        content = llamar_llm_con_fallback(prompt)
        
        match = re.search(r'\[.*\]', content, re.DOTALL)
        if match:
            json_clean = re.sub(r',\s*\]', ']', match.group(0))
            json_clean = re.sub(r',\s*\}', '}', json_clean)
            parsed_items = json.loads(json_clean)
        else:
            if "```" in content:
                content = content.split("```json")[1].split("```")[0].strip() if "```json" in content else content.split("```")[1].strip()
            content = re.sub(r',\s*\]', ']', content)
            content = re.sub(r',\s*\}', '}', content)
            parsed_items = json.loads(content)
            
        for pi in parsed_items:
            full_query = pi.get("original_query", "").strip()
            if not full_query or len(full_query) < len(ultimo_mensaje) * 0.7:
                full_query = ultimo_mensaje.strip()

            cleaned = limpiar_consulta(full_query)
            exp = list(set([cleaned] + pi.get("expanded_queries", [])))
            
            sust_raw = pi.get("sustantivo_principal", "").strip().upper()
            cat_raw = pi.get("categoria_dominio", "GENERAL").upper()

            items_extraidos.append({
                "original_query": full_query,
                "expanded_queries": exp,
                "market_context": "",
                "candidates": [],
                "best_match": None,
                "estado_decision": "Baja",
                "pregunta_aclaratoria": "",
                "one_line_desc": "",
                "sustantivo_principal": sust_raw,
                "requiere_busqueda_web": bool(pi.get("requiere_busqueda_web", False)),
                "requiere_revision_humana": False,
                "categoria_dominio": cat_raw if cat_raw != "FUERA_DE_ALCANCE" else "GENERAL",
                "contexto_resuelto": False,
                "atributos_recolectados": {},
                "atributos_faltantes": [],
                "criticidad": "Baja"
            })
    except Exception as e:
        logger.error(f"Error en extractor: {e}")
        cleaned = limpiar_consulta(ultimo_mensaje)
        items_extraidos.append({
            "original_query": ultimo_mensaje,
            "expanded_queries": [cleaned],
            "market_context": "",
            "candidates": [],
            "best_match": None,
            "estado_decision": "Baja",
            "pregunta_aclaratoria": "",
            "one_line_desc": "",
            "sustantivo_principal": "",
            "requiere_busqueda_web": False,
            "requiere_revision_humana": False,
            "categoria_dominio": "GENERAL",
            "contexto_resuelto": False,
            "atributos_recolectados": {},
            "atributos_faltantes": [],
            "criticidad": "Baja"
        })

    return {"items": items_extraidos}