import os
os.environ["CUDA_VISIBLE_DEVICES"] = ""  # Force CPU to prevent CUDA conflicts
os.environ["OMP_NUM_THREADS"] = "1"      # Prevent thread thrashing/hanging on CPU
os.environ["MKL_NUM_THREADS"] = "1"      # Prevent MKL thread thrashing
os.environ["TQDM_DISABLE"] = "1"         # Disable tqdm progress bars to prevent Windows redirect errors
os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"
os.environ["TOKENIZERS_PARALLELISM"] = "false"

import torch
torch.set_num_threads(1)                 # Prevent PyTorch thread deadlock

import pickle
import re
import numpy as np
from sentence_transformers import SentenceTransformer
import faiss
faiss.omp_set_num_threads(1)             # Force FAISS to use a single thread to prevent Windows Errno 22

def obtener_tokens_clave(query):
    q = query.lower()
    q = re.sub(r'[^a-zA-Z\u00C0-\u017F\s]', ' ', q)
    
    # Únicamente stopwords funcionales en español
    stopwords = {'de', 'para', 'con', 'en', 'un', 'una', 'el', 'la', 'los', 'las', 'y', 'o', 'a', 'del', 'x', 'e', 'd', 'c', 'm'}
    noise = set()  # Vacío intencionalmente: preserva nombres industriales y modelos
    
    raw_tokens = q.split()
    clean_tokens = []
    
    # Mapeo a tokens en español generales e instrumentación industrial
    translations = {
        'workstation': ['estacion', 'trabajo', 'computador'],
        'workstations': ['estacion', 'trabajo', 'computador'],
        'estaciones': ['estacion'],
        'trabajo': ['trabajo'],
        'laptop': ['computador', 'portatil'],
        'laptops': ['computador', 'portatil'],
        'portatiles': ['portatil'],
        'computer': ['computador'],
        'computers': ['computador'],
        'computadores': ['computador'],
        'desktop': ['computador', 'escritorio'],
        'desktops': ['computador', 'escritorio'],
        # Mapeos de tags de instrumentación
        'lsl': ['interruptor', 'nivel', 'bajo', 'instrumento', 'sensor'],
        'lsh': ['interruptor', 'nivel', 'alto', 'instrumento', 'sensor'],
        'ls': ['interruptor', 'nivel', 'instrumento', 'sensor'],
        'lt': ['transmisor', 'nivel', 'instrumento', 'sensor', 'medida'],
        'pt': ['transmisor', 'presion', 'instrumento', 'sensor'],
        'tt': ['transmisor', 'temperatura', 'instrumento', 'sensor'],
        'ft': ['transmisor', 'flujo', 'caudal', 'instrumento', 'sensor'],
        'dp': ['presion', 'diferencial', 'instrumento', 'sensor']
    }
    
    for t in raw_tokens:
        if t in stopwords or t in noise or len(t) < 2:
            continue
        if t in translations:
            clean_tokens.extend(translations[t])
        else:
            clean_tokens.append(t)
            
    return set(clean_tokens)

def limpiar_consulta(query):
    # Limpieza básica para el modelo de embeddings
    q = query.lower()
    
    translations = {
        r'\bworkstation\b': 'estaciones de trabajo para computadores',
        r'\bworkstations\b': 'estaciones de trabajo para computadores',
        r'\blaptop\b': 'computador portatil',
        r'\blaptops\b': 'computador portatil',
        r'\bdesktop\b': 'computadores de escritorio',
        r'\bdesktops\b': 'computadores de escritorio',
        r'\bcomputer\b': 'computador',
        r'\bcomputers\b': 'computadores',
        # Expansión de tags de instrumentación para embeddings
        r'\blsl\b': 'interruptor de nivel bajo sensor instrumento',
        r'\blsh\b': 'interruptor de nivel alto sensor instrumento',
        r'\bls\b': 'interruptor de nivel sensor instrumento',
        r'\blt\b': 'transmisor de nivel sensor instrumento',
        r'\bpt\b': 'transmisor de presion sensor instrumento',
        r'\btt\b': 'transmisor de temperatura sensor instrumento',
        r'\bft\b': 'transmisor de flujo sensor instrumento',
        r'\bdp\b': 'presion diferencial sensor instrumento'
    }
    for en_pattern, es_replacement in translations.items():
        q = re.sub(en_pattern, es_replacement, q)
        
    # Nota: No se filtran marcas ni especificaciones de hardware para preservar
    # nombres industriales (ej: Demtech, Caterpillar) y modelos (500-123, BBD659).
    
        
    q = re.sub(r'\b[a-z]\b', '', q) # Remover letras sueltas (ej: x, e, d)
    q = re.sub(r'[-/+,()]', ' ', q) # Reemplazar puntuaciones residuales con espacio
    q = re.sub(r'\s+', ' ', q).strip()
    return q

