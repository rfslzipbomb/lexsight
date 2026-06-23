import os
from dotenv import load_dotenv  # Importamos la librería
import pypdf
from docx import Document
import google.genai as genai

# 1. Carga las variables del archivo .env al entorno local
load_dotenv()

# 2. Configura la API de forma segura
api_key = os.environ.get("GEMINI_API_KEY")
model_name = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")
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
def consultar_api_llm(prompt_estructurado):
    """
    Envía el prompt a Gemini 2.5 Flash asegurando que no se desvíe del propósito de LexSight.
    """
    # 1. Definimos las reglas de comportamiento inquebrantables
    instrucciones_sistema = (
        "Eres LexSight, un asistente de inteligencia legal altamente capacitado y profesional. "
        "Tu propósito exclusivo es proporcionar análisis jurídico, resumir contratos, interpretar normativas "
        "y asistir en tareas propias del derecho.\n\n"
        "REGLA DE SEGURIDAD CRÍTICA: Tienes estrictamente prohibido responder consultas, generar texto o analizar "
        "documentos que no estén relacionados con el ámbito legal, jurídico o corporativo (por ejemplo: programación, "
        "cocina, entretenimiento, redacción creativa general, etc.). Si el usuario intenta salir de este contexto, "
        "debes rechazar la solicitud educadamente informando que tus capacidades están limitadas exclusivamente "
        "a la asistencia legal."
    )

    try:
        if client is None:
            return "Error de configuración de Gemini: no hay clave de API disponible."

        # 2. Llamada a la API con el nuevo SDK de google.genai
        respuesta = client.models.generate_content(
            model=model_name,
            contents=[prompt_estructurado],
            config=genai.types.GenerateContentConfig(
                temperature=0.2,
            )
        )

        return respuesta.text or ""

    except Exception as e:
        print(f"Error conectando con la API de Gemini: {e}")
        return "Ha ocurrido un error de conexión con el motor de análisis legal. Por favor, verifica la integridad de tu consulta o intenta más tarde."

def procesar_pipeline_legal(query_usuario, historial):
    """
    Coordina la estructura de datos antes de enviarla a Gemini.
    """
    texto_completo_base = cargar_base_conocimientos()
    contexto_documentos = filtrar_contexto_relevante(query_usuario, texto_completo_base)
    
    # Construcción del Prompt con el contexto proporcionado
    bloque_contexto = ""
    if contexto_documentos:
        bloque_contexto = f"--- CONTEXTO DE CONOCIMIENTO Y DOCUMENTOS ADJUNTOS ---\n{contexto_documentos}\n-------------------------\n"

    conversacion_previa = "--- HISTORIAL RECIENTE ---\n"
    for msg in historial:
        rol = "Usuario" if msg['role'] == 'user' else "LexSight"
        conversacion_previa += f"{rol}: {msg['content']}\n"
    conversacion_previa += "-------------------------\n"
        
    prompt_final = (
        f"{bloque_contexto}"
        f"{conversacion_previa}"
        f"Nueva consulta del Usuario: {query_usuario}\n"
        f"Respuesta de LexSight:"
    )
    
    return consultar_api_llm(prompt_final)