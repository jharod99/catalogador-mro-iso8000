# Catalogador UNSPSC — Asistente de Clasificación de Compras

Sistema de clasificación semántica multi-agente para requisiciones técnicas de compras y abastecimiento. Toma requerimientos en lenguaje libre, desambigua categorías ambiguas de forma interactiva y asigna el código **UNSPSC** (8 dígitos) de 17,000+ ítems con cobertura universal.

---

## 🗺️ Diagramas del Sistema

### 1. Grafo LangGraph Puro (`core/graph.py`)

Representación del `StateGraph` compilado de LangGraph (`cache` -> `extractor` -> `market_verifier` -> `retriever` -> `decision_maker` -> `END`).

![LangGraph StateGraph puro](docs/langgraph_puro.png)

---

## 2. Flujo Completo del Sistema y Lógica de Nodos

![Flujo completo del sistema](docs/flujo_sistema.png)

---

## ⚙️ Arquitectura Modular

El sistema está orquestado con **LangGraph** y una cascada de múltiples LLMs con fallback automático (`Groq`, `OpenRouter`, `DeepSeek`, `SiliconFlow`, `Mistral`, `Gemini`):

```text
Proyecto Alura/
├── app.py                        # Servidor Flask (API /api/classify)
├── database.py                   # Gestor de base de datos SQLite local
├── golden_record.json            # Caché persistente de respuestas verificadas
├── core/
│   ├── graph.py                  # Grafo de agentes LangGraph
│   ├── state.py                  # Esquemas de datos (AgentState, ProductItem)
│   ├── models.py                 # Cascada de LLMs con fallback automático
│   ├── config.py                 # Sinónimos, reglas léxicas y NOUN_CLASS_MAPPING
│   ├── rag/
│   │   └── faiss_engine.py       # Búsqueda vectorial FAISS + Índice léxico
│   ├── nodes/
│   │   ├── cache.py              # Búsqueda en Golden Record
│   │   ├── extraction.py         # Extractor dinámico y bypass de aclaraciones
│   │   ├── retrieval.py          # Verificador web y RAG FAISS
│   │   └── decision.py           # Gatekeeper de ambigüedad y asignación de código
│   └── prompts/
│       └── templates.py          # Prompts con Leyes de Desambiguación
├── data/                         # Base de datos SQLite + Vectores FAISS (17k UNSPSC)
├── static/ & templates/          # Interfaz de usuario Web (HTML/JS/CSS)
├── Dockerfile & docker-compose.yml
└── run.bat / run.sh
```

---

## 🧠 Leyes y Salvaguardas de Clasificación

| Regla / Ley | Descripción |
|---|---|
| **Regla de Ceguera Temporal (Blind Spot)** | Durante la evaluación de ambigüedad, se prohíbe mirar el catálogo antes de evaluar la lógica de contexto. |
| **Ley de Auto-Contexto** | Si los atributos (ej. *procesador i9*, *monitor 27"*) ya ubican el producto en una industria (ej. TI), se salta la desambiguación y asigna el código en 1 solo paso. |
| **Ley de la Máquina Destino** | Si el usuario menciona la máquina/equipo destino (ej. *para faja transportadora*, *para aire acondicionado*), no se le vuelve a preguntar; se asigna directamente. |
| **Ley de Servicios e Intangibles** | Software, alojamiento cloud, licencias y servicios de TI mantienen su código UNSPSC sin importar la industria compradora. Se clasifican de inmediato. |
| **Bypass Determinista (<5ms)** | Al hacer clic en una opción de la web UI, el sistema invalida los clics dobles y entrega el código UNSPSC exacto instantáneamente sin bucles. |

---

## 🚀 Instalación y Ejecución

### Windows
```cmd
python app.py
```

### Docker
```bash
docker-compose up -d --build
```

---

## 🌐 API

### `POST /api/classify`

```json
// Request
{ "query": "Estación de trabajo con procesador i9, monitor de 27 pulgadas, teclado y mouse" }

// Response exitosa
{
  "estado": "Alta",
  "data": {
    "codigo_unspsc": "43211515",
    "descripcion_oficial": "Estaciones de trabajo para computadores",
    "jerarquia": "Difusión de Tecnologías de Información y Telecomunicaciones -> Equipo informático y accesorios -> Computadores"
  }
}
---

## 📄 Variables de Entorno (`.env`)

```env
GROQ_API_KEY=...
OPENROUTER_API_KEY=...
DEEPSEEK_API_KEY=...
SILICONFLOW_API_KEY=...
MISTRAL_API_KEY=...
GEMINI_API_KEY=...
FLASK_SECRET_KEY=...
```
