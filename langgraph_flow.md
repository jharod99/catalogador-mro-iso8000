# Flujo del Agente LangGraph — Chat Bot UNSPSC Paramétrico

Este diagrama representa el flujo completo y detallado del agente con el nuevo sistema de indagación de atributos paramétricos para compras MRO industriales.

```mermaid
graph TD
    %% Estilos de Nodos
    classDef startEnd fill:#111827,stroke:#6B7280,stroke-width:2px,color:#F3F4F6;
    classDef nodeStyle fill:#1F2937,stroke:#3B82F6,stroke-width:1px,color:#F3F4F6;
    classDef decisionStyle fill:#374151,stroke:#F59E0B,stroke-width:1.5px,color:#F3F4F6;
    classDef condStyle fill:#111827,stroke:#3b82f6,stroke-width:1px,color:#F3F4F6;

    Start([Inicio: Historial del Chat]):::startEnd --> Extractor[1. Extractor Node <br/> Groq Llama 3]:::nodeStyle
    
    Extractor -->|Extrae sustantivo_principal obligando llaves de la matriz y determina requiere_busqueda_web| CheckSearch{¿Requiere búsqueda web?}:::condStyle
    
    CheckSearch -->|Sí| Verifier[2. Verifier Node <br/> DDG Search + caché]:::nodeStyle
    CheckSearch -->|No / Genérico| Retriever[3. Retriever Node <br/> FAISS + Búsqueda Léxica]:::nodeStyle
    
    Verifier -->|Contexto de internet y marcas reales| Retriever
    
    Retriever -->|Candidatos UNSPSC| Decision[4. Decision Maker <br/> Claude 3.5 Sonnet / fallbacks]:::decisionStyle
    
    Decision --> CheckMatrix{¿Sustantivo en Matrix?}:::condStyle
    
    CheckMatrix -->|Sí| CheckParams{¿Tiene todos los obligatorios y coherentes?}:::condStyle
    CheckMatrix -->|No| CheckConfidence{¿Confianza RAG > 85%?}:::condStyle
    
    CheckParams -->|Falta >= 1 campo o incoherente| Ambiguity[Confianza: Ambigüedad <br/> Llena atributos_faltantes]:::nodeStyle
    CheckParams -->|Completo y Coherente| CheckConfidence
    
    CheckConfidence -->|Sí / Alta| Generator[5. Generator Node <br/> Estandarización ISO 8000]:::nodeStyle
    CheckConfidence -->|No / Baja / Ambigüedad| End([Fin: Retornar JSON con Parámetros y Pregunta]):::startEnd
    
    Ambiguity --> End
    Generator -->|Línea descriptiva estandarizada| End
```

## Descripción de Nodos y Nuevas Lógicas

| Nodo | Rol / Tecnología | Detalle de la Refactorización |
|---|---|---|
| `Start` | Entrada de Historial | Recibe los turnos conversacionales completos desde SQLite. |
| **extractor** | Groq (Llama-3.3 70B) | Mapea la jerga del usuario. **Salvaguarda de Normalización:** Se inyectan las llaves exactas de `MATRIZ_ATRIBUTOS_MRO` para forzar a que use el sustantivo exacto de la familia. Determina el flag `requiere_busqueda_web` (booleano) para discernir si es genérico o requiere conectarse a internet. |
| **verifier** | DuckDuckGo Search API | Busca fichas técnicas en internet para resolver marcas específicas y modelos. **Atajo de Latencia:** Si `requiere_busqueda_web` es `false`, se salta esta búsqueda para ahorrar tiempo. |
| **retriever** | FAISS + Léxica local | Encuentra los 8 candidatos UNSPSC más cercanos combinando distancias vectoriales y coincidencia por palabras clave. |
| **decision_maker** | Claude 3.5 / Llama / fallbacks | Realiza la **auditoría de atributos críticos**: <br/>• Cruza TAGs de instrumentación con el contexto de DuckDuckGo para inferir el equipo.<br/>• Auto-aprueba materiales técnicos si detecta siglas (`HDPE`, `PVC`, `PTFE`, `INOX`).<br/>• **Validación de Coherencia:** Comprueba que los valores provistos en `atributos_recolectados` sean técnicamente lógicos (si son absurdos, los considera como faltantes).<br/>• Si faltan campos obligatorios o incoherentes, asigna `"Ambigüedad"` y rellena `atributos_faltantes`. |
| **generator** | Groq (Llama-3.3 70B) | Redacta la descripción técnica normalizada en una línea bajo el estándar ISO 8000. |
| `End` | Salida JSON | Devuelve la clasificación final o el listado de parámetros recolectados y faltantes para renderizar el formulario en el frontend. |

## Auditoría de Atributos de la Matriz MRO

Si el `sustantivo_principal` coincide con alguno de la matriz, se exigen los siguientes campos:

*   **TUBERIA**: `material`, `diametro`, `sdr_o_cedula`, `presion_o_norma`.
*   **MUELA**: `tipo_muela_movil_o_fija`, `dimensiones_chancadora`, `material_o_manganeso`, `marca_equipo_destino`.
*   **MEMORIA**: `capacidad_gb`, `tecnologia_ddr`, `compatibilidad_equipo`.
*   **MANDIL**: `material_o_proteccion`, `talla`, `color`.
*   **INTERRUPTOR**: `tipo_de_contacto`, `aplicacion_o_tecnologia`, `tag_o_numero_parte`.
*   **LAPTOP**: `procesador`, `memoria_ram`, `almacenamiento_ssd`.
*   **CELULAR**: `almacenamiento`, `color`.

