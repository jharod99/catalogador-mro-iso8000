from ..state import AgentState, ProductItem
import json
import re
import os
import logging
from typing import Dict, Any, List
from ..models import llamar_llm_con_fallback
from ..config import MARCAS_COMUNES, EQUIPOS_COMPLETOS, INDICADORES_REPUESTO, DIAMETROS_COMERCIALES, DIAMETROS_MM_COMERCIALES
from ..prompts.templates import get_decision_prompt, get_generator_prompt

logger = logging.getLogger(__name__)

MATRIZ_ATRIBUTOS_MRO = {}
def decision_maker_node(state: AgentState) -> Dict[str, Any]:
    """Nodo 4: Usa OpenRouter (Claude-3.5-Sonnet) para decidir la clase de cada ítem de forma inteligente."""
    items = state.get("items", [])
    
    estado_global = "Alta"
    mensajes_aclaratorios = []
    
    for item in items:
        # --- FILTRO DE RECHAZO: Omitir si el ítem fue marcado como RECHAZADO por el extractor ---
        if item.get("categoria_dominio") == "RECHAZADO" or item.get("estado_decision") == "Rechazado":
            item["estado_decision"] = "Rechazado"
            item["pregunta_aclaratoria"] = (
                "El producto solicitado no pertenece a las familias especializadas soportadas por el sistema "
                "(Fluidos/Hidráulica, Cómputo/TI o Instrumentación/Equipos Eléctricos). "
                "Requerimiento fuera de alcance."
            )
            estado_global = "Rechazado"
            continue

        cand_str = ""
        for idx, c in enumerate(item["candidates"], 1):
            cand_str += f"{idx}. [{c['codigo_producto']}] {c['nombre_producto']} | {c['ruta_jerarquica']}\n"
            
        prompt = get_decision_prompt(item, cand_str)
        try:
            content = llamar_llm_con_fallback(prompt, providers_order=["openrouter", "deepseek", "groq", "siliconflow", "mistral", "gemini"])
                
            # Extractor robusto de JSON para objeto {}
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
            
            item["estado_decision"] = res_json.get("confianza", "Baja")
            item["sustantivo_principal"] = res_json.get("sustantivo_principal", item.get("sustantivo_principal", ""))
            # Fusionar atributos recolectados preservando los que ya teníamos de extractor/salvaguardas
            recolectados_previos = item.get("atributos_recolectados", {})
            recolectados_nuevos = res_json.get("atributos_recolectados", {})
            combinados = {**recolectados_previos, **recolectados_nuevos}
            
            # --- NORMALIZAR CLAVES DE ATRIBUTOS PARA ALINEACIÓN MRO ---
            normalizados = {}
            for k, v in combinados.items():
                if not v:
                    continue
                k_norm = k.lower().replace(" ", "_").replace("á", "a").replace("é", "e").replace("í", "i").replace("ó", "o").replace("ú", "u")
                
                # Mapeo a modelo_exacto
                if k_norm in ["modelo", "model", "nro_modelo", "num_modelo", "modelo_exacto"]:
                    normalizados["modelo_exacto"] = v
                # Mapeo a numero_de_parte
                elif k_norm in ["numero_parte", "nro_parte", "part_number", "pn", "np", "part_no", "oem_pn", "numero_de_parte"]:
                    normalizados["numero_de_parte"] = v
                # Mapeo a tamaño_de_pantalla
                elif k_norm in ["pantalla", "tamano_pantalla", "tamano_de_pantalla", "screen_size", "screen", "tamanio_de_pantalla", "tamaño_de_pantalla"]:
                    normalizados["tamaño_de_pantalla"] = v
                # Mapeo a capacidad_de_almacenamiento
                elif k_norm in ["almacenamiento", "capacidad", "disco", "storage", "capacidad_almacenamiento", "capacidad_de_almacenamiento"]:
                    normalizados["capacidad_de_almacenamiento"] = v
                # Mapeo a sistema_operativo
                elif k_norm in ["so", "os", "sistema", "sistema_operativo"]:
                    normalizados["sistema_operativo"] = v
                # Mapeo a velocidad_nominal
                elif k_norm in ["velocidad", "velocidad_nominal", "velocidad_rpm", "rpm", "giro"]:
                    normalizados["velocidad_nominal"] = v
                # Mapeo a norma
                elif k_norm in ["norma", "estandar", "norma_fabricacion", "standard"]:
                    normalizados["norma"] = v
                else:
                    normalizados[k] = v

            # --- DEDUCCIÓN DE ATRIBUTOS PARA MOTORES ELÉCTRICOS ---
            sust_upper_val = item.get("sustantivo_principal", "").upper()
            if sust_upper_val == "MOTOR" or "MOTOR" in item["original_query"].upper():
                # 1. Deducir norma (NEMA / IEC) a partir de la carcasa o query
                carcasa_val = str(normalizados.get("carcasa", "")).upper()
                query_upper = item["original_query"].upper()
                
                norma_deducida = None
                if "NEMA" in carcasa_val or "NEMA" in query_upper or any(f"{n}T" in query_upper or f"{n}T" in carcasa_val for n in ["143", "145", "182", "184", "213", "215", "254", "256", "284", "286", "324", "326", "364", "365", "404", "405", "444", "445"]):
                    norma_deducida = "NEMA"
                elif "IEC" in carcasa_val or "IEC" in query_upper:
                    norma_deducida = "IEC"
                
                if norma_deducida and not normalizados.get("norma"):
                    logger.info(f"[MOTOR DEDUCTION] Deducida norma {norma_deducida} a partir de la carcasa/query.")
                    normalizados["norma"] = norma_deducida
                    
                # 2. Deducir RPM a partir de Frecuencia (Hz) y Polos
                hz_match = re.search(r'(\d+)\s*(?:HZ|HERTZIO)', query_upper)
                frecuencia = None
                if hz_match:
                    frecuencia = int(hz_match.group(1))
                else:
                    hz_attr = normalizados.get("frecuencia")
                    if hz_attr:
                        hz_attr_match = re.search(r'(\d+)', str(hz_attr))
                        if hz_attr_match:
                            frecuencia = int(hz_attr_match.group(1))
                            
                polos_match = re.search(r'(\d+)\s*(?:POLOS|POLES|P)\b', query_upper)
                polos = None
                if polos_match:
                    polos = int(polos_match.group(1))
                else:
                    polos_attr = normalizados.get("polos")
                    if polos_attr:
                        polos_attr_match = re.search(r'(\d+)', str(polos_attr))
                        if polos_attr_match:
                            polos = int(polos_attr_match.group(1))
                            
                if frecuencia and polos and polos > 0:
                    # Fórmula síncrona: (120 * f) / p
                    rpm_sinc = int((120 * frecuencia) / polos)
                    # Estimación nominal con deslizamiento (~2% a 5% de caída)
                    deslizamiento = 0.03
                    rpm_nom_est = int(rpm_sinc * (1 - deslizamiento))
                    rango_rpm = f"{rpm_nom_est} RPM"
                    
                    if not normalizados.get("velocidad_nominal"):
                        logger.info(f"[MOTOR DEDUCTION] Deducido RPM: {rango_rpm} a partir de {frecuencia}Hz y {polos} polos.")
                        normalizados["velocidad_nominal"] = rango_rpm

            item["atributos_recolectados"] = normalizados
            
            # --- FILTRADO PROGRAMÁTICO DE FALTANTES YA PRESENTES ---
            faltantes_reales = []
            for f in res_json.get("atributos_faltantes", []):
                attr_name = f.get("atributo", "")
                attr_name_norm = attr_name.lower().replace(" ", "_").replace("á", "a").replace("é", "e").replace("í", "i").replace("ó", "o").replace("ú", "u")
                
                canonical_name = attr_name
                if attr_name_norm in ["modelo", "model", "nro_modelo", "num_modelo", "modelo_exacto"]:
                    canonical_name = "modelo_exacto"
                elif attr_name_norm in ["numero_parte", "nro_parte", "part_number", "pn", "np", "part_no", "oem_pn", "numero_de_parte"]:
                    canonical_name = "numero_de_parte"
                elif attr_name_norm in ["pantalla", "tamano_pantalla", "tamano_de_pantalla", "screen_size", "screen", "tamanio_de_pantalla", "tamaño_de_pantalla"]:
                    canonical_name = "tamaño_de_pantalla"
                elif attr_name_norm in ["almacenamiento", "capacidad", "disco", "storage", "capacidad_almacenamiento", "capacidad_de_almacenamiento"]:
                    canonical_name = "capacidad_de_almacenamiento"
                elif attr_name_norm in ["so", "os", "sistema", "sistema_operativo"]:
                    canonical_name = "sistema_operativo"
                elif attr_name_norm in ["velocidad", "velocidad_nominal", "velocidad_rpm", "rpm", "giro"]:
                    canonical_name = "velocidad_nominal"
                elif attr_name_norm in ["norma", "estandar", "norma_fabricacion", "standard"]:
                    canonical_name = "norma"
                
                if canonical_name not in normalizados:
                    f["atributo"] = canonical_name
                    faltantes_reales.append(f)
            
            item["criticidad"] = res_json.get("criticidad", "Baja")
            item["pregunta_aclaratoria"] = res_json.get("pregunta", "")
            
            # --- SALVAGUARDA PROGRAMÁTICA DE ATRIBUTOS MRO (FILTRO DURO) ---
            sust = item.get("sustantivo_principal", "").upper()
            recolectados_normalizados = normalizados
            
            # 1. Regla 1 (La Ley de la Marca - OBLIGATORIA)
            original_upper = item["original_query"].upper()
            tiene_marca = False
            if recolectados_normalizados.get("marca") or recolectados_normalizados.get("fabricante"):
                tiene_marca = True
            else:
                if any(m in original_upper for m in MARCAS_COMUNES):
                    tiene_marca = True
            
            marca_incompleta = False
            if tiene_marca:
                if "modelo_exacto" not in recolectados_normalizados and "numero_de_parte" not in recolectados_normalizados:
                    marca_incompleta = True

            # 2. Regla 2 (Ensamble vs. Componente)
            ensamble_incompatible = False
            if item.get("candidates"):
                best_cand = item["candidates"][0]
                ruta_candidato = best_cand.get("ruta_hierarchical", "").upper()
                desc_candidato = best_cand.get("product_name", "").upper()
                
                if any(eq in sust for eq in EQUIPOS_COMPLETOS):
                    if any(ind in ruta_candidato or ind in desc_candidato for ind in INDICADORES_REPUESTO):
                        ensamble_incompatible = True

            # 3. Regla 3 (Estándares Comerciales)
            diametro_invalido = False
            if sust == "TUBERIA":
                diam_val = recolectados_normalizados.get("diametro")
                if diam_val:
                    match = re.search(r"(\d+(\.\d+)?)", str(diam_val))
                    if match:
                        num = float(match.group(1))
                        # Valores habituales de diámetro comercial
                        es_comercial = any(abs(num - val) < 0.05 for val in DIAMETROS_COMERCIALES) or any(abs(num - val) < 0.5 for val in DIAMETROS_MM_COMERCIALES)
                        if not es_comercial:
                            diametro_invalido = True

            # --- DETECTAR ATRIBUTOS FALTANTES SEGÚN LA DEDUCCIÓN DINÁMICA ---
            # Inyectar faltante de modelo_exacto si aplica por marca
            if marca_incompleta:
                if not any(f.get("atributo") == "modelo_exacto" for f in faltantes_reales):
                    faltantes_reales.append({
                        "atributo": "modelo_exacto",
                        "tipo_interfaz": "texto",
                        "placeholder": "Ingrese el modelo exacto o número de parte..."
                    })

            # Inyectar faltante de diametro si es un diámetro inválido (para corregirse)
            if diametro_invalido:
                if not any(f.get("atributo") == "diametro" for f in faltantes_reales):
                    faltantes_reales.append({
                        "atributo": "diametro",
                        "tipo_interfaz": "botones",
                        "opciones": ["1/2 PLG", "3/4 PLG", "1 PLG", "2 PLG", "3 PLG", "4 PLG", "6 PLG", "8 PLG", "10 PLG", "12 PLG"]
                    })

            # --- DETECCIÓN DE CONFLICTOS FÍSICOS/GEOMÉTRICOS ---
            conflicto_detectado = False
            msg_conflicto = ""
            
            modelo_val = str(recolectados_normalizados.get("modelo_exacto", "")).upper()
            marca_val = str(recolectados_normalizados.get("marca", "")).upper()
            
            # Buscar valor de factor de forma
            factor_forma = None
            for k, v in recolectados_normalizados.items():
                if k.lower() in ["factor_forma", "factor_de_forma", "form_factor", "dimensiones", "tamano", "tamanio"]:
                    factor_forma = str(v).upper()
                    break
            
            # Conflicto Samsung 990/980 Pro con factor de forma no-2280
            if "SAMSUNG" in marca_val and any(x in modelo_val for x in ["990 PRO", "980 PRO", "970 EVO", "990 EVO", "980", "990"]):
                if factor_forma and any(x in factor_forma for x in ["2242", "2230", "2260"]):
                    conflicto_detectado = True
                    msg_conflicto = f"El SSD Samsung {recolectados_normalizados.get('modelo_exacto')} se fabrica únicamente en el factor de forma M.2 2280. Su especificación de factor de forma ({factor_forma}) es físicamente incompatible."

            # --- SALVAGUARDA DE NÚMERO DE PARTE (UNÍVOCO) / MODELO ESPECÍFICO ---
            # Si ya tenemos el número de parte exacto o un modelo comercial específico,
            # este define al 100% el producto. No se requiere ningún otro atributo.
            # Excepto si hay un conflicto detectado de incompatibilidad geométrica.
            tiene_pn = False
            if not conflicto_detectado:
                tiene_pn = "numero_de_parte" in recolectados_normalizados
                if "modelo_exacto" in recolectados_normalizados:
                    mod_val = str(recolectados_normalizados["modelo_exacto"])
                    # Analizar palabra por palabra para encontrar un P/N (ej: SNV2S/1000G o 83CV00FSLM)
                    palabras_modelo = mod_val.split()
                    for word in palabras_modelo:
                        w_clean = word.strip(".,()[]{}")
                        if any(c.isdigit() for c in w_clean) and any(c.isalpha() for c in w_clean) and len(w_clean) >= 5:
                            # Excluir unidades comunes de capacidad/tamaño (ej: 512GB, 1TB, 1200W, 2280M, 1000G)
                            if not re.match(r'^\d+(GB|TB|MB|HZ|HP|W|V|MM|IN|PLG|RPM|DPI|G)$', w_clean, re.IGNORECASE):
                                tiene_pn = True
                                break
                    # O si es un modelo específico comercial bien conocido con dígitos (ej: 990 Pro) y marca/tiene_marca está presente
                    if not tiene_pn and any(c.isdigit() for c in mod_val) and len(mod_val) >= 3 and tiene_marca:
                        tiene_pn = True
            
            if tiene_pn:
                logger.info(f"[SAFEGUARD] Identificador único/PN o modelo comercial detectado. Limpiando faltantes y forzando Alta.")
                faltantes_reales = []
                marca_incompleta = False
                diametro_invalido = False
                ensamble_incompatible = False
                item["estado_decision"] = "Alta"
                item["pregunta_aclaratoria"] = ""
                idx = 1

            if conflicto_detectado:
                logger.warning(f"[CONFLICT] Conflicto geométrico detectado: {msg_conflicto}")
                faltantes_reales = [{
                    "atributo": "factor_de_forma",
                    "opciones": ["M.2 2280 (Cambiar a factor compatible)", "Factor de forma 2242 (Cambiar modelo de SSD)"],
                    "tipo_interfaz": "botones",
                    "placeholder": None
                }]
                marca_incompleta = False
                diametro_invalido = False
                ensamble_incompatible = False

            item["atributos_faltantes"] = faltantes_reales

            # 4. Regla 4 (Filtro Duro) - Tomar decisión final
            if len(faltantes_reales) > 0 or marca_incompleta or ensamble_incompatible or diametro_invalido or conflicto_detectado:
                item["estado_decision"] = "Ambigüedad"
                item["best_match"] = None
                idx = None
                
                # Modificar pregunta aclaratoria específica
                if conflicto_detectado:
                    item["pregunta_aclaratoria"] = msg_conflicto
                elif marca_incompleta:
                    item["pregunta_aclaratoria"] = "Indique el modelo exacto o número de parte del fabricante."
                elif ensamble_incompatible:
                    item["pregunta_aclaratoria"] = "¿Busca el equipo completo o un repuesto específico para ese equipo?"
                elif diametro_invalido:
                    item["pregunta_aclaratoria"] = "El valor ingresado no coincide con un estándar comercial habitual. Por favor confirme el dato técnico."
            else:
                # Todo completo y coherente
                best_score = item["candidates"][0]["score_percentage"] if item.get("candidates") else 0.0
                if best_score >= 80.0:
                    logger.info(f"[SAFEGUARD] Atributos completos deducidos dinámicamente y score alto ({best_score:.2f}%). Forzando estado 'Alta'.")
                    item["estado_decision"] = "Alta"
                    item["pregunta_aclaratoria"] = ""
                    idx = 1
                else:
                    # RAG score is low, even though attributes are complete
                    item["estado_decision"] = "Ambig\u00fcedad"
                    item["pregunta_aclaratoria"] = "Indique las especificaciones técnicas detalladas del producto."
            
            if idx and 1 <= idx <= len(item["candidates"]):
                item["best_match"] = item["candidates"][idx - 1]
                
            # --- FLAG DE CUARENTENA ---
            best_score = item["candidates"][0]["score_percentage"] if item.get("candidates") else 0.0
            if 50.0 < best_score < 85.0 and len(item.get("atributos_faltantes", [])) == 0 and not ensamble_incompatible and not marca_incompleta and not diametro_invalido and not conflicto_detectado:
                logger.warning(f"[QUARANTINE] Score RAG ({best_score:.2f}%) en rango de cuarentena (50%-85%) y atributos completos. Forzando estado 'Alta' con requiere_revision_humana=True.")
                item["estado_decision"] = "Alta"
                item["requiere_revision_humana"] = True
                item["pregunta_aclaratoria"] = ""
                if item.get("candidates"):
                    item["best_match"] = item["candidates"][0]
            
            if item["estado_decision"] != "Alta":
                estado_global = "Ambig\u00fcedad"
                msg_pregunta = item["pregunta_aclaratoria"] if item["pregunta_aclaratoria"] else "Necesito más detalles."
                # Quitar marcas ** de negrita markdown para visualización limpia en frontend
                msg_pregunta = msg_pregunta.replace("**", "")
                item["pregunta_aclaratoria"] = msg_pregunta
                mensajes_aclaratorios.append(f"• \"{item['original_query']}\": {msg_pregunta}")
                
        except Exception as e:
            logger.error(f"Error en decision_maker para {item['original_query']}: {e}")
            item["estado_decision"] = "Baja"
            item["sustantivo_principal"] = item.get("sustantivo_principal", "")
            item["atributos_recolectados"] = item.get("atributos_recolectados", {})
            item["atributos_faltantes"] = []
            item["criticidad"] = "Baja"
            item["pregunta_aclaratoria"] = "Error procesando la solicitud."
            estado_global = "Baja"

    mensaje_global = ""
    if estado_global != "Alta":
        mensaje_global = "Tengo algunas dudas para poder clasificar correctamente:\n" + "\n".join(mensajes_aclaratorios)
        
    return {"items": items, "estado_global": estado_global, "mensaje_global": mensaje_global}

