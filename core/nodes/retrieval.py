from ..state import AgentState, ProductItem
import json
import re
import faiss
import numpy as np
import logging
from typing import Dict, Any, List
from ..models import ddgs, llamar_llm_con_fallback
from database import get_cached_search, set_cached_search
from ..rag.faiss_engine import get_chatbot, normalizar_texto, obtener_tokens_clave
from .extraction import limpiar_consulta
from ..config import EXCLUDED_BOOST_KEYWORDS, SYNONYM_MAP, NOUN_CLASS_MAPPING
from ..prompts.templates import get_verifier_prompt

logger = logging.getLogger(__name__)

def market_verifier_node(state: AgentState) -> Dict[str, Any]:
    """Nodo 2: Verifica en internet si el producto existe o busca detalles técnicos si es muy específico."""
    items = state.get("items", [])
    
    for item in items:
        query = item["original_query"]
        if item.get("categoria_dominio") == "RECHAZADO":
            logger.info(f"[VERIFIER] Omitiendo búsqueda web para ítem rechazado: '{query}'")
            continue

        # Ruteo por búsqueda web (bypass inteligente)
        if item.get("requiere_busqueda_web") is not True:
            logger.info(f"[VERIFIER] Omitiendo búsqueda web (requiere_busqueda_web=False) para: '{query}'")
            continue

        # 1. Intentar obtener de la caché local primero
        cached_result = get_cached_search(query)
        if cached_result:
            try:
                cached_data = json.loads(cached_result)
                logger.info(f"[CACHE HIT] Usando contexto web guardado para: '{query}'")
                item["market_context"] = cached_data.get("market_context", "")
                # Añadir palabras clave cacheadas a expanded_queries
                for kw in cached_data.get("keywords", []):
                    kw_clean = limpiar_consulta(kw)
                    if kw_clean and kw_clean not in item["expanded_queries"]:
                        item["expanded_queries"].append(kw_clean)
                continue
            except Exception as e:
                logger.error(f"[CACHE] Error decodificando caché para {query}: {e}")

        # 2. Si no hay caché, buscar en DuckDuckGo
        if not ddgs:
            continue
            
        search_query = f"{query} ficha técnica producto industrial"
        
        try:
            results = ddgs.text(search_query, max_results=3)
            
            # Filtrar resultados irrelevantes (diccionarios, noticias, jurídicos)
            relevant_bodies = []
            irrelevant_domains = ['rae.es', 'wikipedia.org', 'definicion', 'significado', 'diccionario']
            for r in results:
                body = r.get('body', '')
                href = r.get('href', '').lower()
                title = r.get('title', '').lower()
                
                # Saltar si parece irrelevante
                is_irrelevant = any(d in href or d in title for d in irrelevant_domains)
                if body and not is_irrelevant:
                    relevant_bodies.append(body)
            
            if relevant_bodies:
                combined_context = " | ".join(relevant_bodies[:2])  # Máximo 2 snippets
                item["market_context"] = f"Datos reales de internet: {combined_context}"
                
                # Extraer palabras clave técnicas con Groq
                extract_prompt = get_verifier_prompt(query, combined_context)
                try:
                    res_content = llamar_llm_con_fallback(extract_prompt)
                    
                    match = re.search(r'\[.*\]', res_content, re.DOTALL)
                    if match:
                        keywords = json.loads(match.group(0))
                        keywords_clean = []
                        for kw in keywords:
                            kw_clean = limpiar_consulta(kw)
                            if kw_clean:
                                keywords_clean.append(kw_clean)
                                if kw_clean not in item["expanded_queries"]:
                                    item["expanded_queries"].append(kw_clean)
                        
                        # Guardar en la caché
                        cache_data = {
                            "market_context": item["market_context"],
                            "keywords": keywords_clean
                        }
                        set_cached_search(query, json.dumps(cache_data, ensure_ascii=False))
                except Exception as ex:
                    logger.error(f"Error extrayendo palabras clave de internet para {query}: {ex}")
            else:
                logger.info(f"DDG: Sin resultados relevantes para '{search_query}'")
                
        except Exception as e:
            logger.error(f"Error DDGS para {query}: {e}")
            
    return {"items": items}

