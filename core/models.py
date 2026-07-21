import os
import logging
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

# Cargar variables de entorno desde .env
load_dotenv()

# Configuración de LangSmith para monitoreo de trazas
if os.environ.get("LANGCHAIN_API_KEY"):
    os.environ["LANGCHAIN_TRACING_V2"] = "true"
    logger.info("[LANGSMITH] Monitoreo activado correctamente.")

# Helper para obtener variables de entorno insensibles a mayúsculas/minúsculas
def get_env_var(key: str) -> str:
    return os.environ.get(key.upper()) or os.environ.get(key) or os.environ.get(key.lower()) or ""

# Clientes
from groq import Groq
try:
    key = get_env_var("GROQ_API_KEY")
    groq_client = Groq(api_key=key) if key else None
except Exception as e:
    groq_client = None

from openai import OpenAI
try:
    key = get_env_var("OPENROUTER_API_KEY")
    openrouter_client = OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=key
    ) if key else None
except:
    openrouter_client = None

from google import genai
try:
    key = get_env_var("GEMINI_API_KEY")
    gemini_client = genai.Client(api_key=key) if key else None
except:
    gemini_client = None

try:
    key = get_env_var("DEEPSEEK_API_KEY")
    deepseek_client = OpenAI(
        base_url="https://api.deepseek.com",
        api_key=key
    ) if key else None
except:
    deepseek_client = None

try:
    key = get_env_var("SILICONFLOW_API_KEY")
    siliconflow_client = OpenAI(
        base_url="https://api.siliconflow.cn/v1",
        api_key=key
    ) if key else None
except:
    siliconflow_client = None

try:
    key = get_env_var("MISTRAL_API_KEY")
    mistral_client = OpenAI(
        base_url="https://api.mistral.ai/v1",
        api_key=key
    ) if key else None
except:
    mistral_client = None

# Búsqueda web
try:
    from duckduckgo_search import DDGS
    ddgs = DDGS()
except:
    ddgs = None


DEFAULT_ORDER = ["groq", "openrouter", "deepseek", "siliconflow", "mistral", "gemini"]

def llamar_llm_con_fallback(prompt: str, providers_order: list = None, temperature: float = 0.1) -> str:
    """
    Llama a los LLMs en cascada según el orden provisto hasta obtener una respuesta exitosa.
    """
    order = providers_order or DEFAULT_ORDER
    
    for provider in order:
        try:
            if provider == "openrouter" and openrouter_client:
                logger.info("Llamando a OpenRouter (Claude-3.5-Sonnet)...")
                response = openrouter_client.chat.completions.create(
                    messages=[{"role": "user", "content": prompt}],
                    model="anthropic/claude-3.5-sonnet:beta",
                    temperature=temperature
                )
                return response.choices[0].message.content
                
            elif provider == "deepseek" and deepseek_client:
                logger.info("Llamando a DeepSeek (deepseek-chat)...")
                response = deepseek_client.chat.completions.create(
                    messages=[{"role": "user", "content": prompt}],
                    model="deepseek-chat",
                    temperature=temperature
                )
                return response.choices[0].message.content
                
            elif provider == "groq" and groq_client:
                logger.info("Llamando a Groq (Llama-3.3-70b-versatile)...")
                response = groq_client.chat.completions.create(
                    messages=[{"role": "user", "content": prompt}],
                    model="llama-3.3-70b-versatile",
                    temperature=temperature
                )
                return response.choices[0].message.content
                
            elif provider == "siliconflow" and siliconflow_client:
                logger.info("Llamando a SiliconFlow (deepseek-ai/DeepSeek-V3)...")
                response = siliconflow_client.chat.completions.create(
                    messages=[{"role": "user", "content": prompt}],
                    model="deepseek-ai/DeepSeek-V3",
                    temperature=temperature
                )
                return response.choices[0].message.content
                
            elif provider == "mistral" and mistral_client:
                logger.info("Llamando a Mistral (mistral-large-latest)...")
                response = mistral_client.chat.completions.create(
                    messages=[{"role": "user", "content": prompt}],
                    model="mistral-large-latest",
                    temperature=temperature
                )
                return response.choices[0].message.content
                
            elif provider == "gemini" and gemini_client:
                logger.info("Llamando a Gemini (gemini-2.5-flash)...")
                response = gemini_client.models.generate_content(
                    model='gemini-2.5-flash',
                    contents=prompt
                )
                return response.text
                
        except Exception as e:
            logger.warning(f"Error en proveedor {provider}: {e}")
            continue

    raise Exception("Todos los proveedores de LLM fallaron.")
