from typing import TypedDict, List, Dict, Any, Optional

class ProductItem(TypedDict):
    original_query: str
    expanded_queries: List[str]
    market_context: str
    candidates: List[Dict[str, Any]]
    best_match: Optional[Dict[str, Any]]
    estado_decision: str
    pregunta_aclaratoria: str
    one_line_desc: str
    sustantivo_principal: str
    atributos_recolectados: Dict[str, str]
    atributos_faltantes: List[Dict[str, Any]]
    requiere_busqueda_web: bool
    requiere_revision_humana: bool
    categoria_dominio: str
    criticidad: str

class AgentState(TypedDict):
    messages: List[Dict[str, str]]
    items: List[ProductItem]
    global_status: str
    estado_global: Optional[str]
    mensaje_global: Optional[str]