def retriever_node(state: AgentState) -> Dict[str, Any]:
    """Nodo 3: Recupera candidatos RAG para cada ítem en la canasta."""
    cb = get_chatbot()
    items = state.get("items", [])
    
    for item in items:
        if item.get("categoria_dominio") == "RECHAZADO":
            logger.info(f"[RETRIEVER] Omitiendo búsqueda RAG para ítem rechazado: '{item['original_query']}'")
            continue
        
        main_noun = normalizar_texto(item.get("sustantivo_principal", ""))
        main_noun_synonyms = {main_noun}
        if main_noun in SYNONYM_MAP:
            for syn in SYNONYM_MAP[main_noun]:
                main_noun_synonyms.add(syn)

        lexical_tokens = set()
        for eq in item["expanded_queries"]:
            tokens = obtener_tokens_clave(eq)
            for t in tokens:
                norm_t = normalizar_texto(t)
                if norm_t not in EXCLUDED_BOOST_KEYWORDS and len(norm_t) > 2:
                    lexical_tokens.add(norm_t)
                    if norm_t in SYNONYM_MAP:
                        for syn in SYNONYM_MAP[norm_t]:
                            lexical_tokens.add(syn)
                
        candidates_dict = {}
        if cb.model is not None:
            for sub_query in item["expanded_queries"]:
                if not sub_query: continue
                try:
                    query_vector = cb.model.encode([sub_query], convert_to_numpy=True, show_progress_bar=False).astype('float32')
                    faiss.normalize_L2(query_vector)
                    
                    scores, ids = cb.index.search(query_vector, 5)
                    
                    for i in range(len(ids[0])):
                        prod_id = int(ids[0][i])
                        score = float(scores[0][i])
                        meta = cb.metadata.get(prod_id, None)
                        if meta:
                            score_perc = score * 100
                            if prod_id in candidates_dict:
                                candidates_dict[prod_id]["score_percentage"] = max(candidates_dict[prod_id]["score_percentage"], score_perc)
                            else:
                                candidates_dict[prod_id] = {
                                    "codigo_producto": prod_id,
                                    "nombre_producto": meta["nombre_producto"],
                                    "ruta_jerarquica": f"{meta['nombre_segmento']} -> {meta['nombre_familia']} -> {meta['nombre_clase']}",
                                    "score_percentage": score_perc,
                                    "lexical_matches": 0,
                                    "metadata": meta
                                }
                except Exception as e_enc:
                    logger.warning(f"[RETRIEVER] Error en encode vectorial: {e_enc}")
        
        # Pre-encode q_clean once outside the metadata loop if model is present
        q_clean = item["expanded_queries"][0] if item["expanded_queries"] else ""
        q_vec = None
        if q_clean and cb.model is not None:
            try:
                q_vec = cb.model.encode([q_clean], convert_to_numpy=True, show_progress_bar=False).astype('float32')
                faiss.normalize_L2(q_vec)
            except Exception:
                q_vec = None
            
        allowed_prefixes = NOUN_CLASS_MAPPING.get(main_noun, None)

        # Keyword match usando índice invertido para alta velocidad y mínimo uso de memoria
        if hasattr(cb, 'inverted_index') and cb.inverted_index:
            prod_token_matches = {}  # prod_id -> set of matched tokens
            for token in lexical_tokens:
                if token in cb.inverted_index:
                    for prod_id in cb.inverted_index[token]:
                        if prod_id not in prod_token_matches:
                            prod_token_matches[prod_id] = set()
                        prod_token_matches[prod_id].add(token)

            for prod_id, matched_tokens in prod_token_matches.items():
                matches = len(matched_tokens)
                prod_id_str = str(prod_id)
                is_class_allowed = True
                if allowed_prefixes:
                    is_class_allowed = any(prod_id_str.startswith(prefix) for prefix in allowed_prefixes)

                if not is_class_allowed:
                    if prod_id in candidates_dict:
                        del candidates_dict[prod_id]
                    continue

                has_main_noun = len(main_noun_synonyms.intersection(matched_tokens)) > 0
                boost = matches * 25.0
                if has_main_noun:
                    boost += 150.0  # Huge boost to prioritize the main product noun!

                if prod_id in candidates_dict:
                    candidates_dict[prod_id]["lexical_matches"] = matches
                    candidates_dict[prod_id]["score_percentage"] += boost
                else:
                    if q_vec is not None:
                        seq_idx = cb.id_to_seq[prod_id]
                        vec = np.zeros(384, dtype='float32')
                        cb.flat_index.reconstruct(seq_idx, vec)
                        vec = vec / np.linalg.norm(vec)
                        score_semantic = float(np.dot(q_vec[0], vec)) * 100
                    else:
                        score_semantic = 0.0
                    candidates_dict[prod_id] = {
                        "codigo_producto": prod_id,
                        "nombre_producto": cb.metadata[prod_id]["nombre_producto"],
                        "ruta_jerarquica": f"{cb.metadata[prod_id]['nombre_segmento']} -> {cb.metadata[prod_id]['nombre_familia']} -> {cb.metadata[prod_id]['nombre_clase']}",
                        "score_percentage": score_semantic + boost,
                        "lexical_matches": matches,
                        "metadata": cb.metadata[prod_id]
                    }
        elif hasattr(cb, 'precomputed_words') and cb.precomputed_words:
            for prod_id, prod_words in cb.precomputed_words.items():
                matches = len(lexical_tokens.intersection(prod_words))
                if matches > 0:
                    prod_id_str = str(prod_id)
                    is_class_allowed = True
                    if allowed_prefixes:
                        is_class_allowed = any(prod_id_str.startswith(prefix) for prefix in allowed_prefixes)
                    
                    if not is_class_allowed:
                        if prod_id in candidates_dict:
                            del candidates_dict[prod_id]
                        continue
                        
                    has_main_noun = len(main_noun_synonyms.intersection(prod_words)) > 0
                    boost = matches * 25.0
                    if has_main_noun:
                        boost += 150.0
                        
                    if prod_id in candidates_dict:
                        candidates_dict[prod_id]["lexical_matches"] = matches
                        candidates_dict[prod_id]["score_percentage"] += boost
                    else:
                        if q_vec is not None:
                            seq_idx = cb.id_to_seq[prod_id]
                            vec = np.zeros(384, dtype='float32')
                            cb.flat_index.reconstruct(seq_idx, vec)
                            vec = vec / np.linalg.norm(vec)
                            score_semantic = float(np.dot(q_vec[0], vec)) * 100
                        else:
                            score_semantic = 0.0
                        candidates_dict[prod_id] = {
                            "codigo_producto": prod_id,
                            "nombre_producto": cb.metadata[prod_id]["nombre_producto"],
                            "ruta_jerarquica": f"{cb.metadata[prod_id]['nombre_segmento']} -> {cb.metadata[prod_id]['nombre_familia']} -> {cb.metadata[prod_id]['nombre_clase']}",
                            "score_percentage": score_semantic + boost,
                            "lexical_matches": matches,
                            "metadata": cb.metadata[prod_id]
                        }
                    
        # --- LIMPIEZA FINAL DE CLASES NO PERMITIDAS ---
        if allowed_prefixes:
            for pid in list(candidates_dict.keys()):
                pid_str = str(pid)
                if not any(pid_str.startswith(prefix) for prefix in allowed_prefixes):
                    del candidates_dict[pid]
                    
        cands = list(candidates_dict.values())
        cands.sort(key=lambda x: x["score_percentage"], reverse=True)
        item["candidates"] = cands[:8]
        
    return {"items": items}