class FastEmbedAdapter:
    def __init__(self, model_name="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"):
        from fastembed import TextEmbedding
        self.embedding_model = TextEmbedding(model_name=model_name)
    
    def encode(self, sentences, convert_to_numpy=True, show_progress_bar=False):
        if isinstance(sentences, str):
            sentences = [sentences]
        embeddings = list(self.embedding_model.embed(sentences))
        return np.array(embeddings, dtype='float32')

class UNSPSCChatbot:
    def __init__(self, data_dir=None):
        if data_dir is None:
            data_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'data')
        self.data_dir = data_dir
        self.index_path = os.path.join(data_dir, 'index.faiss')
        self.metadata_path = os.path.join(data_dir, 'metadata.pkl')
        
        # Verificar que los archivos del "cerebro" existen
        if not os.path.exists(self.index_path) or not os.path.exists(self.metadata_path):
            raise FileNotFoundError(
                f"El cerebro del chatbot no está listo. "
                f"Por favor ejecuta primero 'ingesta_datos.py' para generar el índice y metadatos."
            )
            
        # Cargar modelo de embeddings (FastEmbed -> SentenceTransformer -> Fallback Léxico)
        print("Cargando modelo de lenguaje...")
        self.model = None
        try:
            self.model = FastEmbedAdapter("sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")
            self.model.encode(["test"])
            print("Modelo ONNX FastEmbed cargado exitosamente (RAM optimizada < 250MB).")
        except Exception as e_fast:
            logger.warning(f"FastEmbed no disponible: {e_fast}. Probando SentenceTransformer...")
            try:
                self.device = 'cuda' if torch.cuda.is_available() else 'cpu'
                self.model = SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2', device=self.device)
            except Exception as e_st:
                logger.warning(f"SentenceTransformer no disponible: {e_st}. Usando motor RAG léxico de ultra-baja memoria.")
                self.model = None
        
        # Cargar índice FAISS
        print("Cargando índice vectorial local (FAISS)...")
        self.index = faiss.read_index(self.index_path)
        
        # Cargar mapeo de IDs a índices secuenciales de FAISS para reconstrucción
        self.id_map = faiss.vector_to_array(self.index.id_map)
        self.id_to_seq = {int(id_val): idx for idx, id_val in enumerate(self.id_map)}
        self.flat_index = faiss.downcast_index(self.index.index)
        
        # Cargar metadatos
        print("Cargando metadatos de los productos...")
        with open(self.metadata_path, 'rb') as f:
            self.metadata = pickle.load(f)
            
        print(f"Chatbot listo. Índice vectorial cargado con {self.index.ntotal} productos.")
        
    def buscar(self, query_text, k=3):
        """
        Busca las coincidencias semánticas del texto de entrada en el índice FAISS.
        """
        # 1. Generar embedding de la consulta
        query_vector = self.model.encode([query_text], convert_to_numpy=True, show_progress_bar=False)
        query_vector = query_vector.astype('float32')
        
        # 2. Normalizar L2 para similitud coseno
        faiss.normalize_L2(query_vector)
        
        # 3. Buscar en el índice FAISS
        scores, ids = self.index.search(query_vector, k)
        
        # Obtener los resultados
        resultados = []
        for i in range(k):
            score = float(scores[0][i])
            product_id = int(ids[0][i])
            
            # Obtener metadatos si existen
            prod_meta = self.metadata.get(product_id, None)
            resultados.append({
                'codigo_producto': product_id,
                'score': score,
                'metadata': prod_meta
            })
            
        return resultados

    def clasificar(self, query_text):
        """
        Clasifica la consulta combinando Búsqueda Semántica (FAISS) + Búsqueda Léxica
        (Keyword Search) y aplicando un boost por coincidencia de palabras clave.
        """
        # 1. Generar query limpia (sin ruido técnico o marcas)
        cleaned_query = limpiar_consulta(query_text)
        if not cleaned_query:
            cleaned_query = query_text # Fallback por si la limpieza borra todo
            
        # 2. Obtener tokens clave de la consulta limpia
        key_tokens = obtener_tokens_clave(cleaned_query)
        
        query_vector = self.model.encode([cleaned_query], convert_to_numpy=True, show_progress_bar=False)
        query_vector = query_vector.astype('float32')
        faiss.normalize_L2(query_vector)
        
        # 3. Búsqueda Semántica en FAISS (candidatos base)
        scores, ids = self.index.search(query_vector, 25)
        candidatos_dict = {}
        for i in range(25):
            score = float(scores[0][i])
            prod_id = int(ids[0][i])
            candidatos_dict[prod_id] = score
            
        # 4. Búsqueda Léxica (Keyword Search) sobre todo el catálogo para evitar misses semánticos
        if key_tokens:
            keyword_matches = []
            for prod_id, meta in self.metadata.items():
                prod_text = f"{meta['nombre_producto']} {meta['nombre_clase']} {meta['nombre_familia']}".lower()
                # Normalización básica de formas comunes
                prod_text = prod_text.replace('estaciones', 'estacion').replace('computadores', 'computador').replace('portatiles', 'portatil')
                
                matches = sum(1 for token in key_tokens if token in prod_text)
                if matches > 0:
                    keyword_matches.append((prod_id, matches))
            
            # Re-ordenar por cantidad de coincidencias y tomar las mejores 25 para evaluar
            keyword_matches.sort(key=lambda x: x[1], reverse=True)
            for prod_id, matches in keyword_matches[:25]:
                if prod_id not in candidatos_dict:
                    # Reconstruir vector y calcular la distancia semántica real contra la consulta limpia
                    seq_idx = self.id_to_seq[prod_id]
                    vec = np.zeros(384, dtype='float32')
                    self.flat_index.reconstruct(seq_idx, vec)
                    score = float(np.dot(query_vector[0], vec))
                    candidatos_dict[prod_id] = score

        # 5. Aplicar Boost por coincidencia de palabras clave y compilar candidatos finales
        candidatos_finales = []
        for prod_id, score_semantico in candidatos_dict.items():
            meta = self.metadata.get(prod_id, None)
            if not meta:
                continue
                
            prod_text = f"{meta['nombre_producto']} {meta['nombre_clase']} {meta['nombre_familia']}".lower()
            prod_text = prod_text.replace('estaciones', 'estacion').replace('computadores', 'computador').replace('portatiles', 'portatil')
            
            matches = 0
            if key_tokens:
                for token in key_tokens:
                    if token in prod_text:
                        matches += 1
                overlap_ratio = matches / len(key_tokens)
            else:
                overlap_ratio = 0.0
                
            # Boost proporcional (máximo +0.20)
            boost = 0.20 * overlap_ratio
            score_final = score_semantico + boost
            score_final = min(score_final, 1.0)
            
            candidatos_finales.append({
                'codigo_producto': prod_id,
                'score': score_final,
                'score_base': score_semantico,
                'boost': boost,
                'metadata': meta
            })
            
        candidatos_finales.sort(key=lambda x: x['score'], reverse=True)
        candidatos = candidatos_finales[:3]
        
        if not candidatos:
            return {
                'estado': 'Error',
                'mensaje': 'No se encontraron coincidencias en la base de datos.'
            }
            
        mejor_candidato = candidatos[0]
        score_max = mejor_candidato['score']
        score_percentage = score_max * 100
        
        if score_percentage > 85.0:
            meta = mejor_candidato['metadata']
            ruta = f"{meta['nombre_segmento']} -> {meta['nombre_familia']} -> {meta['nombre_clase']} -> {meta['nombre_producto']}"
            return {
                'estado': 'Alta',
                'codigo_exacto': mejor_candidato['codigo_producto'],
                'nombre_producto': meta['nombre_producto'],
                'ruta_jerarquica': ruta,
                'score': score_max,
                'score_percentage': score_percentage,
                'candidato': mejor_candidato
            }
            
        elif 50.0 <= score_percentage <= 85.0:
            opciones = []
            for c in candidatos:
                meta = c['metadata']
                ruta = f"{meta['nombre_segmento']} -> {meta['nombre_familia']} -> {meta['nombre_clase']} -> {meta['nombre_producto']}"
                opciones.append({
                    'codigo_producto': c['codigo_producto'],
                    'nombre_producto': meta['nombre_producto'],
                    'ruta_jerarquica': ruta,
                    'score': c['score'],
                    'score_percentage': c['score'] * 100
                })
            return {
                'estado': 'Ambig\u00fcedad',
                'mensaje': 'Se encontraron múltiples coincidencias posibles. Por favor, selecciona una de las opciones:',
                'opciones': opciones,
                'score': score_max,
                'score_percentage': score_percentage
            }
            
        else: # < 50.0%
            return {
                'estado': 'Falta de Datos',
                'mensaje': (
                    f"No pudimos determinar la categoría exacta con suficiente confianza "
                    f"(Similitud más alta: {score_percentage:.1f}%). "
                    f"Por favor, especifica más detalles sobre el material, composición o uso del producto."
                ),
                'score': score_max,
                'score_percentage': score_percentage
            }

