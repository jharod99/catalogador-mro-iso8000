from ..state import AgentState, ProductItem
import json
import re
import os
import logging
from typing import Dict, Any, List
from ..models import llamar_llm_con_fallback
from ..prompts.templates import get_decision_prompt

logger = logging.getLogger(__name__)

def decision_maker_node(state: AgentState) -> Dict[str, Any]:
    """Nodo 4: Selecciona el código UNSPSC adecuado o genera preguntas con opciones interactivas."""
    items = state.get("items", [])
    estado_global = "Alta"
    
    for item in items:
        candidates = item.get("candidates", [])
        cand_str = ""
        for idx, c in enumerate(candidates, 1):
            cand_str += f"{idx}. [{c['codigo_producto']}] {c['nombre_producto']} | {c['ruta_jerarquica']}\n"
            
        oq_lower = item.get("original_query", "").lower()
        
        # 1. LEY DE LA MÁQUINA DESTINO: Si la descripción menciona la máquina/equipo destino (ej: "para faja transportadora", "de camión")
        tiene_maquina_destino = (
            "destinado a" in oq_lower or
            "para:" in oq_lower or
            ("para " in oq_lower and len(oq_lower.split("para ")[-1].strip()) > 2) or
            any(m in oq_lower for m in ["faja transportadora", "aire acondicionado", "de camion", "de camión", "repuesto de"])
        )
        
        # 2. LEY DE SERVICIOS E INTANGIBLES: Software, licencias, cloud hosting y suscripciones
        es_servicio_intangible = any(w in oq_lower for w in [
            "cloud", "hosting", "nube", "software", "licencia", "suscripcion", "suscripción", "hosting", "saas"
        ])

        es_aclarado = (
            item.get("contexto_resuelto", False) or 
            tiene_maquina_destino or
            es_servicio_intangible
        )

        # --- CANDADO INFRANQUEABLE (DETERMINISTA DE 1 SOLO PASO) ---
        if es_aclarado:
            if candidates:
                c = candidates[0]
                item["estado_decision"] = "Alta"
                item["codigo_exacto"] = c["codigo_producto"]
                item["nombre_producto"] = c["nombre_producto"]
                item["ruta_jerarquica"] = c["ruta_jerarquica"]
                item["pregunta_aclaratoria"] = ""
                item["opciones"] = []
                item["one_line_desc"] = f"{c['nombre_producto']} (CÓDIGO UNSPSC: {c['codigo_producto']})"
                logger.info(f"[DECISION] Aclaración resuelta vía Bypass. Asignado UNSPSC: [{c['codigo_producto']}] {c['nombre_producto']}")
            else:
                item["estado_decision"] = "Baja"
                item["pregunta_aclaratoria"] = "No se encontraron coincidencias para este producto."
                estado_global = "Baja"
            continue

        # Si no es una aclaración explícita, consultar al LLM para evaluar ambigüedad
        prompt = get_decision_prompt(item, cand_str)
        try:
            content = llamar_llm_con_fallback(prompt, providers_order=["openrouter", "deepseek", "groq", "siliconflow", "mistral", "gemini"])
            
            match = re.search(r'\{.*\}', content, re.DOTALL)
            if match:
                json_clean = re.sub(r',\s*\]', ']', match.group(0))
                json_clean = re.sub(r',\s*\}', '}', json_clean)
                res_json = json.loads(json_clean)
            else:
                if "```" in content:
                    content = content.split("```json")[1].split("```")[0].strip() if "```json" in content else content.split("```")[1].strip()
                content = re.sub(r',\s*\]', ']', content)
                content = re.sub(r',\s*\}', '}', content)
                res_json = json.loads(content)

            idx = res_json.get("indice_seleccionado")
            confianza = res_json.get("confianza", "Ambigüedad")

            if res_json.get("opciones") or confianza == "Ambigüedad" or idx is None:
                idx = None
                confianza = "Ambigüedad"

            if isinstance(idx, int) and 1 <= idx <= len(candidates) and confianza == "Alta":
                c = candidates[idx - 1]
                item["estado_decision"] = "Alta"
                item["codigo_exacto"] = c["codigo_producto"]
                item["nombre_producto"] = c["nombre_producto"]
                item["ruta_jerarquica"] = c["ruta_jerarquica"]
                item["pregunta_aclaratoria"] = ""
                item["opciones"] = []
                item["one_line_desc"] = f"{c['nombre_producto']} (CÓDIGO UNSPSC: {c['codigo_producto']})"
            else:
                item["estado_decision"] = "Ambigüedad"
                item["pregunta_aclaratoria"] = res_json.get("pregunta") or "¿En qué equipo, industria o sistema instalará este producto?"
                raw_opciones = res_json.get("opciones", [])
                clean_opciones = [
                    op for op in raw_opciones
                    if isinstance(op, dict) and not any(w in (op.get("titulo", "") + " " + op.get("descripcion", "")).lower() for w in ["otro", "especificar", "ningun", "ningún"])
                ]
                item["opciones"] = clean_opciones
                estado_global = "Ambigüedad"
                
        except Exception as e:
            logger.error(f"[DECISION] Error procesando decisión LLM: {e}")
            if candidates:
                c = candidates[0]
                item["estado_decision"] = "Alta"
                item["codigo_exacto"] = c["codigo_producto"]
                item["nombre_producto"] = c["nombre_producto"]
                item["ruta_jerarquica"] = c["ruta_jerarquica"]
                item["pregunta_aclaratoria"] = ""
                item["opciones"] = []
            else:
                item["estado_decision"] = "Baja"
                item["pregunta_aclaratoria"] = "No se encontraron coincidencias para este producto."
                estado_global = "Baja"

    return {"items": items, "estado_global": estado_global}
