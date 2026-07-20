import json

def get_extractor_prompt(chat_history: str, llaves_matriz: str) -> str:
    return f"""
Actúa como un Ingeniero de Compras MRO (Mantenimiento, Reparación y Operaciones).
Analiza el siguiente historial de chat y extrae TODOS los ítems individuales a cotizar.

REGLAS ESTRICTAS:
1. Si un texto tiene UN SOLO número de parte (NP, P/N, modelo) o se describe como un solo producto con múltiples atributos separados por comas, es UN SOLO ÍTEM. NO lo separes.
2. Identifica y **FILTRA/ELIMINA** etiquetas administrativas, prefijos de inventario, códigos de contabilidad internos, descripciones de procesos contables o volumen de compra/conteo (ej: "ACTIVO-FIJO-DIVER", "INV-", "AF-", "SOLICITUD DE COMPRA", "10 unidades a comprar", "5 piezas de repuesto", "1000M de cable total a pedir") que no representen la especificación técnica del producto. **NOTA CRÍTICA:** NO elimines especificaciones de longitud unitaria de tramos o dimensiones físicas del producto (ej: "tramos de 6 metros", "longitud de 6m", "tramos de 12 metros", "cable de 1.5 metros", "espesor de 5mm"). Estas dimensiones unitarias son atributos técnicos indispensables y DEBEN mantenerse en 'original_query' y ser extraídas en 'atributos_recolectados'.
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
13. Classifica la consulta en una 'categoria_dominio' basada en su naturaleza física/industrial:
    - 'MECANICA': ÚNICAMENTE para tuberías, válvulas, bridas, codos, conexiones, acoples, juntas, sellos, adaptadores. Cualquier otro producto mecánico (rodamientos, pernos sueltos, muelas, herramientas) clasifícalo como 'FUERA_DE_ALCANCE'.
    - 'TI': ÚNICAMENTE para celulares, auríulares, laptops, servidores, computadoras, memorias RAM, discos de almacenamiento. Cualquier otra cosa clasifícalo como 'FUERA_DE_ALCANCE'.
    - 'ELECTRICA': ÚNICAMENTE para motores eléctricos, interruptores, cables eléctricos, sensores, transmisores industriales, caudalímetros. Cualquier otra cosa clasifícalo como 'FUERA_DE_ALCANCE'.
    - 'FUERA_DE_ALCANCE': para cualquier otro producto que no encaje en las familias especializadas permitidas.
14. **IGNORAR CANTIDADES O VOLUMEN (CRÍTICO):** Identifica y elimina del flujo de catalogación las cantidades totales a comprar o el volumen solicitado para la transacción (ej. si piden "10 unidades de rodamiento" o "quiero pedir 1000 metros de cable", debes ignorar el "10" o "1000" para la transacción y conservar únicamente el sustantivo). **NOTA CRÍTICA:** Esto aplica solo a la cantidad del pedido. NUNCA ignores ni elimines la longitud unitaria de tramos del producto o dimensiones físicas del material (ej: "tramos de 6 metros", "longitud 12m", "cable de 1.5m"), ya que son parte indisoluble de la descripción técnica y no un volumen de compra. NUNCA guardes cantidades numéricas de compra ni las pases a 'atributos_recolectados'."metro" si aplica). NUNCA guardes cantidades numéricas ni las pases a 'atributos_recolectados'.

Historial de chat:
{chat_history}

Responde ÚNICAMENTE con un JSON en formato de array:
[
  {{
    "original_query": "Nombre descriptivo corregido + Marca + Modelo + Material + NP/PN (sin etiquetas contables y preservando el TAG ISA)", 
    "expanded_queries": ["sinonimo_tecnico_1", "sinonimo_tecnico_2", "sinonimo_tecnico_3"],
    "sustantivo_principal": "SUSTANTIVO_PRINCIPAL_MAPEADO",
    "requiere_busqueda_web": true,
    "categoria_dominio": "MECANICA" | "TI" | "ELECTRICA" | "FUERA_DE_ALCANCE",
    "atributos_recolectados": {{"clave": "valor", ...}}
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
Actúa como un Especialista en Clasificación UNSPSC de suministros industriales, mineros y tecnológicos y un Auditor de Compras MRO estricto.
Debes asignar el código correcto al siguiente requerimiento y auditar los atributos técnicos requeridos.

Requerimiento: "{item['original_query']}"
Sustantivo Principal actual: "{item.get('sustantivo_principal', '')}"
Atributos Recolectados hasta ahora: {json.dumps(item.get('atributos_recolectados', {}), ensure_ascii=False)}
Contexto de internet (Crucial para marcas específicas y TAGs de instrumentación): {item.get('market_context', '')}

Candidatos UNSPSC recuperados de la base de datos:
{cand_str}

REGLAS DE AUDITORÍA (AUDITORÍA DINÁMICA DE CATALOGACIÓN ISO 8000):
Eres un auditor experto en catalogación ISO 8000 y compras técnicas MRO. En lugar de usar una matriz de atributos fija, debes DEDUCIR dinámicamente de 3 a 5 atributos técnicos OBLIGATORIOS (ej: Dimensiones, Diámetro, Capacidades, Materiales, Voltajes, Normas, etc.) necesarios para adquirir este artículo específico en el mercado industrial de forma exitosa.

Tus tareas y REGLAS CRÍTICAS de auditoría (Filtro Duro):
1. **Deducción de Atributos Críticos**: Analiza el 'sustantivo_principal' y el mejor candidato UNSPSC. DEDUCE automáticamente de 3 a 5 atributos técnicos indispensables para realizar la compra de ese ítem. Por ejemplo:
   - Para TUBERIAS: diámetro, material, sdr_o_cedula, presion_o_norma.
   - Para AURICULARES/CELULARES: capacidad/almacenamiento, color. (NOTA: NUNCA solicites sistema operativo ni marca/modelo para teléfonos celulares si ya se especificó un modelo como Poco, iPhone, etc., ya que son fijos y predefinidos. Adicionalmente, las opciones que sugieras en 'atributos_faltantes' para marcas y modelos conocidos DEBEN corresponder estrictamente a las especificaciones comerciales reales del fabricante para ese modelo exacto de lanzamiento: para Samsung S26 solo existen capacidades de "256GB" y "512GB", y colores "Blanco", "Negro", "Violeta Cobalto" y "Azul Cielo"; para Poco X7 Pro o iPhone 17 usa sus opciones reales. No inventes opciones genéricas o inválidas).
   - Para MOTORES: potencia, voltaje, rpm, fases.
   - Para MEMORIAS RAM: capacidad, tecnología (DDR3/4/5), compatibilidad.
   - Para CAUDALIMETROS/FLUJOMETROS/SENSORES DE FLUJO: tecnología de medición, diámetro nominal, tipo de conexión, recubrimiento interno (liner), material de electrodos, señal de salida, alimentación eléctrica.
2. **Regla 1 (La Ley de la Marca - OBLIGATORIA):** Si el requerimiento original del usuario o el historial menciona CUALQUIER MARCA comercial (ej: Huawei, Apple, Lenovo, Caterpillar, SKF, Demtech, etc.), el atributo `modelo_exacto` o `numero_de_parte` se vuelve un campo OBLIGATORIO. Si falta o no está en 'atributos_recolectados', la confianza del ítem DEBE ser 'Ambigüedad' y debes pedirle en la 'pregunta' que busque esa información en el manual o placa del equipo.
3. **Regla 2 (Ensamble vs. Componente):** Revisa con cuidado la `ruta_jerarquica` de los candidatos UNSPSC de FAISS. Si el usuario solicita un equipo completo o producto final (ej: "Auriculares", "Bomba", "Motor", "Celular") y el mejor candidato de FAISS tiene descrita una ruta de partes o accesorios (ej: "Partes o accesorios de...", "Accesorios de..."), DEBES invalidar ese candidato (seleccionar null), bajar la confianza a 'Ambigüedad' y preguntar al usuario: "¿Busca el equipo completo o un repuesto para el mismo?"
4. **Regla 3 (Estándares Comerciales):** Si el usuario proporciona dimensiones o magnitudes técnicas (ej: diámetros de tuberías, voltajes de memorias, pesos de muelas, etc.), usa tu conocimiento base para validar si existe como estándar comercial. (Ej: en tuberías, un diámetro de 35\" no es estándar comercial habitual, pero 36\" sí lo es). Si es un valor atípico o no comercial, pasa a 'Ambigüedad' e indica en la 'pregunta': "El valor ingresado no coincide con un estándar comercial habitual. Por favor confirme el dato técnico."
5. **Regla 4 (Filtro Duro - Hard Gate):** No hay bypass ni excepciones. Si el usuario ya proporcionó un número de parte (Part Number / P/N / Código de fabricante) o modelo exacto unívoco de fabricante (ej: "83CV00FSLM", "SS-43GXS4", "W2S130-AA03-01"), NO debes solicitar ningún otro atributo técnico adicional (como tamaño de pantalla, disco, refrigeración, color, etc.), ya que el P/N define físicamente el producto por completo. En ese caso, 'atributos_faltantes' debe estar vacío y la confianza debe ser 'Alta'. Solo solicita atributos adicionales si el modelo provisto es general o una serie con variaciones comerciales (ej: "iPhone 15", "Samsung S26", "Legion Pro"). Si falta un campo obligatorio y no hay P/N unívoco, la confianza DEBE ser 'Ambigüedad' y debes generar dinámicamente en 'atributos_faltantes' la lista de los campos técnicos que faltan, asignando el tipo_interfaz ('botones' con opciones estándar comerciales o 'texto' con un placeholder) de forma lógica basándote en tu conocimiento del mercado industrial, y redactar una 'pregunta' que indique cortés y directamente qué información exacta falta para poder proceder.
5b. **Regla 4b (P/N Primero - Flujo Inverso):** Si el usuario proporciona directamente un número de parte o código de fabricante al inicio de la conversación (ej: "IFM4080K", "8705TSA1N0", "83CV00FSLM"), el sistema debe extraer todos los atributos técnicos a partir de ese código usando su conocimiento base y/o el contexto de internet. NO solicites atributos que ya están definidos por el P/N. Este es el flujo más eficiente: P/N → extracción automática de atributos → clasificación directa.
5c. **Regla 5 (Coherencia Norma-Material - CRÍTICO):** Cuando debas pedir la norma de fabricación del cuerpo ('norma_fabricacion_cuerpo') de un equipo o instrumento, las opciones que ofrezcas DEBEN ser coherentes con el material de cuerpo ya declarado en 'atributos_recolectados'. Ejemplos de alineación obligatoria:
   - Si el material del cuerpo es "acero al carbono" o "CS": ofrece ÚNICAMENTE normas como ASTM A105 (forjado), ASTM A216 WCB (fundido), ASTM A234 WPB (soldado), ASTM A106 Gr.B (tubería). NUNCA ofrezcas ASTM A182 F316, DIN 1.4404, 316L ni normas de inoxidable o aleaciones.
   - Si el material del cuerpo es "acero inoxidable" o "INOX" o "316L": ofrece ÚNICAMENTE normas como ASTM A182 F316/F304, DIN 1.4404, ASTM A351 CF8M.
   - Si el material del cuerpo es "hierro fundido" o "fierro fundido" o "FF": ofrece ÚNICAMENTE normas como ASTM A126 Cl.B, ASTM A48 Cl.40, EN-GJL-250.
   Si el material ya está declarado, jamás ofrezcas normas incompatibles con ese material.
5d. **Regla 6 (Caudalímetro: Canal Cerrado vs. Canal Abierto - CRÍTICO):** Para CAUDALIMETROS/FLUJOMETROS, la diferencia entre canal cerrado y canal abierto es fundamental. NUNCA clasifiques un caudalímetro con conexiones bridadas (ANSI, DIN, PN) o roscadas como "canal abierto". Las reglas son:
   - Si el texto menciona "conexiones bridadas", "bridado", "ANSI Clase", "PN16", "extremos bridados", "instalación en tubería a presión": el equipo es de CANAL CERRADO (full-bore o insertion). Busca candidatos UNSPSC del tipo "Medidor de flujo electromagnético de tubería" o "Flujómetro electromagnetic de conducto cerrado".
   - Si el texto menciona "canal abierto", "vertedero", "canaleta Parshall", "río", "zanja", "acequia": el equipo es de CANAL ABIERTO (open channel).
   - La tecnología electromagnética (Faraday) SIEMPRE opera en conducto cerrado y lleno de fluido. Jamás la clasifiques como canal abierto.
6. **Alineación de Atributos**: Si el usuario proporciona datos técnicos en su mensaje o historial, compáralos con tus atributos deducidos.
   - APROBACIÓN AUTOMÁTICA DE MATERIAL: Si el requerimiento del usuario incluye siglas técnicas de materiales conocidas (ej: HDPE, PVC, PTFE, PU, INOX, ASTM, ASTM A105, etc.), debes dar por aprobado el parámetro de material automáticamente y guardarlo en 'atributos_recolectados'.
   - CRUCE DE TAGS: Si el usuario ingresa un TAG de instrumentación (ej: 47-130-LSL-034), crúzalo con el 'Contexto de internet' para inferir a qué equipo o sistema pertenece.
7. Evalúa la COHERENCIA técnica:
   - **COHERENCIA TÉCNICA (CRÍTICO):** No basta con que el usuario envíe un dato; debes validar que el dato tenga sentido físico o industrial (ej: una tubería no puede ser de "madera", un SDR no puede ser "900", un diámetro de tubería no puede ser "100 PLG"). Si el dato es absurdo o físicamente imposible para el tipo de ítem, considéralo como FALTANTE y establece la confianza en "Ambigüedad", detallando el error técnico en la 'pregunta'.
   - Valida que los valores provistos en 'atributos_recolectados' sean lógicamente correctos y compatibles. Si un valor es incoherente, considéralo como FALTANTE.
   - **MÉTRICA VS IMPERIAL (CRÍTICO):** NUNCA conviertas automáticamente pulgadas a milímetros en 'atributos_recolectados' (ej: si el usuario pide 7/8IN, guarda "7/8 PLG" o "7/8IN", NUNCA "M16" o "M22.225"). Mantén el sistema de medición del usuario original.
   - **SISTEMA OPERATIVO EN TELÉFONOS (CRÍTICO):** NUNCA solicites el sistema operativo, versión o marca para teléfonos celulares o smartphones (ej: Poco, iPhone, Xiaomi, Samsung, etc.), ya que viene predeterminado de fábrica por el modelo. Esto aplica tanto para atributos deducidos como faltantes.
   - **LÍMITE Y RELEVANCIA COMERCIAL (FILTRO DE FRICCIÓN INFINITA - CRÍTICO):** NUNCA solicites especificaciones de diseño interno, características secundarias o detalles físicos que no afecten directamente la compatibilidad comercial estándar y la compra del artículo.
     1. Para CÓMPUTO/TI (celulares, audífonos, laptops, memorias): Si el usuario ya proporcionó una marca y un modelo (ej: "Kingston NV2", "Poco X7 Pro", "Sony WH-1000XM4"), NO solicites atributos adicionales que vienen definidos de fábrica (como frecuencia de respuesta de sonido, tipo de micrófono, material de almohadillas, tipo de chip Bluetooth, etc.). Solo pregunta por capacidad (RAM/Almacenamiento) y color si no están claros. Si se da un P/N (ej: "SNV2S/1000G"), no pidas NADA más.
     2. Para MECÁNICA (tuberías, válvulas): Limítate a: diámetro, material del cuerpo, clase de presión (cédula/rating), y tipo de conexión. Queda prohibido preguntar por tratamientos térmicos adicionales, pruebas de laboratorio o tolerancias milimétricas a menos que sea una aplicación crítica.
     3. Para ELÉCTRICA (motores, cables): Limítate a: potencia (HP/kW), velocidad nominal (RPM), voltaje, y tipo de montaje. Queda prohibido preguntar por detalles secundarios del rotor o rodamientos internos si ya se especificaron la marca y el tipo básico.
   - **COMPATIBILIDAD Y COHERENCIA DE HARDWARE DE ALTO RENDIMIENTO (CRÍTICO):** Si el producto es una laptop/computadora y cuenta con hardware de gama extrema (ej: procesadores Intel Core i9-13900HX/14900HX, AMD Ryzen 9, Intel Core Ultra 9, y tarjetas gráficas dedicadas NVIDIA RTX 4080/4090):
     1. El tamaño de pantalla sugerido en 'atributos_faltantes' DEBE limitarse a tamaños físicamente viables para disipar dicho calor (únicamente 16" o 18"). Queda prohibido ofrecer opciones de chasis pequeños (como 14" o menores), ya que son físicamente incompatibles con la refrigeración requerida por estos chips.
     2. El sistema de refrigeración sugerido en 'atributos_faltantes' debe ser de alto rendimiento (ej: Vapor Chamber o Refrigeración Líquida). Queda prohibido ofrecer "Doble ventilador" estándar o básico, que solo es para gamas de entrada.
     3. El tipo de panel de pantalla para estas gamas extremas (ej: Lenovo Legion Pro 7i/9i) solo debe incluir tecnologías premium reales (Mini-LED, IPS de alta gama, OLED). Queda estrictamente prohibido sugerir paneles de baja gama como "VA" o "TN".
     4. Si el usuario ya especificó un dato técnico como la resolución exacta (ej: 3,2K, 4K, 3840x2400) o frecuencia (ej: 165Hz, 240Hz), NO lo ignores ni vuelvas a preguntar por él. Úsalo para deducir o validar los demás campos (ej: si es una resolución de 3840x2400 en Lenovo Legion, esta corresponde exclusivamente a la Legion 9i Gen 10 de 18" con procesador Core Ultra 9, y no a la Legion Pro 7i Gen 9 de 16" con i9-14900HX). Realiza un cruce de compatibilidad estricto entre el procesador, resolución de pantalla, tamaño del chasis y gráfica antes de sugerir opciones.
     5. **CONTRADICCIONES Y COMPATIBILIDAD COMERCIAL (CRÍTICO):** Si el usuario proporciona combinaciones de componentes que comercial o físicamente no existen juntos (ej: procesador Intel Core i9-14900HX con una pantalla de resolución 3840x2400, ya que el i9-14900HX viene con pantalla de 3.2K/3200x2000 de 16", y la resolución 3840x2400 pertenece a la Legion 9i de 18" con Core Ultra 9):
        - DEBES marcar la confianza en 'Ambigüedad'.
        - En 'pregunta', debes explicar clara y cortésmente la contradicción técnica/comercial y consultar al usuario qué especificación desea corregir o mantener (ej: 'El procesador i9-14900HX se comercializa con pantalla de 3.2K (3200x2000) en 16", mientras que la resolución 3840x2400 corresponde a pantallas de 18" con Intel Core Ultra 9. Confirme cuál desea mantener.').
        - Considera como faltante o dudoso el atributo contradictorio para que pueda ser corregido.
   - **COMPATIBILIDAD FÍSICA:** Asegura que todos los componentes recolectados en el mismo ítem sean físicamente compatibles.
   - Si falta uno o más campos obligatorios deducidos (o son incoherentes/absurdos), la confianza DEBE ser "Ambigüedad", debes listar los campos faltantes estructurados en 'atributos_faltantes' y redactar una 'pregunta' técnica, directa, y extremadamente concisa (sin rodeos, sin saludos, y sin repetir el nombre o descripción del producto).
   - **REGLA DE FORMATO Y CONCISIÓN:** 
     1. La 'pregunta' NO debe contener el nombre ni el sustantivo del producto.
     2. NUNCA uses marcado de negrita markdown (`**`) para resaltar términos. Si deseas destacar algo, usa comillas dobles normales (`"`).
   - Si no falta ningún campo obligatorio deducido y hay suficiente información para clasificar con alta confianza, la confianza debe ser "Alta" y debes seleccionar el 'indice_seleccionado' (1 a 8) del candidato más apto.
8. Analiza la criticidad:
   - Si detectas fluidos peligrosos (ácido, cianuro, relaves), altas presiones (ej: >150 PSI, cédula alta, alta presión), o componentes de izaje/cargas pesadas, la criticidad debe ser "Alta". De lo contrario, "Media" o "Baja".

Responde ÚNICAMENTE con un JSON con la siguiente estructura (sin comillas invertidas ni bloques markdown):
{{
    "indice_seleccionado": (número del 1 al 8, o null),
    "confianza": "Alta" | "Ambigüedad" | "Baja",
    "pregunta": "Tu pregunta aclaratoria técnica si aplica, o vacío si no (sin usar ** para resaltar)",
    "sustantivo_principal": "Sustantivo en mayúsculas",
    "atributos_recolectados": {{"clave": "valor", ...}},
    "atributos_faltantes": [
        {{
            "atributo": "nombre_del_atributo",
            "tipo_interfaz": "botones" | "texto",
            "opciones": ["Opción 1", "Opción 2", ...] o null,
            "placeholder": "Texto del placeholder..." o null
        }}
    ],
    "criticidad": "Alta" | "Media" | "Baja"
}}
"""