def main():
    print("=" * 60)
    print("      Motor de Clasificación y Búsqueda Semántica UNSPSC      ")
    print("=" * 60)
    
    try:
        chatbot = UNSPSCChatbot()
    except FileNotFoundError as e:
        print(f"\n[ERROR] {e}")
        return
    except Exception as e:
        print(f"\n[ERROR] Ocurrió un error al inicializar el chatbot: {e}")
        return

    print("\nEl chatbot está listo. Escribe 'salir' para terminar.")
    print("-" * 60)
    
    while True:
        try:
            query = input("\nConsulta de producto (ej: 'comida para perros'): ").strip()
            if not query:
                continue
            if query.lower() in ['salir', 'exit', 'quit']:
                print("¡Hasta luego!")
                break
                
            res = chatbot.clasificar(query)
            
            print("\n" + "-" * 40)
            print(f"ESTADO DE RETORNO: {res['estado']} (Confianza: {res['score_percentage']:.2f}%)")
            print("-" * 40)
            
            if res['estado'] == 'Alta':
                print(f"Código UNSPSC: {res['codigo_exacto']}")
                print(f"Producto:      {res['nombre_producto']}")
                print(f"Ruta Jerárquica:")
                print(f"  {res['ruta_jerarquica']}")
                
            elif res['estado'] == 'Ambig\u00fcedad':
                print(res['mensaje'])
                for idx, opc in enumerate(res['opciones'], 1):
                    print(f"\nOption {idx} (Confianza: {opc['score_percentage']:.2f}%):")
                    print(f"  Código UNSPSC: {opc['codigo_producto']}")
                    print(f"  Producto:      {opc['nombre_producto']}")
                    print(f"  Jerarquía:     {opc['ruta_jerarquica']}")
                    
            elif res['estado'] == 'Falta de Datos':
                print(res['mensaje'])
                
        except (KeyboardInterrupt, EOFError):
            print("\n¡Hasta luego!")
            break
        except Exception as e:
            print(f"\nError al procesar la consulta: {e}")

if __name__ == '__main__':
    main()
import unicodedata

_chatbot = None
def get_chatbot():
    global _chatbot
    if _chatbot is None:
        _chatbot = UNSPSCChatbot()
        import re
        _chatbot.inverted_index = {}
        print("Precomputando índice invertido de productos para búsqueda léxica ultra-rápida...")
        for prod_id, meta in _chatbot.metadata.items():
            prod_text = f"{meta['nombre_producto']} {meta['nombre_clase']} {meta['nombre_familia']}"
            prod_text_norm = normalizar_texto(prod_text)
            words = set(re.findall(r'[a-z0-9]+', prod_text_norm))
            for w in words:
                if len(w) > 2:
                    if w not in _chatbot.inverted_index:
                        _chatbot.inverted_index[w] = []
                    _chatbot.inverted_index[w].append(prod_id)
        print("Precomputación de índice invertido completa.")
    return _chatbot

def normalizar_texto(text: str) -> str:
    text = text.lower()
    text = "".join(c for c in unicodedata.normalize('NFD', text) if unicodedata.category(c) != 'Mn')
    return text