def generator_node(state: AgentState) -> Dict[str, Any]:
    """Nodo 5: Genera una línea descriptiva por ítem."""
    items = state.get("items", [])
    
    for item in items:
        if item["estado_decision"] == "Alta" and item["best_match"]:
            cod = item["best_match"]["codigo_producto"]
            nom = item["best_match"]["nombre_producto"]
            
            prompt = get_generator_prompt(item, nom, item.get('atributos_recolectados', {}))
            try:
                debug_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "debug_prompt.txt")
                with open(debug_path, "a", encoding="utf-8") as debug_file:
                    debug_file.write(f"\n=========================================\nITEM: {item['original_query']}\nPROMPT:\n{prompt}\n")
            except Exception:
                pass
                    
            try:
                desc = llamar_llm_con_fallback(prompt, providers_order=["groq", "deepseek", "siliconflow", "mistral", "gemini", "openrouter"])
                desc = desc.strip().replace("\n", " ")
                desc = desc.strip('"\'')
            except Exception as e_llm:
                logger.warning(f"[GENERATOR] Error en LLMs ({e_llm}). Usando fallback de limpieza programática en Python.")
                desc = item.get('original_query', '')
                
            # --- LIMPIEZA PROGRAMÁTICA STRICT ---
            # Elimina cualquier bloque de paréntesis o texto suelto explicativo de datos no provistos
            desc = re.sub(
                r'(?:,\s*)?(?:(?:\b(?:sin|no)\b\s+(?:especifica|especificado|marca|modelo|p/n|n/a|aplica)\b)|(?:marca\s+no\s+especificada)|(?:p/n\s+no\s+especificado)|(?:\([^)]*(?:no\s+se\s+proporciona|no\s+disponible|n/a|no\s+especifica|sin\s+marca|no\s+aplica|marca\s+no\s+especificada)[^)]*\)))',
                '', 
                desc, 
                flags=re.IGNORECASE
            )
            # Eliminar placeholders de NP/PN como "NP [CÓDIGO]" o "NP NO DISPONIBLE"
            desc = re.sub(
                r'(?:,\s*)?(?:NP|PN|P/N)\s*(?:\[[^\]]*\]|NO\s+DISPONIBLE|NO\s+APLICA|N/A|NO\s+SE\s+PROPORCIONA|NO\s+ESPECIFICADO|NO\s+ESPECIFICA)\b',
                '',
                desc,
                flags=re.IGNORECASE
            )
            # Eliminar cualquier otro placeholder genérico en corchetes
            desc = re.sub(r'(?:,\s*)?\[[^\]]*\]', '', desc)
            # Asegurar formato correcto de NP/PN al final y no como atributo separado (solo si el código tiene dígitos)
            desc = re.sub(r',\s*([\w\.\-]*\d[\w\.\-]*),\s*(NP|PN|P/N)\b', r', \2 \1', desc, flags=re.IGNORECASE)
            # Eliminar "NP", "PN" o "P/N" sueltos al final de la descripción sin ningún código asociado
            desc = re.sub(r'(?:,\s*|\s+)\b(?:NP|PN|P/N)\b\s*$', '', desc, flags=re.IGNORECASE)
            
            # --- EXPANSIÓN DE ABREVIATURAS INDUSTRIALES (PROGRAMÁTICA) ---
            # Expandir F°F°, FF, F.F. a FIERRO FUNDIDO
            desc = re.sub(r'\bF\s*°\s*F\s*°\b', 'FIERRO FUNDIDO', desc, flags=re.IGNORECASE)
            desc = re.sub(r'\bF\.F\.\b', 'FIERRO FUNDIDO', desc, flags=re.IGNORECASE)
            # Eliminar cualquier caracter ° residual
            desc = desc.replace('°', '')
            # Eliminar etiquetas redundantes tipo "DISCO:", "MARCA:", "MATERIAL:", "ACCIONAMIENTO:"
            desc = re.sub(r'\b(DISCO|MARCA|MATERIAL|ACCIONAMIENTO|TIPO DE CONEXION|ACTUACION)\s*:\s*', '', desc, flags=re.IGNORECASE)
            
            # --- LIMPIEZA PROGRAMÁTICA DE FRASES REDUNDANTES DE CÓMPUTO/TI (ISO 8000) ---
            desc = re.sub(r'\bCAPACIDAD\s+DE\s+', '', desc, flags=re.IGNORECASE)
            desc = re.sub(r'\bDE\s+ALMACENAMIENTO\s+INTERNO\b', '', desc, flags=re.IGNORECASE)
            desc = re.sub(r'\bDE\s+ALMACENAMIENTO\b', '', desc, flags=re.IGNORECASE)
            desc = re.sub(r'\bDE\s+MEMORIA\s+RAM\b', 'RAM', desc, flags=re.IGNORECASE)
            desc = re.sub(r'\bMEMORIA\s+RAM\b', 'RAM', desc, flags=re.IGNORECASE)
            desc = re.sub(r'\bCONECTIVIDAD\s+', '', desc, flags=re.IGNORECASE)
            desc = re.sub(r'\bCOLOR\s+', '', desc, flags=re.IGNORECASE)
            desc = re.sub(r'(?:,\s*)?\bEQUIPO\s+LIBERADO(?:\s+PARA\s+CUALQUIER\s+OPERADOR)?\b', '', desc, flags=re.IGNORECASE)
            desc = re.sub(r'^TELÉFONO\s+CELULAR\s+INTELIGENTE\b', 'SMARTPHONE', desc, flags=re.IGNORECASE)
            desc = re.sub(r'^TELEFONO\s+CELULAR\s+INTELIGENTE\b', 'SMARTPHONE', desc, flags=re.IGNORECASE)
            desc = re.sub(r'^TELÉFONO\s+CELULAR\b', 'CELULAR', desc, flags=re.IGNORECASE)
            desc = re.sub(r'^TELEFONO\s+CELULAR\b', 'CELULAR', desc, flags=re.IGNORECASE)
            
            # Eliminar comillas dobles residuales de pulgadas
            desc = desc.replace('"', '').replace("'", "")
            
            # --- ANTI-ALUCINACIÓN DE NP/PN ---
            # Si el LLM inyectó un NP/PN que NO existía en la consulta original, eliminarlo
            np_match = re.search(r'(?:,\s*)?\b(?:NP|PN|P/N)\s+([\w\.\-]+)', desc, flags=re.IGNORECASE)
            if np_match:
                np_code = np_match.group(1)
                original = item.get('original_query', '')
                if np_code.upper() not in original.upper():
                    desc = re.sub(r'(?:,\s*)?\b(?:NP|PN|P/N)\s+[\w\.\-]+', '', desc, flags=re.IGNORECASE)
            
            # --- REMOCIÓN DE TAGS DE INSTRUMENTACIÓN (PROGRAMÁTICO) ---
            # El TAG es un identificador lógico de planta y no debe ensuciar la descripción física del material
            tag_code = item.get("atributos_recolectados", {}).get("tag_instrumentacion")
            if tag_code:
                # Eliminar "TAG [CÓDIGO]" o el código de TAG suelto si fue inyectado por el LLM
                desc = re.sub(r'(?:,\s*)?\bTAG\s+' + re.escape(tag_code), '', desc, flags=re.IGNORECASE)
                desc = re.sub(r'(?:,\s*)?\b' + re.escape(tag_code) + r'\b', '', desc, flags=re.IGNORECASE)
                # Limpiar cualquier alusión que haya quedado como NP o PN asociada al TAG
                desc = re.sub(r'(?:,\s*)?\b(?:NP|PN|P/N)\s+' + re.escape(tag_code), '', desc, flags=re.IGNORECASE)
            
            # --- NORMALIZAR INICIO DE CAUDALIMETROS ---
            if item.get("sustantivo_principal") == "CAUDALIMETRO":
                # Si no empieza por CAUDALIMETRO, corregir el inicio
                if not desc.upper().startswith("CAUDALIMETRO"):
                    desc = re.sub(r'^SENSOR\s+(?:DE\s+)?FLUJO\s+(?:TIPO\s+)?ELECTROMAGNETICO', 'CAUDALIMETRO ELECTROMAGNETICO', desc, flags=re.IGNORECASE)
                    desc = re.sub(r'^SENSOR\s+(?:DE\s+)?FLUJO', 'CAUDALIMETRO', desc, flags=re.IGNORECASE)
                    if not desc.upper().startswith("CAUDALIMETRO"):
                        desc = f"CAUDALIMETRO, {desc}"
            
            attrs = item.get("atributos_recolectados", {})
            
            # --- FORMATEO ESTRICTO EN PYTHON PARA VENTILADORES ---
            if item.get("sustantivo_principal") == "VENTILADOR":
                tipo = attrs.get("tipo", "").upper()
                voltaje = attrs.get("voltaje", "").upper()
                dims_rpm = attrs.get("dimensiones_o_rpm", "").upper()
                oem_pn = attrs.get("oem_pn", "").upper()
                eq_dest = attrs.get("equipo_destino", "").upper()
                marca = attrs.get("marca", "").upper()
                modelo = attrs.get("modelo", "").upper()
                
                # Limpieza y espaciado de unidades en variables
                if voltaje:
                    voltaje = re.sub(r'\b(\d+)\s*(VDC|VAC|V)\b', r'\1 \2', voltaje)
                if dims_rpm:
                    dims_rpm = re.sub(r'\b(\d+)\s*(MM|RPM|IN|PLG|PULGADAS)\b', r'\1 \2', dims_rpm)
                
                # Armar la línea descriptiva
                parts = ["VENTILADOR PARA EVAPORADOR"]
                if tipo:
                    parts[0] = f"VENTILADOR {tipo} PARA EVAPORADOR"
                
                if voltaje:
                    parts.append(voltaje)
                if dims_rpm:
                    parts.append(dims_rpm)
                if oem_pn:
                    parts.append(f"OEM PN {oem_pn}")
                if eq_dest:
                    parts.append(f"PARA {eq_dest}")
                if marca:
                    if marca not in eq_dest:
                        parts.append(marca)
                if modelo:
                    if modelo != oem_pn and modelo not in oem_pn:
                        parts.append(modelo)
                        
                desc = ", ".join(parts)
            
            # --- FORMATEO ESTRICTO EN PYTHON PARA SMARTPHONES / CELULARES (ISO 8000) ---
            sust_main = str(item.get("sustantivo_principal", "")).upper()
            oq_upper = str(item.get("original_query", "")).upper()
            if sust_main in ["TELEFONO", "CELULAR", "SMARTPHONE"] or any(k in oq_upper for k in ["CELULAR", "SMARTPHONE", "GALAXY", "POCO", "IPHONE"]):
                marca = ""
                modelo = ""
                capacidad = ""
                ram = ""
                red = ""
                color = ""
                
                for k, v in attrs.items():
                    k_lower = str(k).lower()
                    v_str = str(v).upper()
                    if "marca" in k_lower:
                        marca = v_str
                    elif "modelo" in k_lower:
                        modelo = v_str
                    elif "almacenamiento" in k_lower or "capacidad" in k_lower:
                        capacidad = v_str
                    elif "ram" in k_lower:
                        ram = v_str
                    elif "conectividad" in k_lower or "red" in k_lower:
                        red = v_str
                    elif "color" in k_lower:
                        color = v_str
                        
                # Limpieza estricta de sufijos redundantes
                if capacidad:
                    capacidad = re.sub(r'\b(?:CAPACIDAD\s+DE\s+|DE\s+ALMACENAMIENTO(?:\s+INTERNO)?|ALMACENAMIENTO)\b', '', capacidad, flags=re.IGNORECASE).strip()
                if ram:
                    ram = re.sub(r'\b(?:DE\s+MEMORIA\s+)?RAM\b', '', ram, flags=re.IGNORECASE).strip()
                    if ram and not ram.endswith("RAM"):
                        ram = f"{ram} RAM"
                if red:
                    red = re.sub(r'\bCONECTIVIDAD\s+', '', red, flags=re.IGNORECASE).strip()
                if color:
                    color = re.sub(r'\bCOLOR\s+', '', color, flags=re.IGNORECASE).strip()
                
                header = "SMARTPHONE" if ("SMART" in oq_upper or "A54" in modelo or "IPHONE" in modelo or "POCO" in modelo or "GALAXY" in modelo) else "CELULAR"
                if marca and marca not in header:
                    header += f" {marca}"
                if modelo and modelo not in header:
                    header += f" {modelo}"
                    
                parts = [header]
                if capacidad:
                    parts.append(capacidad)
                if ram:
                    parts.append(ram)
                if red:
                    parts.append(red)
                if color:
                    parts.append(color)
                    
                desc = ", ".join(parts)
            
            # --- FORMATEO ESTRICTO EN PYTHON PARA IMPRESORAS ---
            if item.get("sustantivo_principal") == "IMPRESORA":
                tecnologia = attrs.get("tecnologia_impresion", "").upper()
                resolucion = attrs.get("resolucion_dpi", "").upper()
                marca = attrs.get("marca", "").upper()
                modelo = attrs.get("modelo", "").upper()
                
                parts = ["IMPRESORA DE CODIGOS DE BARRA"]
                if tecnologia:
                    parts.append(tecnologia)
                if resolucion:
                    parts.append(resolucion)
                if marca:
                    parts.append(f"MARCA {marca}")
                if modelo:
                    parts.append(f"MODELO {modelo}")
                
                desc = ", ".join(parts)
            
            # --- FORMATEO POSICIONAL ESTRICTO PARA TUBERIAS (ISO 8000) ---
            if item.get("sustantivo_principal") == "TUBERIA":
                mat   = str(attrs.get("material", attrs.get("material_cuerpo", ""))).upper()
                tipo  = str(attrs.get("tipo", attrs.get("tipo_tuberia", ""))).upper()
                diam  = str(attrs.get("diametro", attrs.get("diametro_nominal", ""))).upper()
                ced   = str(attrs.get("cedula", attrs.get("schedule", attrs.get("sdr", attrs.get("espesor_pared", ""))))).upper()
                norma_t = str(attrs.get("norma", attrs.get("norma_fabricacion", attrs.get("grado", "")))).upper()
                ext   = str(attrs.get("extremos", "")).upper()
                lon   = str(attrs.get("longitud_tramo", attrs.get("longitud", ""))).upper()
                recub = str(attrs.get("recubrimiento", attrs.get("revestimiento", ""))).upper()
                # Normalizar cédula
                ced = re.sub(r'\bSCHEDULE\b', 'SCH', ced, flags=re.IGNORECASE)
                ced = re.sub(r'\bCEDULA\b', 'SCH', ced, flags=re.IGNORECASE)
                # Normalizar longitud
                lon = re.sub(r'\b(METROS?)\b', 'M', lon, flags=re.IGNORECASE)
                # Detectar si el material ya está implícito en la norma
                norma_upper_t = norma_t.upper()
                mat_redund = (("A106" in norma_upper_t and "CARBONO" in mat) or
                              ("A53" in norma_upper_t and "CARBONO" in mat) or
                              ("A312" in norma_upper_t and "INOX" in mat) or
                              ("D1785" in norma_upper_t and "PVC" in mat))
                if mat and not mat_redund:
                    header_tub = f"TUBERIA {mat}" + (f" {tipo}" if tipo and tipo not in mat else "")
                elif tipo:
                    header_tub = f"TUBERIA {tipo}"
                else:
                    header_tub = "TUBERIA"
                parts_tub = [header_tub]
                if diam:   parts_tub.append(diam)
                if ced:    parts_tub.append(ced)
                if norma_t: parts_tub.append(norma_t)
                if ext:    parts_tub.append(ext)
                if lon:    parts_tub.append(lon)
                if recub and "RECUBRIMIENTO" not in recub:
                    parts_tub.append(f"RECUBRIMIENTO {recub}")
                elif recub:
                    parts_tub.append(recub)
                desc = ", ".join(p for p in parts_tub if p)

            # --- FORMATEO POSICIONAL ESTRICTO PARA VÁLVULAS (ISO 8000) ---
            if item.get("sustantivo_principal") == "VALVULA":
                tipo_v  = str(attrs.get("tipo", attrs.get("tipo_valvula", ""))).upper()
                diam_v  = str(attrs.get("diametro", attrs.get("diametro_nominal", ""))).upper()
                rating  = str(attrs.get("rating", attrs.get("clase_presion", attrs.get("presion", "")))).upper()
                conex   = str(attrs.get("tipo_conexion", attrs.get("conexion", attrs.get("extremos", "")))).upper()
                mat_c   = str(attrs.get("material_cuerpo", attrs.get("material", ""))).upper()
                mat_d   = str(attrs.get("material_disco", attrs.get("disco", attrs.get("obturador", "")))).upper()
                mat_a   = str(attrs.get("material_asiento", attrs.get("asiento", ""))).upper()
                accion  = str(attrs.get("accionamiento", "")).upper()
                norma_v = str(attrs.get("norma", attrs.get("norma_fabricacion", ""))).upper()
                marca_v = str(attrs.get("marca", "")).upper()
                mod_v   = str(attrs.get("modelo_exacto", attrs.get("numero_de_parte", ""))).upper()
                # Normalizar rating
                rating = re.sub(r'\b(150|300|600|900|1500|2500|3000)\s*(LBS?|LIBRAS?|#)\b', r'CL\1', rating, flags=re.IGNORECASE)
                rating = re.sub(r'\bCL\s+(\d+)\b', r'CL\1', rating, flags=re.IGNORECASE)
                header_val = "VALVULA"
                if tipo_v: header_val += f" {tipo_v}"
                if diam_v: header_val += f" {diam_v}"
                parts_val = [header_val]
                if rating: parts_val.append(rating)
                if conex:  parts_val.append(conex)
                if mat_c:
                    parts_val.append(f"CUERPO {mat_c}" if "CUERPO" not in mat_c else mat_c)
                if mat_d:
                    parts_val.append(f"DISCO {mat_d}" if "DISCO" not in mat_d else mat_d)
                if mat_a:
                    parts_val.append(f"ASIENTO {mat_a}" if "ASIENTO" not in mat_a else mat_a)
                if accion:
                    parts_val.append(accion if accion.startswith("CON ") else f"CON {accion}")
                if norma_v and norma_v not in " ".join(parts_val):
                    parts_val.append(norma_v)
                if marca_v: parts_val.append(marca_v)
                if mod_v:   parts_val.append(mod_v)
                desc = ", ".join(p for p in parts_val if p)

            # --- FORMATEO POSICIONAL ESTRICTO PARA MOTORES ELÉCTRICOS (ISO 8000) ---
            if item.get("sustantivo_principal") == "MOTOR":
                pot    = str(attrs.get("potencia", attrs.get("potencia_hp", attrs.get("potencia_kw", "")))).upper()
                volt   = str(attrs.get("voltaje", attrs.get("tension", ""))).upper()
                fases  = str(attrs.get("fases", "")).upper()
                rpm    = str(attrs.get("velocidad_nominal", "")).upper()
                freq   = str(attrs.get("frecuencia", "")).upper()
                carc   = str(attrs.get("carcasa", "")).upper()
                ip_v   = str(attrs.get("proteccion", attrs.get("ip", attrs.get("grado_proteccion", "")))).upper()
                mont   = str(attrs.get("tipo_montaje", attrs.get("montaje", ""))).upper()
                norma_m= str(attrs.get("norma", "")).upper()
                marca_m= str(attrs.get("marca", "")).upper()
                mod_m  = str(attrs.get("modelo_exacto", attrs.get("numero_de_parte", ""))).upper()
                # Normalizar potencia
                pot = re.sub(r'\b(\d+[\.,]?\d*)\s*(HP|CV)\b', r'\1 HP', pot, flags=re.IGNORECASE)
                pot = re.sub(r'\b(\d+[\.,]?\d*)\s*(KW|KVA)\b', r'\1 KW', pot, flags=re.IGNORECASE)
                # Normalizar fases
                fases = re.sub(r'\b3\s*F(?:ASES?)?\b', 'TRIFÁSICO', fases, flags=re.IGNORECASE)
                fases = re.sub(r'\b1\s*F(?:ASE?)?\b', 'MONOFÁSICO', fases, flags=re.IGNORECASE)
                fases = re.sub(r'\bTRI\s*F[ÁA]SICO\b', 'TRIFÁSICO', fases, flags=re.IGNORECASE)
                # Normalizar RPM/frecuencia
                if rpm and not rpm.upper().endswith("RPM"):
                    rpm = f"{rpm} RPM"
                rpm = re.sub(r'\b(\d+)\s*RPM\b', r'\1 RPM', rpm)
                freq = re.sub(r'\b(\d+)\s*(HZ|HERTZ|HERZIOS)\b', r'\1 HZ', freq, flags=re.IGNORECASE)
                # Normalizar IP
                if ip_v and not ip_v.startswith("IP"):
                    ip_v = f"IP{ip_v}"
                if mont and not mont.startswith("MONTAJE"):
                    mont = f"MONTAJE {mont}"
                parts_mot = ["MOTOR ELÉCTRICO"]
                if pot:    parts_mot.append(pot)
                if volt:   parts_mot.append(volt)
                if fases:  parts_mot.append(fases)
                if rpm:    parts_mot.append(rpm)
                if freq:   parts_mot.append(freq)
                if carc:   parts_mot.append(f"CARCASA {carc}" if "CARCASA" not in carc else carc)
                if ip_v:   parts_mot.append(ip_v)
                if mont:   parts_mot.append(mont)
                if norma_m and norma_m not in " ".join(parts_mot):
                    parts_mot.append(norma_m)
                if marca_m: parts_mot.append(marca_m)
                if mod_m:   parts_mot.append(mod_m)
                desc = ", ".join(p for p in parts_mot if p)

            # --- FORMATEO POSICIONAL ESTRICTO PARA LAPTOP / PC (ISO 8000) ---
            sust_m_upper = str(item.get("sustantivo_principal", "")).upper()
            oq_upper_lap = str(item.get("original_query", "")).upper()
            is_laptop = (sust_m_upper in ["LAPTOP", "COMPUTADORA", "PC", "COMPUTADOR"] or
                         any(k in oq_upper_lap for k in ["LAPTOP", "NOTEBOOK", "THINKPAD", "MACBOOK", "CHROMEBOOK"]))
            if is_laptop and sust_m_upper not in ["TELEFONO", "CELULAR", "SMARTPHONE"]:
                marca_l  = str(attrs.get("marca", "")).upper()
                serie_l  = str(attrs.get("modelo_exacto", attrs.get("serie", attrs.get("numero_de_parte", "")))).upper()
                cpu_l    = str(attrs.get("procesador", attrs.get("cpu", ""))).upper()
                ram_l    = str(attrs.get("memoria_ram", attrs.get("ram", ""))).upper()
                sto_l    = str(attrs.get("capacidad_de_almacenamiento", attrs.get("almacenamiento", attrs.get("disco", "")))).upper()
                scr_l    = str(attrs.get("tamaño_de_pantalla", attrs.get("pantalla", ""))).upper()
                so_l     = str(attrs.get("sistema_operativo", "")).upper()
                # Limpiar redundancias
                ram_l = re.sub(r'\b(?:DE\s+MEMORIA\s+)?RAM\b', '', ram_l, flags=re.IGNORECASE).strip()
                if ram_l and not ram_l.upper().endswith("RAM"):
                    ram_l = f"{ram_l} RAM"
                sto_l = re.sub(r'\b(?:DE\s+ALMACENAMIENTO(?:\s+INTERNO)?|ALMACENAMIENTO)\b', '', sto_l, flags=re.IGNORECASE).strip()
                scr_l = re.sub(r'\b(\d+[\.,]?\d*)\s*(PULGADAS?|IN|PLG|")\b', r'\1 IN', scr_l, flags=re.IGNORECASE)
                cpu_l = re.sub(r'^PROCESADOR\s+', '', cpu_l, flags=re.IGNORECASE).strip()
                # Header
                header_lap = "LAPTOP"
                if marca_l and marca_l not in serie_l:
                    header_lap += f" {marca_l}"
                if serie_l:
                    header_lap += f" {serie_l}"
                parts_lap = [header_lap]
                if cpu_l:  parts_lap.append(f"PROCESADOR {cpu_l}" if not cpu_l.startswith("PROCESADOR") else cpu_l)
                if ram_l:  parts_lap.append(ram_l)
                if sto_l:  parts_lap.append(sto_l)
                if scr_l:  parts_lap.append(scr_l)
                if so_l:   parts_lap.append(so_l)
                desc = ", ".join(p for p in parts_lap if p)

            # Asegurar limpieza de espacios finales y comas sueltas
            desc = desc.strip().rstrip(',')
            
            # --- DEDUPLICACIÓN DE ATRIBUTOS (ISO 8000) ---
            attributes = [attr.strip() for attr in desc.split(',') if attr.strip()]
            unique_attributes = []
            
            for attr in attributes:
                attr_upper = attr.upper()
                # Si es un duplicado exacto, omitir
                if attr_upper in unique_attributes:
                    continue
                    
                # Si el atributo es una unidad sola (ej: "KG", "MM", "V", "HP") y ya está mencionada con número, omitir
                is_redundant_unit = False
                if attr_upper in ["KG", "MM", "V", "HP", "W", "A", "HZ"]:
                    for prev in unique_attributes:
                        if re.search(r'\b\d+\s*' + attr_upper + r'\b', prev) or re.search(r'\b\d+' + attr_upper + r'\b', prev):
                            is_redundant_unit = True
                            break
                            
                if not is_redundant_unit:
                    unique_attributes.append(attr_upper)
                    
            desc = ", ".join(unique_attributes).upper()
            if not desc:
                desc = item['original_query'].upper()
            item["one_line_desc"] = desc
            logger.info(f"[GENERATOR FINAL] {item['one_line_desc']}")
                
    return {"items": items}
