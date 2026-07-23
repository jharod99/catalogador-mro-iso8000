from .state import AgentState, ProductItem
from langgraph.graph import StateGraph, END
from typing import TypedDict, List, Dict, Any, Optional

from .nodes.cache import cache_node, guardar_en_cache
from .nodes.extraction import extractor_node
from .nodes.retrieval import market_verifier_node, retriever_node
from .nodes.decision import decision_maker_node
from .rag.faiss_engine import get_chatbot
import logging

logger = logging.getLogger(__name__)

def route_cache(state: AgentState):
    if state.get("estado_global") == "Alta":
        return END
    else:
        return "extractor"

def route_decision(state: AgentState):
    return END

# --- CONFIGURACIÓN Y COMPILACIÓN DEL GRAFO DE AGENTE ---
workflow = StateGraph(AgentState)

workflow.add_node("cache", cache_node)
workflow.add_node("extractor", extractor_node)
workflow.add_node("market_verifier", market_verifier_node)
workflow.add_node("retriever", retriever_node)
workflow.add_node("decision_maker", decision_maker_node)

workflow.set_entry_point("cache")

workflow.add_conditional_edges(
    "cache",
    route_cache,
    {
        END: END,
        "extractor": "extractor"
    }
)

workflow.add_edge("extractor", "market_verifier")
workflow.add_edge("market_verifier", "retriever")
workflow.add_edge("retriever", "decision_maker")

workflow.add_edge("decision_maker", END)

agente = workflow.compile()

