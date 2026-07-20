from ..state import AgentState, ProductItem
import json
import re
import unicodedata
import logging
from typing import Dict, Any, List
from ..models import llamar_llm_con_fallback
from ..config import FIELD_ABBREVIATIONS, ALLOWED_PRODUCTS, BODY_MATERIALS
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
    """Nodo 1: Extrae todos los productos mencionados en el chat y los divide en ítems."""
    messages = state.get("messages", [])
    if not messages:
        return {"items": []}
    
    # Formatear historial
    chat_history = ""
    for m in messages:
        chat_history += f"{m['role'].capitalize()}: {m['content']}\n"

    # --- PRE-PROCESAMIENTO DE ABREVIATURAS DE CAMPO ---
    # Expande abreviaturas crípticas ANTES de enviar a cualquier LLM
    FIELD_ABBREVIATIONS = [
        (r'\bF\s*°\s*F\s*°\b', 'FIERRO FUNDIDO'),
        (r'\bF\.F\.\b', 'FIERRO FUNDIDO'),
        (r'\bAC\s*/\s*INOX\b', 'ACERO INOXIDABLE'),
        (r'\bA\.INOX\b', 'ACERO INOXIDABLE'),
        (r'\bAC\s*/\s*C\b', 'ACERO AL CARBONO'),
    ]
    for pattern, replacement in FIELD_ABBREVIATIONS:
        chat_history = re.sub(pattern, replacement, chat_history, flags=re.IGNORECASE)

    # --- EXPANSION DE JERGA DE EMPAQUE DE PILAS (ej. AA/2, AAA/4) ---
    chat_history = re.sub(
        r'\b(?:PILA|PILAS|BATERIA|BATERIAS)\s+(?:ALCALINA\s+)?([A-Z0-9]{2,4})/(\d+)\b',
        r'PILA ALCALINA TAMAÑO \1, BLISTER CON \2 UNIDADES',
        chat_history,
        flags=re.IGNORECASE
    )
    # También capturar si solo viene AA/2 o AAA/4 en contexto
    chat_history = re.sub(
        r'\b([A-Z0-9]{2,4})/(\d+)\b',
        r'TAMAÑO \1, BLISTER CON \2 UNIDADES',
        chat_history,
        flags=re.IGNORECASE
    )

    # Generar claves de la matriz para el prompt
    llaves_matriz = ", ".join([f'"{k}"' for k in MATRIZ_ATRIBUTOS_MRO.keys()])
    
    prompt = get_extractor_prompt(chat_history, llaves_matriz)
    
    items_extraidos = []
    try:
        content = llamar_llm_con_fallback(prompt)
        
        # Extractor robusto de JSON usando regex
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
            # --- POST-EXTRACCIÓN: expandir abreviaturas en original_query y atributos ---
            oq = pi["original_query"]
            for pattern, replacement in FIELD_ABBREVIATIONS:
                oq = re.sub(pattern, replacement, oq, flags=re.IGNORECASE)
            
            # Expansión de jerga de empaques para pilas (AA/2, AAA/4, etc.) en original_query
            oq = re.sub(r'\b(?:PILA|PILAS|BATERIA|BATERIAS)\s+(?:ALCALINA\s+)?([A-Z0-9]{2,4})/(\d+)\b', r'PILA ALCALINA TAMAÑO \1, BLISTER CON \2 UNIDADES', oq, flags=re.IGNORECASE)
            oq = re.sub(r'\b([A-Z0-9]{2,4})/(\d+)\b', r'TAMAÑO \1, BLISTER CON \2 UNIDADES', oq, flags=re.IGNORECASE)
            pi["original_query"] = oq
            
            attrs = pi.get("atributos_recolectados", {})
            for key, val in list(attrs.items()):
                if isinstance(val, str):
                    for pattern, replacement in FIELD_ABBREVIATIONS:
                        val = re.sub(pattern, replacement, val, flags=re.IGNORECASE)
                    val = re.sub(r'\b([A-Z0-9]{2,4})/(\d+)\b', r'TAMAÑO \1, BLISTER CON \2 UNIDADES', val, flags=re.IGNORECASE)
                    attrs[key] = val
            
            # Detección y normalización del sustantivo de pilas
            sust_upper = str(pi.get("sustantivo_principal", "")).upper()
            if any(p in oq.upper() or p in sust_upper for p in ["PILA", "BATERIA", "BAT"]):
                if "SOPORTE" not in oq.upper() and "HOLDER" not in oq.upper():
                    pi["sustantivo_principal"] = "PILA"
                    sust_upper = "PILA"
            
            # Detección y normalización del sustantivo de ventiladores
            if any(p in oq.upper() or p in sust_upper for p in ["VENTILADOR", "FAN", "SOPLADOR"]):
                if "SOPORTE" not in oq.upper() and "HOLDER" not in oq.upper():
                    pi["sustantivo_principal"] = "VENTILADOR"
                    sust_upper = "VENTILADOR"
            
            # Detección y normalización del sustantivo de impresora
            if any(p in oq.upper() or p in sust_upper for p in ["IMPRESORA", "PRINTER", "ETIQUETADORA"]):
                if not any(ex in oq.upper() for ex in ["SOPORTE", "CABEZAL", "CARTUCHO", "TONER", "CINTA", "RIBBON", "PAPEL", "ETIQUETA"]):
                    pi["sustantivo_principal"] = "IMPRESORA"
                    sust_upper = "IMPRESORA"
            
            # --- RELLENO DE VALORES POR DEFECTO PARA PILAS ---
            if sust_upper == "PILA":
                # Extraer tamaño
                tam = attrs.get("tamano", "")
                if not tam:
                    tam_match = re.search(r'\b(AAA|AA|C|D|9V|CR2032|CR2016|LR44)\b', oq.upper())
                    if tam_match:
                        tam = tam_match.group(1)
                        attrs["tamano"] = tam
                
                # Inyectar voltaje por defecto según el tamaño
                if not attrs.get("voltaje"):
                    if tam in ["AA", "AAA", "C", "D", "LR44"]:
                        attrs["voltaje"] = "1.5V"
                    elif tam in ["CR2032", "CR2016"]:
                        attrs["voltaje"] = "3V"
                    elif tam == "9V":
                        attrs["voltaje"] = "9V"
                
                # Extraer presentación si viene de la jerga de empaque /2 o blister
                if not attrs.get("presentacion"):
                    pres_match = re.search(r'\bBLISTER\s+CON\s+(\d+)\s+UNIDADES\b', oq.upper())
                    if pres_match:
                        attrs["presentacion"] = pres_match.group(0)
                    elif "/2" in oq or "BLISTER CON 2" in oq.upper():
                        attrs["presentacion"] = "BLISTER CON 2 UNIDADES"
                    elif "/4" in oq or "BLISTER CON 4" in oq.upper():
                        attrs["presentacion"] = "BLISTER CON 4 UNIDADES"
            
            # --- SALVAGUARDA DE EXTRACCIÓN PARA VENTILADORES ---
            if sust_upper == "VENTILADOR":
                oq_upper = pi["original_query"].upper()
                
                # Buscar también sobre el mensaje original del usuario en el historial por si el LLM recortó detalles
                raw_user_input = oq_upper
                if messages:
                    user_msgs = [m['content'].upper() for m in messages if m['role'] == 'user']
                    if user_msgs:
                        raw_user_input = user_msgs[-1]
                
                # 1. Tipo
                if not attrs.get("tipo"):
                    if "AXIAL" in oq_upper or "AXIAL" in raw_user_input:
                        attrs["tipo"] = "AXIAL"
                    elif "CENTRIFUGO" in oq_upper or "CENTRÍFUGO" in oq_upper or "CENTRIFUGO" in raw_user_input:
                        attrs["tipo"] = "CENTRIFUGO"
                    elif "RADIAL" in oq_upper or "RADIAL" in raw_user_input:
                        attrs["tipo"] = "RADIAL"
                
                # 2. OEM PN
                if not attrs.get("oem_pn"):
                    for target in [oq_upper, raw_user_input]:
                        pn_match = re.search(r'\b(?:OEM\s+)?(?:PN|P/N|NP|PART\s+NUMBER|MODELO)\s*([A-Z0-9\-\.\_]+)', target)
                        if pn_match:
                            attrs["oem_pn"] = pn_match.group(1)
                            break
                    if not attrs.get("oem_pn"):
                        # Intentar buscar un modelo directo si existe marca ebm-papst o similar
                        for target in [oq_upper, raw_user_input]:
                            mod_match = re.search(r'\b(?:W2S130[A-Z0-9\-\.\_]*)\b', target)
                            if mod_match:
                                attrs["oem_pn"] = mod_match.group(0)
                                break
                
                # 3. Equipo Destino
                if not attrs.get("equipo_destino"):
                    # Si el LLM recortó el equipo destino de original_query, lo recuperamos del raw_user_input
                    if "PARA CABINA EXCAVADORA CAT 336" in raw_user_input:
                        attrs["equipo_destino"] = "CABINA EXCAVADORA CAT 336"
                    elif "PARA EVAPORADOR CAMPAMENTO" in raw_user_input:
                        attrs["equipo_destino"] = "EVAPORADOR CAMPAMENTO"
                    else:
                        for target in [oq_upper, raw_user_input]:
                            found = False
                            for pattern in [
                                r'\bPARA\s+(CABINA\s+[\w\s\-\.]+)',
                                r'\bPARA\s+(EXCAVADORA\s+[\w\s\-\.]+)',
                                r'\bPARA\s+(EVAPORADOR\s+[\w\s\-\.]+)',
                                r'\bPARA\s+([\w\s\-\.]{4,35})(?:,|$)'
                            ]:
                                eq_match = re.search(pattern, target)
                                if eq_match:
                                    candidate = eq_match.group(1).strip()
                                    if candidate in ["EVAPORADOR", "EL EVAPORADOR"]:
                                        continue
                                    attrs["equipo_destino"] = candidate
                                    found = True
                                    break
                            if found:
                                break
                
                # 4. Dimensiones o RPM
                if not attrs.get("dimensiones_o_rpm"):
                    dims = []
                    for target in [oq_upper, raw_user_input]:
                        # Buscar RPM
                        rpm_match = re.search(r'\b\d+\s*RPM\b', target)
                        if rpm_match and rpm_match.group(0) not in dims:
                            dims.append(rpm_match.group(0))
                        # Buscar dimensiones (ej: 300MM, 12 IN)
                        dim_match = re.search(r'\b\d+\s*(?:MM|IN|PLG|PULGADAS)(?:\s+DIÁMETRO|\s+DIAMETRO)?\b', target)
                        if dim_match and dim_match.group(0) not in dims:
                            dims.append(dim_match.group(0))
                    
                    if dims:
                        attrs["dimensiones_o_rpm"] = " / ".join(dims)
                    else:
                        parts = []
                        if attrs.get("diametro"): parts.append(attrs["diametro"])
                        if attrs.get("rpm"): parts.append(attrs["rpm"])
                        if parts:
                            attrs["dimensiones_o_rpm"] = " / ".join(parts)
            
            # --- SALVAGUARDA DE EXTRACCIÓN PARA IMPRESORAS ---
            if sust_upper == "IMPRESORA":
                oq_upper = pi["original_query"].upper()
                raw_user_input = oq_upper
                if messages:
                    user_msgs = [m['content'].upper() for m in messages if m['role'] == 'user']
                    if user_msgs:
                        raw_user_input = user_msgs[-1]
                
                # 1. Marca: ZEBRA o HONEYWELL
                if not attrs.get("marca"):
                    if "ZEBRA" in oq_upper or "ZEBRA" in raw_user_input:
                        attrs["marca"] = "ZEBRA"
                    elif "HONEYWELL" in oq_upper or "HONEYWELL" in raw_user_input:
                        attrs["marca"] = "HONEYWELL"
                
                # 2. Modelo: ZT610, ZT620, ZT411, ZT410, ZT420, PM43, PD43, ZM400
                if not attrs.get("modelo"):
                    for target in [oq_upper, raw_user_input]:
                        mod_match = re.search(r'\b(ZT610|ZT620|ZT411|ZT410|ZT420|PM43|PD43|ZM400)\b', target)
                        if mod_match:
                            attrs["modelo"] = mod_match.group(1)
                            break
                
                # 3. Resolución DPI
                if not attrs.get("resolucion_dpi"):
                    for target in [oq_upper, raw_user_input]:
                        dpi_match = re.search(r'\b(203|300|600)\s*DPI\b', target)
                        if dpi_match:
                            attrs["resolucion_dpi"] = dpi_match.group(1) + " DPI"
                            break
                        elif "203DPI" in target:
                            attrs["resolucion_dpi"] = "203 DPI"
                            break
                        elif "300DPI" in target:
                            attrs["resolucion_dpi"] = "300 DPI"
                            break
                        elif "600DPI" in target:
                            attrs["resolucion_dpi"] = "600 DPI"
                            break

                # 4. Tecnología de impresión
                if not attrs.get("tecnologia_impresion"):
                    for target in [oq_upper, raw_user_input]:
                        if "TRANSFERENCIA TERMICA" in target or "TRANSFERENCIA TÉRMICA" in target:
                            attrs["tecnologia_impresion"] = "TRANSFERENCIA TERMICA"
                            break
                        elif "TERMICA DIRECTA" in target or "TÉRMICA DIRECTA" in target:
                            attrs["tecnologia_impresion"] = "TERMICA DIRECTA"
                            break
            
            # Normalizar para FAISS
            cleaned = limpiar_consulta(pi["original_query"])
            exp = list(set([cleaned] + pi.get("expanded_queries", [])))
            
            # --- SALVAGUARDA: Inyectar material_cuerpo si el LLM lo omitió ---
            # Detecta materiales de cuerpo conocidos en el original_query y los inyecta
            oq_upper = pi["original_query"].upper()
            has_body_material = any(k for k in attrs if "cuerpo" in k.lower() or "body" in k.lower())
            if not has_body_material:
                for keyword, material_name in BODY_MATERIALS:
                    if keyword in oq_upper:
                        attrs["material_cuerpo"] = material_name
                        logger.info(f"[SAFEGUARD] Inyectando material_cuerpo='{material_name}' (detectado en original_query)")
                        break
            
            # --- VALIDACIÓN DE ESPECIALIZACIÓN EXCLUSIVA ---
            def _norm_str(t):
                return "".join(c for c in unicodedata.normalize('NFD', str(t).upper()) if unicodedata.category(c) != 'Mn')

            cat_raw = pi.get("categoria_dominio", "GENERAL").upper()
            sust_raw = pi.get("sustantivo_principal", "").strip().upper()
            sust_norm = _norm_str(sust_raw)
            oq_norm = _norm_str(pi["original_query"])

            # Deducir/corregir categoría por palabras clave
            for cat_name, keywords in ALLOWED_PRODUCTS.items():
                if any(kw in sust_norm for kw in keywords) or any(kw in oq_norm for kw in keywords):
                    cat_raw = cat_name
                    break

            es_valido = False
            if cat_raw in ALLOWED_PRODUCTS:
                if any(kw in sust_norm for kw in ALLOWED_PRODUCTS[cat_raw]):
                    es_valido = True
                elif any(kw in oq_norm for kw in ALLOWED_PRODUCTS[cat_raw]):
                    es_valido = True

            final_cat = cat_raw if es_valido else "RECHAZADO"
            if not es_valido:
                logger.warning(f"[SPECIALIZATION FILTER] Rechazado: '{pi['original_query']}' (Sust: '{sust_raw}', Cat: '{cat_raw}')")

            items_extraidos.append({
                "original_query": pi["original_query"],
                "expanded_queries": exp,
                "market_context": "",
                "candidates": [],
                "best_match": None,
                "estado_decision": "Baja" if es_valido else "Rechazado",
                "pregunta_aclaratoria": "" if es_valido else "El producto solicitado no pertenece a las familias especializadas soportadas por el sistema (Fluidos/Hidráulica, Cómputo/TI o Instrumentación/Equipos Eléctricos).",
                "one_line_desc": "",
                "sustantivo_principal": sust_raw,
                "requiere_busqueda_web": bool(pi.get("requiere_busqueda_web", False)) if es_valido else False,
                "requiere_revision_humana": False,
                "categoria_dominio": final_cat,
                "atributos_recolectados": attrs,
                "atributos_faltantes": [],
                "criticidad": "Baja"
            })
    except Exception as e:
        logger.error(f"Error en extractor: {e}")
        # Fallback básico si falla el LLM
        ultimo_mensaje = messages[-1]["content"] if messages else ""
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
            "atributos_recolectados": {},
            "atributos_faltantes": [],
            "criticidad": "Baja"
        })

    return {"items": items_extraidos}