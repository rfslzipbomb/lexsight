import os
import re
from datetime import datetime
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_JUSTIFY, TA_CENTER
from reportlab.lib.colors import HexColor

def crear_informe_pdf(texto_informe, directorio_salida, nombre_archivo):
    """
    Toma texto estructurado en Markdown básico y genera un PDF formateado.
    """
    # Estandarización de la ruta de guardado
    if not os.path.exists(directorio_salida):
        os.makedirs(directorio_salida)

    filepath = os.path.join(directorio_salida, nombre_archivo)

    # Configuración del lienzo PDF
    doc = SimpleDocTemplate(filepath, pagesize=letter,
                            rightMargin=50, leftMargin=50,
                            topMargin=50, bottomMargin=50)

    styles = getSampleStyleSheet()

    # Creación de Estilos Corporativos para LexSight
    estilo_titulo = ParagraphStyle(
        'TituloReporte',
        parent=styles['Heading1'],
        alignment=TA_CENTER,
        textColor=HexColor("#1a434e"), # Color corporativo LexSight
        spaceAfter=20
    )

    estilo_normal = ParagraphStyle(
        'NormalJustificado',
        parent=styles['Normal'],
        alignment=TA_JUSTIFY,
        fontSize=11,
        leading=16, # Interlineado
        spaceAfter=12
    )

    Story = []

    # 1. Agregar Encabezado
    Story.append(Paragraph("Informe de Deep Research - LexSight", estilo_titulo))
    fecha = datetime.now().strftime("%d de %B, %Y - %H:%M")
    Story.append(Paragraph(f"<b>Fecha de análisis:</b> {fecha}", styles['Normal']))
    Story.append(Spacer(1, 20))

    # 2. Sanitización: Prevenir que caracteres sueltos (<, >) rompan ReportLab
    texto_seguro = texto_informe.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')

    # 3. Traducción de Markdown a ReportLab XML
    texto_seguro = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', texto_seguro) # Convertir **negritas**
    texto_seguro = re.sub(r'\*(.*?)\*', r'<i>\1</i>', texto_seguro)       # Convertir *cursivas*

    # 4. Procesamiento por Párrafos
    parrafos = texto_seguro.split('\n\n')
    for p in parrafos:
        p_limpio = p.strip()
        if p_limpio:
            # Si el LLM listó items con guiones o asteriscos, los formateamos bonito
            if p_limpio.startswith('- ') or p_limpio.startswith('* '):
                p_limpio = p_limpio[2:] 
                Story.append(Paragraph(f"&bull; {p_limpio}", estilo_normal))
            else:
                # Reemplazar saltos de línea internos por <br/> de ReportLab
                p_limpio = p_limpio.replace('\n', '<br/>')
                Story.append(Paragraph(p_limpio, estilo_normal))

    # Construir y guardar
    doc.build(Story)
    return filepath