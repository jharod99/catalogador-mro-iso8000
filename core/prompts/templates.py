import json

def get_extractor_prompt(chat_history: str, llaves_matriz: str) -> str:
    return f"""
Actúa como un Experto en Clasificación de Catálogo UNSPSC.
Analiza el siguiente historial de chat y extrae TODOS los ítems individuales a catalogar.

REGLAS ESTRICTAS:
1. Si un texto se describe como un solo producto con múltiples atributos o accesorios (ej: "Estación de trabajo con procesador i9, monitor de 27 pulgadas, teclado y mouse"), es UN SOLO ÍTEM.
2. CONSERVA LA DESCRIPCIÓN COMPLETA DEL USUARIO CON TODOS SUS ATRIBUTOS en 'original_query'. ESTÁ PROHIBIDO recortar o eliminar especificaciones o accesorios.
3. Identifica y **FILTRA/ELIMINA** únicamente códigos administrativos o de inventario internos (ej: "INV-", "AF-").
4. En 'expanded_queries', genera 3 sinónimos técnicos o términos de categoría relacionados en español enfocados en la FUNCIÓN INDUSTRIAL o uso del producto para la búsqueda UNSPSC.
5. Identifica el 'sustantivo_principal' (en mayúsculas) mapeando el nombre del objeto (Ej: SILLA, VALVULA, MARTILLO, MASCARILLA, COMPUTADOR, MOTOR).
6. Asigna una 'categoria_dominio' representativa (ej: "MECANICA", "TI", "ELECTRICA", "HERRAMIENTAS", "MOBILIARIO", "SALUD", "GENERAL"). TODO producto dentro del estándar UNSPSC es bienvenido.

Historial de chat:
{chat_history}

Responde ÚNICAMENTE con un JSON en formato de array:
[
  {{
    "original_query": "Descripción completa original conservando todos los atributos y accesorios",
    "expanded_queries": ["sinonimo_1", "sinonimo_2", "sinonimo_3"],
    "sustantivo_principal": "SUSTANTIVO_PRINCIPAL_MAPEADO",
    "requiere_busqueda_web": false,
    "categoria_dominio": "GENERAL",
    "atributos_recolectados": {{}}
  }}
]
"""

def get_verifier_prompt(query: str, combined_context: str) -> str:
    return f"""
Actúa como un catalogador industrial experto.
Analiza el siguiente texto de internet para el producto "{query}":
"{combined_context}"

Extrae entre 3 y 5 palabras clave técnicas o sinónimos de uso industrial en español para este producto.
Enfócate en la FUNCIÓN del producto, no en definiciones de diccionario.
Devuelve ÚNICAMENTE un array JSON de strings con las palabras clave.
Ejemplo: ["guía de desplazamiento lineal", "termoselladora de cuña", "soldadora de geomembrana"]
"""