def clasificar_con_agente(messages: List[Dict[str, str]]) -> Dict[str, Any]:
    input_state = {"messages": messages, "items": []}
    
    final_state = {}
    try:
        for event in agente.stream(input_state):
            for value in event.values():
                if isinstance(value, dict):
                    final_state.update(value)
    except Exception as e:
        import traceback
        tb_str = traceback.format_exc()
        logger.error(f"Error crítico en LangGraph: {e}\n{tb_str}")
        # --- FALLBACK DE BÚSQUEDA LOCAL OFFLINE ---
        try:
            user_query = None
            for m in reversed(messages):
                if isinstance(m, str) and m.strip():
                    user_query = m.strip()
                    break
                elif isinstance(m, dict) and m.get("role") == "user":
                    user_query = m.get("content", "").strip()
                    break
            if user_query:
                logger.info(f"[FALLBACK] Iniciando clasificación local offline para: '{user_query}'...")
                chatbot = get_chatbot()
                rag_res = chatbot.clasificar(user_query)
                estado = rag_res.get("estado", "Falta de Datos")
                if estado == "Alta":
                    nombre_prod = rag_res.get("nombre_producto", "")
                    sustantivo = nombre_prod.split()[0].replace(",", "").upper() if nombre_prod else "PRODUCTO"
                    return {
                        "estado": "Alta",
                        "items": [{
                            "codigo_exacto": rag_res.get("codigo_exacto"),
                            "nombre_producto": nombre_prod,
                            "ruta_jerarquica": rag_res.get("ruta_jerarquica", ""),
                            "score_percentage": rag_res.get("score_percentage", 0.0),
                            "one_line_desc": f"{nombre_prod.upper()} (MODO LOCAL OFFLINE)",
                            "sustantivo_principal": sustantivo,
                            "atributos_recolectados": {},
                            "atributos_faltantes": [],
                            "criticidad": "Baja",
                            "requiere_revision_humana": False,
                            "categoria_dominio": "GENERAL"
                        }]
                    }
                else:
                    msg_extra = "\n\n(Búsqueda local RAG activada por interrupción del servicio AI)"
                    return {
                        "estado": "Ambig\u00fcedad",
                        "mensaje": rag_res.get("mensaje", "No pudimos procesar la consulta de forma local.") + msg_extra,
                        "items": []
                    }
        except Exception as e_fallback:
            import traceback
            tb_str = traceback.format_exc()
            logger.error(f"[FALLBACK] Error crítico en el fallback offline: {e_fallback}\n{tb_str}")
            
        return {"estado": "Error", "mensaje": f"Error del agente AI: {str(e)}"}
        
    estado = final_state.get("estado_global", "Baja")
    items = final_state.get("items", [])
    
    # --- RESILIENCIA OFFLINE / FALLBACK PARA BAJA CONFIANZA O FALLO GENERAL ---
    if estado == "Baja" or not items:
        try:
            user_query = None
            for m in reversed(messages):
                if m.get("role") == "user":
                    user_query = m.get("content")
                    break
            if user_query:
                logger.warning(f"[FALLBACK] Detectado estado '{estado}'. Intentando clasificación local offline para: '{user_query}'...")
                chatbot = get_chatbot()
                rag_res = chatbot.clasificar(user_query)
                if rag_res.get("estado") == "Alta":
                    nombre_prod = rag_res.get("nombre_producto", "")
                    sustantivo = nombre_prod.split()[0].replace(",", "").upper() if nombre_prod else "PRODUCTO"
                    logger.info(f"[FALLBACK] Clasificación local exitosa con alta confianza ({rag_res.get('score_percentage', 0.0):.2f}%). Retornando RAG local.")
                    return {
                        "estado": "Alta",
                        "items": [{
                            "codigo_exacto": rag_res.get("codigo_exacto"),
                            "nombre_producto": nombre_prod,
                            "ruta_jerarquica": rag_res.get("ruta_jerarquica", ""),
                            "score_percentage": rag_res.get("score_percentage", 0.0),
                            "one_line_desc": f"{nombre_prod.upper()} (MODO LOCAL OFFLINE)",
                            "sustantivo_principal": sustantivo,
                            "atributos_recolectados": {},
                            "atributos_faltantes": [],
                            "criticidad": "Baja",
                            "requiere_revision_humana": False,
                            "categoria_dominio": "GENERAL"
                        }]
                    }
        except Exception as e_fallback:
            logger.error(f"[FALLBACK] Error en fallback de baja confianza: {e_fallback}")
            
    if estado == "Alta":
        resultados = []
        for i in items:
            best = i.get("best_match") or {}
            meta = best.get("metadata") or {}
            cod = i.get("codigo_exacto") or best.get("codigo_producto", "")
            nom = i.get("nombre_producto") or best.get("nombre_producto", "")
            ruta = i.get("ruta_jerarquica") or ""
            if not ruta and meta:
                ruta = f"{meta.get('nombre_segmento')} -> {meta.get('nombre_familia')} -> {meta.get('nombre_clase')} -> {meta.get('nombre_producto')}"

            resultados.append({
                "codigo_exacto": str(cod),
                "nombre_producto": nom,
                "ruta_jerarquica": ruta,
                "score_percentage": best.get("score_percentage", 100.0),
                "one_line_desc": i.get("one_line_desc", f"UNSPSC {cod}: {nom}"),
                "sustantivo_principal": i.get("sustantivo_principal", ""),
                "atributos_recolectados": i.get("atributos_recolectados", {}),
                "atributos_faltantes": [],
                "criticidad": "Baja",
                "requiere_revision_humana": False,
                "categoria_dominio": "GENERAL"
            })
        
        first_item = resultados[0] if resultados else {}
        return {
            "status": "success",
            "message": "Clasificación exitosa.",
            "data": {
                "codigo_unspsc": str(first_item.get("codigo_exacto", "")),
                "jerarquia": first_item.get("ruta_jerarquica", ""),
                "descripcion_oficial": first_item.get("nombre_producto", "")
            },
            "ui_action": "display_result_and_confirm",
            "estado": "Alta",
            "items": resultados
        }
    else:
        # Modo pregunta aclaratoria con opciones seleccionables (Formato B - Requires Context)
        items_aclaracion = []
        opciones_globales = []
        pregunta_global = ""
        for i in items:
            pregunta_item = i.get("pregunta_aclaratoria", "")
            if pregunta_item and not pregunta_global:
                pregunta_global = pregunta_item
            opciones_item = i.get("opciones", [])
            if opciones_item and not opciones_globales:
                opciones_globales = opciones_item

            items_aclaracion.append({
                "original_query": i["original_query"],
                "sustantivo_principal": i.get("sustantivo_principal", ""),
                "atributos_recolectados": i.get("atributos_recolectados", {}),
                "atributos_faltantes": i.get("atributos_faltantes", []),
                "criticidad": "Baja",
                "pregunta_aclaratoria": pregunta_item,
                "opciones": opciones_item,
                "requiere_revision_humana": False,
                "categoria_dominio": "GENERAL"
            })

        options_list = []
        for op in opciones_globales:
            if isinstance(op, dict):
                options_list.append(f"{op.get('titulo', '')} ({op.get('descripcion', '')})")
            else:
                options_list.append(str(op))

        prod_name = items[0].get("sustantivo_principal", "producto") if items else "producto"
        msg_text = pregunta_global or f"El término [{prod_name}] es genérico. Para asegurar una clasificación exacta, selecciona la industria o aplicación principal:"

        return {
            "status": "requires_context",
            "message": msg_text,
            "options": options_list,
            "ui_action": "render_buttons",
            "estado": "Ambigüedad",
            "mensaje": msg_text,
            "opciones": opciones_globales,
            "items": items_aclaracion
        }
