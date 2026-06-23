import os
import sqlite3
from flask import Flask, render_template, request, jsonify
from flask_cors import CORS
# Importamos las herramientas de lectura que ya programamos en tu backend_consultas
from backend_consultas import procesar_pipeline_legal, extraer_texto_pdf, extraer_texto_docx

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
        archivo_adjunto = request.files.get('file')

        texto_del_archivo = ""

        # 1. Validación y guardado si el usuario adjuntó un documento
        if archivo_adjunto and archivo_adjunto.filename != '':
            nombre_seguro = archivo_adjunto.filename
            
            # --- AQUÍ VA LA VALIDACIÓN DEL SERVIDOR ---
            extensiones_permitidas = ['.pdf', '.docx']
            if not any(nombre_seguro.lower().endswith(ext) for ext in extensiones_permitidas):
                # Rechaza la petición si no es un PDF o DOCX
                return jsonify({'response': 'Formato de archivo no admitido. LexSight solo procesa documentos PDF o DOCX.'}), 400
            # ------------------------------------------

            ruta_temporal = os.path.join(UPLOAD_TEMP_DIR, nombre_seguro)
            archivo_adjunto.save(ruta_temporal)

            # Extraer el texto según su formato
            if nombre_seguro.endswith('.pdf'):
                texto_del_archivo = extraer_texto_pdf(ruta_temporal)
            elif nombre_seguro.endswith('.docx'):
                texto_del_archivo = extraer_texto_docx(ruta_temporal)

            # Eliminar el archivo temporal para mantener el entorno limpio
            if os.path.exists(ruta_temporal):
                os.remove(ruta_temporal)

        # Si no hay mensaje pero sí archivo, estructuramos un texto para el log
        log_mensaje = mensaje_usuario if mensaje_usuario else f"[Envió un documento: {archivo_adjunto.filename}]"

        # 2. Guardar interacción en SQLite
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO historial_chat (session_id, remitente, mensaje) VALUES (?, ?, ?)",
            (session_id, 'user', log_mensaje)
        )
        conn.commit()

        # 3. Contexto reciente
        cursor.execute(
            "SELECT remitente, mensaje FROM historial_chat WHERE session_id = ? ORDER BY timestamp DESC LIMIT 6",
            (session_id,)
        )
        filas = cursor.fetchall()
        historial_contexto = [{"role": f[0], "content": f[1]} for f in reversed(filas)]

        # 4. Inyectar texto del documento extraído (si lo hay)
        if texto_del_archivo:
            mensaje_usuario = f"{mensaje_usuario}\n\n[CONTEXTO ADJUNTO POR EL USUARIO DESDE EL DOCUMENTO]:\n{texto_del_archivo}"

        # 5. Ejecutar pipeline legal (conecta con Gemini)
        respuesta_bot = procesar_pipeline_legal(mensaje_usuario, historial_contexto)

        # 6. Guardar respuesta generada
        cursor.execute(
            "INSERT INTO historial_chat (session_id, remitente, mensaje) VALUES (?, ?, ?)",
            (session_id, 'bot', respuesta_bot)
        )
        conn.commit()
        conn.close()

        return jsonify({'response': respuesta_bot}), 200

    except Exception as e:
        print(f"Error procesando adjunto multipart en /api/chat: {e}")
        return jsonify({'response': 'Error en el servidor al leer o procesar el documento enviado.'}), 500

if __name__ == '__main__':
    # init_db()
    app.run(debug=True, port=5001)