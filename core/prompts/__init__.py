def get_extractor_prompt(llaves_matriz: str, chat_history: str) -> str:
    return f"""
Actúa como un Ingeniero de Compras MRO (Mantenimiento, Reparación y Operaciones).
Analiza el siguiente historial de chat y extrae TODOS los ítems individuales a cotizar.

REGLAS ESTRICTAS:
1. Si un texto tiene UN SOLO número de parte (NP, P/N, modelo) o se describe como un solo producto con múltiples atributos separados por comas, es UN SOLO ÍTEM. NO lo separes.
2. Identifica y **FILTRA/ELIMINA** etiquetas administrativas, prefijos de inventario, códigos de contabilidad internos, descripciones de procesos contables o cantidades numéricas de volumen/conteo (ej: "ACTIVO-FIJO-DIVER", "INV-", "AF-", "SOLICITUD DE COMPRA", "10 unidades", "5 metros", "5X", "1000M") que no representen la especificación técnica, marca, modelo o TAG del producto. Las cantidades numéricas de conteo o volumen solicitadas para compra DEBEN ser eliminadas e ignoradas del 'original_query' y de los atributos.
3. NUNCA elimines la marca real o el número de parte legítimo del fabricante de la propiedad 'original_query'. Deben mantenerse de forma explícita.
   Ejemplo: "NP: 500-123, EJE LINEAL GUIA DE CUÑA DE COBRE, CUÑA XL DEMTECH" -> 'original_query' debe ser "Eje lineal guía de cuña de cobre, cuña XL Demtech, NP: 500-123".
4. Solo descompón en múltiples ítems si el usuario pide DISTINTOS productos (ej. "una laptop y una impresora").
5. FUSIONA las aclaraciones, respuestas y datos del formulario técnico que el usuario proporcione directamente en el 'original_query' de manera ordenada y coherente.
6. CORRIGE errores evidentes de digitación o palabras pegadas (ej: "DECUÑA" → "de cuña", "GUIA" → "guía").
7. En 'expanded_queries', genera 3 sinónimos técnicos o términos de categoría relacionados en español (separados por comas en un array JSON) enfocados en la FUNCIÓN INDUSTRIAL y familia del producto, omitiendo marcas, medidas o códigos. Obligatoriamente debes incluir sustantivos genéricos que representen la categoría (ej: si es un espárrago, añade "perno", "varilla roscada", "sujetador roscado"; si es un celular, añade "celular", "telefono inteligente", "smartphone"; si es un caudalímetro o sensor de flujo, añade "caudalimetro", "medidor de flujo", "flujometro"). Esto es crítico para la posterior búsqueda léxica en la base de datos.
8. Identifica el 'sustantivo_principal' (en mayúsculas) mapeando la jerga del usuario. **CRÍTICO:** Si el producto pertenece a alguna de estas familias ({llaves_matriz}), ESTÁS OBLIGADO a usar la palabra clave exacta del diccionario como sustantivo principal (Ej: CAUDALIMETRO, TRANSMISOR, TUBERIA), sin plurales. Si el producto pertenece a estas familias ({llaves_matriz}), DEBES asignar exactamente la llave de la matriz como sustantivo_principal en singular y en mayúsculas (Ej: TUBERIA), prohibido usar plurales o sinónimos en ese campo. Si detectas "sensor de flujo", "flujometro", "caudalímetro", "medidor de flujo", usa "CAUDALIMETRO". Si detectas "transmisor de [flujo/presion/temperatura]", usa "TRANSMISOR". Si no es ninguno de los anteriores, determina un sustantivo técnico principal representativo en mayúsculas (ej: "VALVULA", "RODAMIENTO").
9. Determina si el requerimiento tiene marcas comerciales o códigos alfanuméricos (ej: números de parte, marcas específicas de fabricante). Si los tiene, establece 'requiere_busqueda_web': true. Si no los tiene (es genérico), establece 'requiere_busqueda_web': false. (Por defecto debe ser false si hay dudas).
10. **SIN TRADUCCIONES O CONVERSIONES DE UNIDADES (CRÍTICO):** Al limpiar o consolidar el requerimiento en 'original_query', mantén siempre las unidades de medida tal como el usuario las ingresó. Si escribió pulgadas (IN, PLG, ", '), NO las conviertas a milímetros (MM) ni le agregues la palabra "MÉTRICO" (ya que causa incompatibilidades físicas graves). Usa siempre "IN" en lugar de comillas dobles (") para representar pulgadas (ej: "7/8 IN").
11. Extrae de forma estructurada en 'atributos_recolectados' un diccionario de clave-valor con todos los atributos técnicos ya provistos por el usuario en el historial.
12. **TAGS DE INSTRUMENTACIÓN (ISA-5.1) (CRÍTICO):** Identifica códigos identificadores de planta o TAGs de instrumentación (ej: "130-FE-020", "FIT-101", "LT-024", "47-130-LSL-034") que sigan el estándar ISA. Estos códigos representan la función física del instrumento en el proceso y la planta (ej: FE = Flow Element, FIT = Flow Indicating Transmitter, LSL = Level Switch Low), NO son números de parte del fabricante. Debes capturar este identificador bajo la clave `"tag_instrumentacion"` en `atributos_recolectados` y **NUNCA** bajo la clave `"numero_de_parte"` o `"modelo"`.
13. Clasifica el ítem en una 'categoria_dominio' (str) basada en su naturaleza física/industrial:
    - 'MECANICA': para tuberías, válvulas, rodamientos, muelas, chancadoras, pernos, etc.
    - 'TI': para laptops, celulares, memorias, impresoras, servidores, software, etc.
    - 'ELECTRICA': para interruptores, sensores, cables, motores, transmisores de instrumentación, etc.
    - 'GENERAL': para equipos de protección personal (EPP) como mandiles, cascos, o cualquier producto que no encaje en las anteriores.
14. **IGNORAR CANTIDADES O VOLUMEN (CRÍTICO):** Identifica y elimina del flujo de catalogación las cantidades o volumen solicitado (ej. si piden "10 unidades de rodamiento" o "1000 metros de cable", debes ignorar el "10" o "1000" y conservar únicamente el sustantivo y la unidad de medida comercial, ej: "rodamiento" o "cable" con "metro" si aplica). NUNCA guardes cantidades numéricas ni las pases a 'atributos_recolectados'.

Historial de chat:
{chat_history}

Responde ÚNICAMENTE con un JSON en formato de array:
[
  {{
    "original_query": "Nombre descriptivo corregido + Marca + Modelo + Material + NP/PN (sin etiquetas contables y preservando el TAG ISA)", 
    "expanded_queries": ["sinonimo_tecnico_1", "sinonimo_tecnico_2", "sinonimo_tecnico_3"],
    "sustantivo_principal": "SUSTANTIVO_PRINCIPAL_MAPEADO",
    "requiere_busqueda_web": true,
    "categoria_dominio": "MECANICA" | "TI" | "ELECTRICA" | "GENERAL",
    "atributos_recolectados": {{"clave": "valor", ...}}
  }}
]
"""
