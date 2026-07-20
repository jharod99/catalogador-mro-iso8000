"""
Módulo de generación de descripciones técnicas comerciales.
Utiliza la clave API centralizada de Gemini para generar descripciones mejoradas.
"""
import os
from google import genai

# --- Carga centralizada de claves API ---
def _cargar_clave_gemini():
    path = os.path.join(os.path.dirname(__file__), "Clave API.txt")
    try:
        with open(path, 'r', encoding='utf-8') as f:
            for line in f:
                if ":" in line:
                    k, v = line.split(":", 1)
                    if k.strip() == "Gemini_API_KEY":
                        return v.strip()
    except Exception as e:
        print(f"Error cargando clave Gemini desde '{path}': {e}")
    return ""

_gemini_client = None
def _get_gemini_client():
    global _gemini_client
    if _gemini_client is None:
        api_key = _cargar_clave_gemini()
        if not api_key:
            raise RuntimeError("No se encontró la clave 'Gemini_API_KEY' en 'Clave API.txt'.")
        _gemini_client = genai.Client(api_key=api_key)
    return _gemini_client


def mejorar_descripcion(raw_text, clase_unspsc):
    """
    Genera una descripción técnica comercial estructurada a partir del texto
    crudo del usuario y la categoría UNSPSC asignada.
    """
    prompt = f"""
Actúa como un comprador técnico experto. 
Tengo el siguiente texto desordenado o abreviado que un usuario ingresó para buscar un producto:
"{raw_text}"

Este producto ha sido clasificado bajo la categoría UNSPSC: "{clase_unspsc}".

Tu tarea es tomar ese texto original e inferir sus especificaciones para redactar una "Descripción Comercial/Técnica" estructurada, limpia y profesional, ideal para enviarla a un proveedor en una orden de compra o cotización.

Reglas:
1. No inventes características que no estén implícitas en el texto original, pero dale formato profesional.
2. Usa viñetas para listar las especificaciones técnicas extraídas.
3. Devuelve SOLO la descripción resultante en formato Markdown. Nada de saludos ni "Aquí tienes...".
4. Si el texto original es muy corto (ej. "laptop dell"), infiere los campos que el proveedor típicamente requeriría (ej. "Procesador: [A definir]", "RAM: [A definir]").
5. CORRIGE errores ortográficos, de digitación o de espaciado evidentes (ej. 'decuña' → 'de cuña').

Formato esperado:
**[Nombre Genérico del Producto]**
* **Marca/Modelo:** ...
* **Especificaciones:**
  * ...
"""
    try:
        client = _get_gemini_client()
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt
        )
        return response.text.strip()
    except Exception as e:
        return f"**Error al generar descripción:** {str(e)}"


if __name__ == "__main__":
    # Prueba rápida
    txt = "BALANZA BBD659-400, 30KG X 5G/1G (E/D), 300MM X 400MM, FRONT MOUNT, INOX 304, RS-485 + USB,220VAC"
    print(mejorar_descripcion(txt, "Balanzas industriales"))