def get_generator_prompt(item: dict, nom: str, attrs: dict) -> str:
    return f"""
Actúa como un Especialista en Catalogación MRO (Mantenimiento, Reparación y Operaciones) bajo el estándar ISO 8000.
Tu tarea es tomar el requerimiento original y sus atributos técnicos recolectados para redactar una descripción técnica estandarizada en UNA SOLA LÍNEA para el maestro de artículos.

REGLAS ESTRICTAS DE ESTRUCTURA (Sustantivo + Modificadores):
1. FORMATO EXACTO: [SUSTANTIVO PRINCIPAL] [ADJETIVO/TIPO], [MEDIDAS/CAPACIDAD], [CLASE DE PRESIÓN], [TIPO DE CONEXIÓN], [MATERIAL DEL CUERPO], [MATERIAL INTERNO/DISCO/ASIENTO], [ACCIONAMIENTO], [MARCA], [P/N o MODELO].
2. ELIMINA CONECTORES INNECESARIOS: Prohibido usar artículos (el, la, los, las) y palabras redundantes (repuesto, accesorio, suministro, equipo). **EXCEPCIONES PERMITIDAS:**
   - "CON" se permite para describir elementos acompañantes en kits o ensambles (ej: "ESPARRAGO, ..., CON 2 TUERCAS ..., 2 ARANDELAS ...") y para accionamientos (ej: "CON VOLANTE", "CON ACTUADOR NEUMÁTICO").
   - "TIPO" se permite como prefijo de conexión o configuración (ej: "TIPO LUG", "TIPO WAFER").
   - "CUERPO" y "DISCO" se permiten como prefijos de material cuando hay múltiples materiales que diferenciar (ej: "CUERPO FIERRO FUNDIDO, DISCO ACERO INOX").
3. SUSTANTIVO PRIMERO: Inicia siempre con el nombre exacto del objeto (Ej: RODAMIENTO, VALVULA, CUÑA, MOTOR, ESPARRAGO, SOCKOLET, WELDOLET, THREADOLET, CODO). Nunca inicies con la marca. NUNCA alteres o abrevies de forma incorrecta fittings de derivación específicos (como SOCKOLET, WELDOLET, THREADOLET) a términos genéricos como "SOCKET" o similares. Mantén la denominación exacta ingresada por el usuario.
4. ABREVIATURAS DE UNIDADES Y ESPACIADO: Usa formato industrial estándar (V en lugar de voltios, MM en lugar de milímetros, IN en lugar de pulgadas, HP, KG). 
   - **REGLA DE ORO 1 (PULGADAS):** Usa siempre "IN" en lugar de comillas dobles (") o comillas simples (') para las pulgadas (ej: escribe "7/8 IN" y no "7/8\"" ni "7/8'"). Las comillas dobles rompen cargas masivas en ERPs (como CSV) y no deben usarse.
   - **REGLA DE ORO 2 (ESPACIADO):** Separa siempre con espacios las unidades de los números y los operadores de dimensión "X" (ej. de "16IN X 3IN" o "16x3" a "16 IN X 3 IN").
5. SEPARADORES: Usa únicamente comas (,) seguidas de un espacio para separar los atributos.
6. MAYÚSCULAS: Devuelve absolutamente toda la descripción en MAYÚSCULAS.
7. CORRECCIÓN Y NORMALIZACIÓN DE UNIDADES: 
   - NO conviertas medidas en pulgadas (IN, PLG, ", ') a milímetros (MM) usando cálculos matemáticos exactos a menos que sea explícitamente requerido. Mantén el sistema de medición original del usuario (ej. si pide 7/8IN, usa 7/8 IN, NUNCA uses M16 o M22.225 ni digas que es "MÉTRICO" si el original es en pulgadas).
8. COHERENCIA FÍSICA Y DIMENSIONAL (CRÍTICO): Asegura la compatibilidad de todos los elementos del ensamblaje. Si un espárrago mide 7/8 IN de diámetro, sus tuercas y arandelas asociadas DEBEN ser de 7/8 IN de rosca (físicamente compatibles). NUNCA mezcles diámetros (como espárrago de 7/8 IN con tuercas M16).
9. PRECISIÓN GEOMÉTRICA (CRÍTICO): Un espárrago (ESPARRAGO) es una varilla sin cabeza. NUNCA lo adjetives como "ESPARRAGO HEXAGONAL" (la cabeza hexagonal no existe en espárragos). Las tuercas del ensamble sí son hexagonales (TUERCA HEX o TUERCA HEXAGONAL), pero el espárrago en sí no lo es.
10. EVITA REDUNDANCIAS (CRÍTICO): Si una norma, grado o estándar ya define la composición del material (ej: la especificación ASTM A193 Grado B7 ya implica acero de aleación AISI 4140 tratado térmicamente; ASTM A194 Grado 2H ya define tuercas de acero al carbono de alta resistencia; ASTM F436 ya define arandelas planas templadas; ASTM A105 ya define acero al carbono forjado), NO escribas de forma redundante el material crudo (ej: evita escribir "ACERO AISI 4140, GRADO B7 ASTM A193", "ACERO AL CARBONO, GRADO 2H ASTM A194" o "ACERO AL CARBONO ASTM A105", usa simplemente "ASTM A193 GR B7", "ASTM A194 GR 2H" y "ASTM A105" o similares). PERO si el material NO está definido por una norma ASTM/ASME/API específica, SÍ debes escribirlo explícitamente (ej: "CUERPO FIERRO FUNDIDO", "DISCO ACERO INOX").
11. ESTANDARIZACIÓN DE RATING DE PRESIÓN: Estandariza las clases o ratings de presión (ej: cambia "3000 LB", "3000 LIBRAS", "3000#" a "CL3000" o "CLASS 3000"; cambia "150 LB" a "CL150"; cambia "300 LBS" a "CL300"). Junta el prefijo "CL" con el número en una sola cadena sin espacio para evitar que los scripts de carga lo rompan (ej: "CL3000").
12. EXPANSIÓN DE ABREVIATURAS INDUSTRIALES DE CAMPO (CRÍTICO): Expande SIEMPRE las abreviaturas crípticas de materiales y especificaciones de campo a sus nombres completos y legibles. Ejemplos obligatorios:
    - "F°F°" o "FF" (en contexto de materiales de válvulas/bombas) → "FIERRO FUNDIDO"
    - "AC/INOX" o "A.INOX" → "ACERO INOXIDABLE" (o simplemente "ACERO INOX")
    - "AC" (en contexto de materiales) → "ACERO AL CARBONO"
    - "BZ" → "BRONCE"
    - "CI" → "HIERRO FUNDIDO" (Cast Iron)
    - "SS" → "ACERO INOXIDABLE" (Stainless Steel)
    - "CS" → "ACERO AL CARBONO" (Carbon Steel)
    NUNCA dejes abreviaturas crípticas o caracteres especiales (°) sin expandir en la descripción final.
13. PRESERVACIÓN DE ACCIONAMIENTO Y ACTUACIÓN (CRÍTICO): Si el usuario especifica un tipo de accionamiento (volante, palanca, actuador neumático, actuador eléctrico, engranaje, etc.), este dato DEBE aparecer en la descripción final precedido por "CON" (ej: "CON VOLANTE", "CON ACTUADOR NEUMÁTICO", "CON PALANCA"). NUNCA omitas el accionamiento.
14. CONTEXTO POSICIONAL PARA VÁLVULAS Y EQUIPOS CON MÚLTIPLES MATERIALES: Cuando un equipo tiene materiales distintos para diferentes componentes (cuerpo, disco, asiento, vástago, etc.), usa prefijos posicionales para distinguirlos claramente:
    - "CUERPO [MATERIAL]" para el material del cuerpo principal.
    - "DISCO [MATERIAL]" para el material del disco/obturador.
    - "ASIENTO [MATERIAL]" para el material del sello/asiento.
    - "TIPO [CONFIGURACIÓN]" para el tipo de conexión o montaje (ej: "TIPO LUG", "TIPO WAFER", "EXTREMOS BRIDADOS").
15. SUPRESIÓN DE ETIQUETAS REDUNDANTES: Elimina etiquetas como "DISCO:", "MARCA:", "MATERIAL:", "ACCIONAMIENTO:" ya que en una taxonomía posicional separada por comas, estas etiquetas sobran. El orden de los campos ya implica a qué se refiere cada atributo.
17. TAGS DE INSTRUMENTACIÓN (CRÍTICO): NUNCA incluyas identificadores de planta o TAGs de instrumentación (ej: "130-FE-020", "FIT-101", "LT-024") en la descripción técnica final del material. Los TAGs indican la ubicación física en planta, no la especificación del material que debe ser genérico para reemplazo. Elimina cualquier TAG que provenga del requerimiento original.
18. ESTRUCTURA POSICIONAL PARA CAUDALIMETROS (CRÍTICO): Si el sustantivo principal es CAUDALIMETRO, redacta la descripción en el siguiente orden estricto de atributos separados por comas:
    CAUDALIMETRO [TECNOLOGÍA/TIPO], [DIÁMETRO], [TIPO DE CONEXIÓN], [RECUBRIMIENTO INTERNO], [MATERIAL DE ELECTRODOS], [SEÑAL DE SALIDA], [ALIMENTACIÓN], [MARCA], [MODELO].
    Ejemplo: CAUDALIMETRO ELECTROMAGNETICO, 3 IN, BRIDADAS, PTFE, HASTELLOY C, 4-20 MA + HART, 24 VDC, ROSEMOUNT, 8705.
    NUNCA uses la palabra "CON" para la marca (ej: evita escribir "CON ROSEMOUNT", usa simplemente "ROSEMOUNT").
19. NUNCA ALUCINES ATRIBUTOS NO SOLICITADOS: No agregues ratings de presión (ej. CL150), materiales de cuerpo (ej. ACERO INOX), ni accesorios no declarados si el usuario no los especificó explícitamente en el requerimiento original o en los atributos recolectados.
20. ESTRUCTURA POSICIONAL PARA PILAS (CRÍTICO): Si el sustantivo principal es PILA, redacta la descripción en el siguiente orden de atributos separados por comas:
    PILA [TIPO/QUÍMICA], TAMAÑO [TAMAÑO], [VOLTAJE], [PRESENTACIÓN], [MARCA].
    Ejemplo: PILA ALCALINA, TAMAÑO AA, 1.5V, BLISTER CON 2 UNIDADES, DURACELL.
    NUNCA uses la jerga críptica /2, /4 o similares en la descripción final; expándelo obligatoriamente a "BLISTER CON [N] UNIDADES" en el campo de presentación.
21. CONCISIÓN Y SUPRESIÓN DE TEXTO REDUNDANTE EN CÓMPUTO / TI (ISO 8000):
    Para productos de Cómputo/TI (celulares, laptops, computadoras, memorias, discos, etc.):
    - Queda estrictamente PROHIBIDO incluir frases o etiquetas redundantes como "CAPACIDAD DE", "DE ALMACENAMIENTO INTERNO", "DE MEMORIA RAM", "CONECTIVIDAD", "COLOR", "EQUIPO LIBERADO PARA CUALQUIER OPERADOR".
    - El sustantivo para teléfonos móviles/inteligentes debe ser SMARTPHONE o CELULAR.
    - Las capacidades deben ser únicamente el número + unidad (ej: "256 GB", "8 GB RAM", "5G", "NEGRO").
    - Ejemplo correcto: SMARTPHONE SAMSUNG GALAXY A54, 256 GB, 8 GB RAM, 5G, NEGRO.
    - Para LAPTOP: LAPTOP [MARCA] [SERIE/MODELO], PROCESADOR [CPU], [RAM] RAM, [ALMACENAMIENTO], [PANTALLA], [SO].
      Ejemplo: LAPTOP LENOVO THINKPAD E16, CORE I7-13700H, 16 GB RAM, 512 GB SSD, 16 IN, WINDOWS 11 PRO.
22. ESTRUCTURA POSICIONAL PARA TUBERIAS (CRÍTICO): Si el sustantivo principal es TUBERIA, redacta la descripción en el siguiente orden estricto de atributos separados por comas:
    TUBERIA [TIPO/MATERIAL], [DIÁMETRO NOMINAL], [CÉDULA O SDR], [NORMA/GRADO], [EXTREMOS], [LONGITUD TRAMO], [RECUBRIMIENTO].
    Ejemplos:
    - TUBERIA ACERO AL CARBONO SIN COSTURA, 8 IN, SCH 80, ASTM A106 GR B, EXTREMOS BISELADOS, 6 M, RECUBRIMIENTO EPÓXICO.
    - TUBERIA PVC PRESIÓN, 4 IN, SDR 17, ASTM D1785, EXTREMOS LISOS.
    REGLAS:
    - Omite el campo si no fue especificado por el usuario (no alucines datos faltantes).
    - No incluyas textos como "LONGITUD DE TRAMO DE", "CON RECUBRIMIENTO", basta con el dato directo.
    - Si el material ya está definido por una norma ASTM (ej: ASTM A106 GR B define el acero al carbono sin costura), no repitas el material.
23. ESTRUCTURA POSICIONAL PARA VÁLVULAS (CRÍTICO): Si el sustantivo principal es VALVULA, redacta la descripción en el siguiente orden estricto de atributos separados por comas:
    VALVULA [TIPO] [DIÁMETRO], [CLASE DE PRESIÓN], [TIPO DE CONEXIÓN], [MATERIAL CUERPO], [MATERIAL DISCO/OBTURADOR], [MATERIAL ASIENTO], [ACCIONAMIENTO], [NORMA/EXTREMOS], [MARCA], [MODELO/P.N].
    Ejemplos:
    - VALVULA COMPUERTA 6 IN, CL150, BRIDADA, CUERPO ASTM A216 WCB, DISCO ACERO AL CARBONO, ASIENTO LATÓN, CON VOLANTE, API 600.
    - VALVULA MARIPOSA 4 IN, CL150, TIPO WAFER, CUERPO FIERRO FUNDIDO, DISCO ACERO INOX, ASIENTO EPDM, CON PALANCA.
    - VALVULA BOLA 2 IN, CL300, ROSCADA, CUERPO ASTM A105, BOLA ACERO INOX, ASIENTO PTFE, CON PALANCA.
    REGLAS:
    - Usa siempre "CUERPO [MATERIAL]", "DISCO [MATERIAL]" y "ASIENTO [MATERIAL]" como prefijos posicionales.
    - Omite los prefijos solo si el material ya está implícito en la norma (ej: "ASTM A216 WCB" ya define el cuerpo en acero al carbono fundido).
    - NUNCA omitas el tipo de accionamiento si fue especificado (CON VOLANTE, CON PALANCA, CON ACTUADOR NEUMÁTICO, etc.).
24. ESTRUCTURA POSICIONAL PARA MOTORES ELÉCTRICOS (CRÍTICO): Si el sustantivo principal es MOTOR, redacta la descripción en el siguiente orden estricto de atributos separados por comas:
    MOTOR ELÉCTRICO [POTENCIA], [VOLTAJE], [FASES], [VELOCIDAD NOMINAL], [FRECUENCIA], [CARCASA], [PROTECCIÓN IP], [TIPO DE MONTAJE], [NORMA], [MARCA], [MODELO].
    Ejemplos:
    - MOTOR ELÉCTRICO 50 HP, 460 V, TRIFÁSICO, 1746 RPM, 60 HZ, CARCASA NEMA 324T, IP55, MONTAJE B3, NEMA, WEG, W22.
    - MOTOR ELÉCTRICO 15 KW, 380 V, TRIFÁSICO, 1450 RPM, 50 HZ, CARCASA IEC 160L, IP54, MONTAJE B3, IEC.
    REGLAS:
    - Si la potencia está en HP, no la conviertas a KW a menos que el usuario lo especifique.
    - Si no se conoce la marca ni el modelo, omite esos campos (no alucines datos).
    - Usa "TRIFÁSICO" o "MONOFÁSICO" en lugar de "3F" o "1F".
25. ESTRUCTURA POSICIONAL PARA BRIDAS Y FITTINGS (CRÍTICO): Si el sustantivo principal es BRIDA, CODO, TEE, REDUCCIÓN, SOCKOLET, WELDOLET, THREADOLET, NIPLE o similar, redacta en este orden:
    [SUSTANTIVO EXACTO] [TIPO/SERIE], [DIÁMETRO NOMINAL], [CLASE DE PRESIÓN], [TIPO DE CONEXIÓN/CARA], [MATERIAL/NORMA], [MARCA] (si aplica).
    Ejemplos:
    - BRIDA CUELLO DE SOLDADURA, 6 IN, CL150, CARA PLANA, ASTM A105.
    - CODO 90° RADIO LARGO, 2 IN, SCH 40, EXTREMOS BISELADOS, ASTM A234 WPB.
    - SOCKOLET, 2 IN X 3/4 IN, CL3000, ASTM A105.
    - NIPLE ACERO AL CARBONO, 2 IN X 6 IN, SCH 40, ASTM A106 GR B.
26. REGLA GLOBAL DE OMISIÓN INTELIGENTE:
    Para TODAS las familias: si un atributo no fue especificado por el usuario y no es deducible con certeza técnica de los atributos recolectados, simplemente OMÍTELO de la descripción final. NUNCA rellenes con textos como "NO ESPECIFICADO", "N/A", "SIN MARCA" o similares. La descripción debe contener únicamente lo que se sabe con certeza.

Requerimiento original: '{item['original_query']}'
Sustantivo principal sugerido: '{item.get("sustantivo_principal", "")}'
Atributos recolectados: {json.dumps(attrs, ensure_ascii=False)}
Categoría UNSPSC asignada: '{nom}'

Devuelve ÚNICAMENTE la descripción estandarizada, sin saludos, comillas, ni explicaciones adicionales.
"""
