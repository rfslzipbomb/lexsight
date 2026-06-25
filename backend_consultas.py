import os
import re
from dotenv import load_dotenv  # Importamos la librería
import pypdf
from docx import Document
import google.genai as genai

# 1. Carga las variables del archivo .env al entorno local
load_dotenv()

# 2. Configura la API de forma segura
api_key = os.environ.get("GEMINI_API_KEY")
primary_model_name = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")
fallback_model_names = [m.strip() for m in os.environ.get("GEMINI_MODEL_FALLBACKS", "gemini-2.5-alpha,gemini-2.1, gemini-2.5-flash-lite").split(",") if m.strip() and m.strip() != primary_model_name]
if not api_key:
    print("ADVERTENCIA: No se encontró GEMINI_API_KEY en las variables de entorno.")
    client = None
else:
    client = genai.client.Client(api_key=api_key)

KNOWLEDGE_DIR = os.path.join(os.path.dirname(__file__), 'knowledge_base')

if not os.path.exists(KNOWLEDGE_DIR):
    os.makedirs(KNOWLEDGE_DIR)

# ... [MANTÉN TUS FUNCIONES extraer_texto_pdf y extraer_texto_docx EXACTAMENTE IGUAL] ...
def extraer_texto_pdf(path):
    texto = ""
    try:
        with open(path, "rb") as f:
            lector = pypdf.PdfReader(f)
            for pagina in lector.pages:
                texto += pagina.extract_text() + "\n"
    except Exception as e:
        print(f"Error leyendo PDF en {path}: {e}")
    return texto

def extraer_texto_docx(path):
    texto = ""
    try:
        doc = Document(path)
        for parrafo in doc.paragraphs:
            texto += parrafo.text + "\n"
    except Exception as e:
        print(f"Error leyendo DOCX en {path}: {e}")
    return texto

def cargar_base_conocimientos():
    contenido_total = []
    if not os.path.exists(KNOWLEDGE_DIR):
        return ""
    for archivo in os.listdir(KNOWLEDGE_DIR):
        ruta_completa = os.path.join(KNOWLEDGE_DIR, archivo)
        if archivo.endswith('.pdf'):
            contenido_total.append(extraer_texto_pdf(ruta_completa))
        elif archivo.endswith('.docx'):
            contenido_total.append(extraer_texto_docx(ruta_completa))
        elif archivo.endswith('.txt'):
            with open(ruta_completa, 'r', encoding='utf-8') as f:
                contenido_total.append(f.read())
    return "\n".join(contenido_total)

def filtrar_contexto_relevante(query, base_texto, max_caracteres=10000):
    if not base_texto:
        return ""
    parrafos = base_texto.split('\n')
    palabras_clave = [w.lower() for w in query.split() if len(w) > 3]
    fragmentos_coincidentes = []
    for parrafo in parrafos:
        if any(kw in parrafo.lower() for kw in palabras_clave):
            fragmentos_coincidentes.append(parrafo.strip())
    contexto_filtrado = "\n".join(fragmentos_coincidentes)
    return contexto_filtrado[:max_caracteres] if contexto_filtrado else base_texto[:max_caracteres]

# ==========================================
# CONEXIÓN CON GEMINI Y VALIDACIONES (GUARDRAILS)
# ==========================================
def limpiar_texto_respuesta(texto):
    """Elimina formatos markdown y etiquetas HTML que no deben aparecer en la UI."""
    if not texto:
        return texto

    # Eliminar bloques de código o delimitadores de estilo del LLM
    texto = re.sub(r'```[\s\S]*?```', '', texto)

    # Limpiar etiquetas HTML
    texto = re.sub(r'<[^>]+>', '', texto)

    # Limpiar negritas, itálicas y subrayados de markdown
    markdown_patterns = [r'\*\*(.*?)\*\*', r'\*(.*?)\*', r'__(.*?)__', r'_(.*?)_', r'`(.*?)`']
    for pattern in markdown_patterns:
        texto = re.sub(pattern, r'\1', texto)

    # Limpiar citas y guiones o bullets al inicio de línea
    texto = re.sub(r'^[\s]*>\s*', '', texto, flags=re.MULTILINE)
    texto = re.sub(r'^[\s]*[-*•]+\s+', '', texto, flags=re.MULTILINE)

    # Normalizar espacios en blanco y saltos de línea
    texto = re.sub(r'\s*\n\s*\n\s*', '\n\n', texto)
    texto = re.sub(r'\n{3,}', '\n\n', texto)
    return texto.strip()


