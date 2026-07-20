import os
import time
import pickle
import pandas as pd
import numpy as np
import torch
from sentence_transformers import SentenceTransformer
import faiss

def main():
    start_time = time.time()
    
    # 1. Crear estructura de carpetas
    base_dir = os.path.dirname(os.path.abspath(__file__))
    data_dir = os.path.join(base_dir, 'data')
    os.makedirs(data_dir, exist_ok=True)
    print(f"Carpeta '{data_dir}' verificada/creada.")
    
    # 2. Leer catálogo Excel
    excel_path = os.path.join(base_dir, 'unspcs-modelo.xlsx')
    if not os.path.exists(excel_path):
        print(f"Error: No se encontró el archivo '{excel_path}' en '{base_dir}'.")
        return
        
    print(f"Cargando archivo Excel '{excel_path}'...")
    df = pd.read_excel(excel_path)
    print(f"Catálogo cargado con {len(df)} registros.")
    
    # Identificar nombres de columnas dinámicamente debido a posibles problemas de codificación (ej: Código)
    col_mapping = {}
    for col in df.columns:
        col_lower = col.lower()
        if 'segmento' in col_lower:
            if 'nombre' in col_lower:
                col_mapping['nom_segmento'] = col
            else:
                col_mapping['cod_segmento'] = col
        elif 'familia' in col_lower:
            if 'nombre' in col_lower:
                col_mapping['nom_familia'] = col
            else:
                col_mapping['cod_familia'] = col
        elif 'clase' in col_lower:
            if 'nombre' in col_lower:
                col_mapping['nom_clase'] = col
            else:
                col_mapping['cod_clase'] = col
        elif 'producto' in col_lower:
            if 'nombre' in col_lower:
                col_mapping['nom_producto'] = col
            else:
                col_mapping['cod_producto'] = col

    # Validar que todas las columnas requeridas fueron mapeadas
    required_keys = ['cod_producto', 'nom_producto', 'cod_clase', 'nom_clase', 
                     'cod_familia', 'nom_familia', 'cod_segmento', 'nom_segmento']
    missing_keys = [k for k in required_keys if k not in col_mapping]
    if missing_keys:
        print(f"Error: Columnas faltantes o no reconocidas: {missing_keys}")
        print(f"Columnas disponibles en Excel: {list(df.columns)}")
        return
        
    print("Mapeo de columnas exitoso:")
    for k, v in col_mapping.items():
        print(f"  - {k} -> {v}")
        
    # 3. Concatenar los campos para crear descripciones ricas en contexto
    print("Construyendo strings de contexto enriquecidos...")
    contextos = []
    metadata = {}
    
    for idx, row in df.iterrows():
        # Extraer valores y limpiar
        cod_prod = int(row[col_mapping['cod_producto']])
        nom_prod = str(row[col_mapping['nom_producto']]).strip()
        cod_clase = int(row[col_mapping['cod_clase']])
        nom_clase = str(row[col_mapping['nom_clase']]).strip()
        cod_fam = int(row[col_mapping['cod_familia']])
        nom_fam = str(row[col_mapping['nom_familia']]).strip()
        cod_seg = int(row[col_mapping['cod_segmento']])
        nom_seg = str(row[col_mapping['nom_segmento']]).strip()
        
        # Formato de contexto enriquecido de alta pureza semántica (sin ruido de etiquetas)
        texto_puro = f"{nom_prod}, clase {nom_clase}, familia {nom_fam}, segmento {nom_seg}"
        contexto = texto_puro.lower()
        contextos.append(contexto)
        
        # Guardar metadatos jerárquicos
        metadata[cod_prod] = {
            'codigo_producto': cod_prod,
            'nombre_producto': nom_prod,
            'codigo_clase': cod_clase,
            'nombre_clase': nom_clase,
            'codigo_familia': cod_fam,
            'nombre_familia': nom_fam,
            'codigo_segmento': cod_seg,
            'nombre_segmento': nom_seg,
            'contexto': contexto
        }
        
    # 4. Inicializar modelo de lenguaje
    print("Cargando el modelo 'paraphrase-multilingual-MiniLM-L12-v2'...")
    device = 'cuda' if torch.cuda.is_available() else 'cpu'
    print(f"Dispositivo de procesamiento seleccionado: {device.upper()}")
    model = SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2', device=device)
    
    # 5. Generar embeddings
    print("Generando embeddings vectoriales (esto puede tomar unos minutos)...")
    t_emb_start = time.time()
    embeddings = model.encode(
        contextos, 
        batch_size=256, 
        show_progress_bar=True, 
        convert_to_numpy=True
    )
    t_emb_end = time.time()
    print(f"Embeddings generados en {t_emb_end - t_emb_start:.2f} segundos.")
    print(f"Dimensiones de los embeddings: {embeddings.shape}")
    
    # 6. Normalización L2 (necesaria para que el Inner Product equivalga a la similitud coseno)
    print("Normalizando vectores para similitud coseno...")
    embeddings = embeddings.astype('float32')
    faiss.normalize_L2(embeddings)
    
    # 7. Crear índice local FAISS con mapeo de IDs personalizados (Código de Producto)
    print("Creando índice local de FAISS...")
    dimension = embeddings.shape[1]
    index_flat = faiss.IndexFlatIP(dimension) # Flat Inner Product
    index = faiss.IndexIDMap(index_flat)      # Envoltura para mapeo de IDs personalizados
    
    # IDs correspondientes a cada vector
    ids = df[col_mapping['cod_producto']].values.astype('int64')
    
    # Agregar vectores con sus IDs correspondientes
    index.add_with_ids(embeddings, ids)
    print(f"Vectores agregados al índice FAISS. Total en índice: {index.ntotal}")
    
    # 8. Guardar índice FAISS y Metadatos en disco
    index_file = os.path.join(data_dir, 'index.faiss')
    metadata_file = os.path.join(data_dir, 'metadata.pkl')
    
    print(f"Guardando índice vectorial en '{index_file}'...")
    faiss.write_index(index, index_file)
    
    print(f"Guardando archivo de metadatos en '{metadata_file}'...")
    with open(metadata_file, 'wb') as f:
        pickle.dump(metadata, f)
        
    total_time = time.time() - start_time
    print(f"\n¡Ingesta completada con éxito!")
    print(f"Tiempo total transcurrido: {total_time:.2f} segundos.")
    print(f"Archivos creados:")
    print(f"  - {index_file} ({os.path.getsize(index_file) / (1024*1024):.2f} MB)")
    print(f"  - {metadata_file} ({os.path.getsize(metadata_file) / (1024*1024):.2f} MB)")

if __name__ == '__main__':
    main()