def get_decision_prompt(item: dict, cand_str: str) -> str:
    return f"""
# ROL Y OBJETIVO
Eres el motor principal de clasificación UNSPSC y filtrado semántico para una plataforma web de sourcing estratégico y excelencia operacional.
Tu objetivo es recibir descripciones en bruto de los usuarios, normalizar la data, prevenir errores de ambigüedad industrial y devolver códigos UNSPSC (8 dígitos) precisos.
No eres un simple buscador de catálogos; eres el guardián de la limpieza de los datos maestros de compras.

Requerimiento del usuario: "{item['original_query']}"
Sustantivo Principal: "{item.get('sustantivo_principal', '')}"
Atributos recopilados: {json.dumps(item.get('atributos_recolectados', {}), ensure_ascii=False)}
Contexto de mercado: {item.get('market_context', '')}

Candidatos UNSPSC recuperados de la base de datos:
{cand_str}

# REGLAS DE OPERACIÓN (EJECUCIÓN ESTRICTA EN 5 FASES)

Fase 1: Normalización y Auto-Contexto
- Analiza la descripción completa. Aísla el producto central, pero EVALÚA LOS ATRIBUTOS (ej. procesador i9, monitor, voltaje, tipo de material) que lo acompañan.
- LEY DE LA MÁQUINA DESTINO: Si la descripción original del usuario ya menciona explícitamente el sistema, máquina, equipo o aplicación destino (ej: "para faja transportadora", "para aire acondicionado", "de camión", "para repuesto de"), TIENES ESTRICTAMENTE PROHIBIDO preguntar por la industria en la Fase 3. Debes asumir ese contexto como válido y saltar directo a la Fase 4 para dar el código.
- LEY DE SERVICIOS E INTANGIBLES: Los servicios generales, software, licencias, suscripciones o alojamiento en la nube (ej: "Licencia de software", "Cloud hosting", "Servidor en la nube", "Suscripción mensual", "Servicio de consultoría") mantienen el mismo código UNSPSC sin importar qué industria los compre. Si detectas un servicio o bien intangible de TI o software, NO PREGUNTES por la industria del usuario. Clasifícalo directamente en los segmentos correspondientes (ej. 43 u 81).
- Si los atributos, accesorios o palabras clave presentes en la descripción original ya determinan claramente a qué industria pertenece el producto (Ej: "Estación de trabajo" + "i9, monitor" = Claramente TI / "Válvula" + "cardíaca" = Claramente Médico / "Tubo" + "acero 304" = Claramente Industrial/Mecánica), debes absorber ese contexto automáticamente.

Fase 2: Gatekeeper de Ambigüedad (Filtro Crítico)
- Evalúa el término central junto con su auto-contexto.
- ¿El producto, incluso considerando sus atributos y accesorios, sigue perteneciendo ambiguamente a más de una industria?
- REGLA DE CEGUERA TEMPORAL (BLIND SPOT):
  Durante la Fase 2, TIENES ESTRICTAMENTE PROHIBIDO buscar mentalmente el producto en el catálogo UNSPSC. Tu única tarea en esta fase es hacer una "lluvia de ideas" de escenarios: ¿Este ítem con sus atributos actuales lo usaría un oficinista de TI, un médico, un mecánico o un ingeniero de planta? Si la respuesta es claramente solo UNO (ej: Estación de trabajo i9 con monitor = TI), NO es ambiguo.
- APLICA LA LEY DE LA MÁQUINA DESTINO Y LEY DE SERVICIOS: Si el producto tiene máquina destino explícita o es un servicio/software intangible, NUNCA es ambiguo.
- Si la respuesta es SÍ (sigue siendo ambiguo entre industrias distintas, como un "sensor" genérico sin máquina ni aplicación definida): Pasa a la Fase 3 (Pregunta al usuario).
- Si la respuesta es NO (los atributos, la máquina destino o el tipo intangible ya lo ubicaron en una categoría clara): SALTA la Fase 3 e ir DIRECTO a la Fase 4.

Fase 3: Bifurcación y Web UI (Desambiguación)
- Si determinaste que sigue siendo ambiguo en la Fase 2, formula una pregunta clara solicitando ÚNICAMENTE la industria o aplicación final.
- REGLA ESTRICTA: NUNCA pidas marcas, números de parte ni especificaciones dimensionales. Enfócate solo en resolver la ambigüedad de aplicación.
- Proporciona entre 2 y 4 opciones estructuradas de aplicación.

Fase 4: Mapeo Semántico
- Selecciona la clase exacta UNSPSC (8 dígitos) correspondiente al producto y su auto-contexto.

Fase 5: Validación y Cierre
- Si el contexto fue resuelto (por auto-contexto o por el usuario), asigna el candidato de la lista (`indice_seleccionado` de 1 a 8) y establece `confianza` en "Alta".
- Si es ambiguo, establece `confianza` en "Ambigüedad" e `indice_seleccionado` en null.

REGLA CRÍTICA: Tu salida debe ser ÚNICA Y EXCLUSIVAMENTE un objeto JSON válido. Cero texto adicional, cero formato markdown.
Responde ÚNICAMENTE con un objeto JSON en este formato:
{{
    "indice_seleccionado": 1 | null,
    "confianza": "Alta" | "Ambigüedad",
    "sustantivo_principal": "SUSTANTIVO",
    "pregunta": "Pregunta clara de desambiguación pidiendo industria o aplicación final",
    "opciones": [
        {{
            "titulo": "Opción 1 (Ej: Uso Industrial / Medición de procesos)",
            "descripcion": "Ejemplo claro de aplicación"
        }},
        {{
            "titulo": "Opción 2 (Ej: Uso Médico / Diagnóstico y salud)",
            "descripcion": "Ejemplo claro de aplicación"
        }}
    ]
}}
"""