# Modifica la función consultar_api_llm para recibir el modo
def consultar_api_llm(prompt_estructurado, mode="fast"):
    try:
        if client is None:
            return "Error de configuración de Gemini."

        # Priorización de modelos según el modo
        if mode == "deep":
            # Usar el modelo más potente para razonamiento complejo
            modelos_a_intentar = ["gemini-2.5-pro", primary_model_name] + fallback_model_names
        else:
            # Modelos rápidos para el flujo convencional
            modelos_a_intentar = [primary_model_name] + fallback_model_names

        ultimo_error = None
        for modelo in modelos_a_intentar:
            try:
                # Si es deep research, le damos más libertad creativa (temperatura) para redactar el informe
                temp = 0.4 if mode == "deep" else 0.2
                respuesta = client.models.generate_content(
                    model=modelo,
                    contents=[prompt_estructurado],
                    config=genai.types.GenerateContentConfig(temperature=temp)
                )
                
                texto_salida = respuesta.text if hasattr(respuesta, 'text') else getattr(respuesta.output[0], 'content', '')
                return limpiar_texto_respuesta(texto_salida)
            except Exception as e:
                ultimo_error = e
                continue
                
        return "Ha ocurrido un error de conexión con el motor de análisis legal."
    except Exception as e:
        return "Error interno en consultar_api_llm."


def procesar_pipeline_legal(query_usuario, historial, texto_documento=""):
    """
    Pipeline legal rápido para el modo principal de LexSight.
    """
    prompt_legal = (
        "Eres LexSight, un asistente legal profesional. Responde de forma clara y concisa, "
        "centrándote en el análisis jurídico, los riesgos relevantes y las recomendaciones prácticas.\n\n"
    )

    if texto_documento:
        prompt_legal += f"DOCUMENTO ADJUNTO:\n{texto_documento}\n\n"

    if historial:
        historial_texto = "\n".join([f"{item['role'].capitalize()}: {item['content']}" for item in historial])
        prompt_legal += f"CONTEXTO DEL HISTORIAL:\n{historial_texto}\n\n"

    prompt_legal += f"CONSULTA DEL USUARIO:\n{query_usuario}\n\nRESPUESTA:"
    return consultar_api_llm(prompt_legal, mode="fast")


# Crea una nueva función para el pipeline de Deep Research
def procesar_pipeline_deep_research(query_usuario, historial, texto_documento, contexto_kb):
    prompt_deep = (
        "Eres LexSight, actuando en modo 'Deep Research'. Se te ha entregado un documento legal "
        "y/o una consulta compleja. Tu tarea es generar una respuesta dividida ESTRICTAMENTE en dos secciones.\n\n"
        "REGLAS ESTRICTAS DE FORMATO:\n"
        "1. ESTÁ ABSOLUTAMENTE PROHIBIDO USAR ETIQUETAS HTML.\n"
        "2. Divide tu respuesta usando EXACTAMENTE estos marcadores:\n\n"
        "[RESUMEN_EJECUTIVO]\n"
        "(Escribe aquí un resumen sucinto, claro y directo de máximo 2 o 3 párrafos para mostrar en la interfaz de chat rápido)\n\n"
        "[INFORME_COMPLETO]\n"
        "(Escribe aquí el informe exhaustivo detallado usando Markdown con **negritas** y guiones para listas)\n\n"
        "En la sección [INFORME_COMPLETO] debes analizar el documento e identificar:\n"
        "1. Tipo de contrato o naturaleza.\n"
        "2. Cláusulas principales, obligaciones y derechos.\n"
        "3. Montos y fechas críticas.\n"
        "4. ALERTA DE RIESGOS: Señala explícitamente condiciones sospechosas, multas excesivas o restricciones ambiguas.\n\n"
        f"--- CONTEXTO DE BASE DE CONOCIMIENTOS ---\n{contexto_kb}\n"
        f"--- DOCUMENTO ADJUNTO ---\n{texto_documento}\n"
        f"--- CONSULTA DEL USUARIO ---\n{query_usuario}\n"
        "RESPUESTA:"
    )
    
    # Retornamos crudo para hacer el split en app.py
    return consultar_api_llm(prompt_deep, mode="deep")