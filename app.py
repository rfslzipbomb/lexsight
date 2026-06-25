import os
import sqlite3
from pdf_generator import crear_informe_pdf
from backend_consultas import procesar_pipeline_legal, procesar_pipeline_deep_research, extraer_texto_pdf, extraer_texto_docx, limpiar_texto_respuesta
from flask import Flask, render_template, request, jsonify, url_for
from flask_cors import CORS
import uuid
from fpdf import FPDF # Asegúrate de hacer: pip install fpdf2

REPORTS_DIR = os.path.join(os.path.dirname(__file__), 'app/static/reports')
if not os.path.exists(REPORTS_DIR):
    os.makedirs(REPORTS_DIR)

app = Flask(
    __name__,
    template_folder='app/templates',
    static_folder='app/static',
    static_url_path='/static'
)
CORS(app)

@app.route('/')
@app.route('/home')
def home():
    return render_template('home.html')

@app.route('/chatbot')
def chatbot():
    return render_template('chatbot.html')

@app.route('/sobre-nosotros')
def about():
    return render_template('sobre-nosotros.html')

DB_PATH = os.path.join(os.path.dirname(__file__), 'lexsight.sqlite')
UPLOAD_TEMP_DIR = os.path.join(os.path.dirname(__file__), 'app/static/uploads_temp')

if not os.path.exists(UPLOAD_TEMP_DIR):
    os.makedirs(UPLOAD_TEMP_DIR)

# (Mantenemos tu función init_db() e indexado de rutas normales igual...)

@app.route('/api/chat', methods=['POST'])
def chat_api():
    try:
        mensaje_usuario = request.form.get('message', '').strip()
        session_id = request.form.get('session_id', 'session_general')
        modo_analisis = request.form.get('mode', 'fast') # Recuperamos el modo
        archivo_adjunto = request.files.get('file')

        texto_del_archivo = ""
        # ... [MANTÉN AQUÍ TU LÓGICA DE GUARDADO TEMPORAL Y EXTRACCIÓN DE TEXTO EXACTAMENTE IGUAL] ...

        # Recuperar historial
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT remitente, mensaje FROM historial_chat WHERE session_id = ? ORDER BY timestamp DESC LIMIT 6", (session_id,))
        filas = cursor.fetchall()
        historial_contexto = [{"role": f[0], "content": f[1]} for f in reversed(filas)]

        # --- BIFURCACIÓN DE FLUJO ---
        # --- BIFURCACIÓN DE FLUJO ---
        response_data = {}

        if modo_analisis == 'deep':
            from backend_consultas import cargar_base_conocimientos, filtrar_contexto_relevante
            texto_base = cargar_base_conocimientos()
            contexto_kb = filtrar_contexto_relevante(mensaje_usuario, texto_base)
            
            # Ejecutar Deep Research (Retorna texto con delimitadores)
            respuesta_cruda = procesar_pipeline_deep_research(mensaje_usuario, historial_contexto, texto_del_archivo, contexto_kb)
            
            # Inicializar variables por defecto en caso de que el LLM falle con el formato
            resumen_chat = "Análisis profundo completado. Por favor, revisa el documento adjunto."
            informe_completo = respuesta_cruda

            # Separar el Resumen del Informe Completo
            if "[RESUMEN_EJECUTIVO]" in respuesta_cruda and "[INFORME_COMPLETO]" in respuesta_cruda:
                partes = respuesta_cruda.split("[INFORME_COMPLETO]")
                resumen_chat = partes[0].replace("[RESUMEN_EJECUTIVO]", "").strip()
                informe_completo = partes[1].strip()
            
            # 1. Generar el PDF Profesional con el Informe Completo
            REPORTS_DIR = os.path.join(os.path.dirname(__file__), 'app', 'static', 'reports')
            nombre_reporte = f"DeepResearch_{uuid.uuid4().hex[:8]}.pdf"
            crear_informe_pdf(informe_completo, REPORTS_DIR, nombre_reporte)

            # 2. Limpiar solo el Resumen Ejecutivo para la UI
            texto_chat_limpio = limpiar_texto_respuesta(resumen_chat)
            url_pdf = url_for('static', filename=f'reports/{nombre_reporte}')

            # 3. Preparar controles interactivos sin mezclarlos con el texto del chat
            botones_interfaz = (
                f"<div class='d-flex gap-2'>"
                f"<button type='button' onclick='abrirModalPDF(\"{url_pdf}\")' class='btn btn-sm text-white fw-medium shadow-sm' style='background-color: #1a434e; border-radius: 10px;'>"
                f"<i class='fa-solid fa-file-magnifying-glass me-2'></i>Ver Informe Completo</button>"
                f"<a href='{url_pdf}' download class='btn btn-sm btn-outline-secondary' style='border-radius: 10px;' title='Descargar archivo'>"
                f"<i class='fa-solid fa-download'></i></a>"
                f"</div>"
            )

            response_data = {
                'response': texto_chat_limpio,
                'buttons_html': botones_interfaz
            }
        else:
            # Flujo rápido convencional
            if texto_del_archivo:
                mensaje_usuario = f"{mensaje_usuario}\n\n[DOCUMENTO]:\n{texto_del_archivo}"
            response_data = {
                'response': procesar_pipeline_legal(mensaje_usuario, historial_contexto)
            }

        # 6. Guardar en SQLite y retornar
        # ... (Tu código existente para guardar e insertar)
        return jsonify(response_data), 200
    except Exception as e:
        print(f"Error procesando /api/chat: {e}")
        return jsonify({'response': 'Error en el servidor.'}), 500

if __name__ == '__main__':
    # init_db()
    app.run(debug=True, port=5001)