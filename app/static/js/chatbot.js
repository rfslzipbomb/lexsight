/**
 * LexSight Chatbot Core - Soporte de Texto y Carga de Documentos
 */

const SESSION_ID = 'lex_' + Math.random().toString(36).substring(2, 11);
const API_URL = '/api/chat';

const fileInput = document.getElementById('file-input');
const btnAttach = document.getElementById('btn-attach');
const previewContainer = document.getElementById('file-preview-container');
const previewName = document.getElementById('file-preview-name');
const btnRemoveFile = document.getElementById('btn-remove-file');

// Disparar el selector de archivos al presionar el clip
btnAttach.addEventListener('click', () => fileInput.click());

// Escuchar cuando el usuario selecciona un archivo
fileInput.addEventListener('change', () => {
  if (fileInput.files.length > 0) {
    const file = fileInput.files[0];
    previewName.innerHTML = `<i class="fa-solid fa-file-lines me-2"></i>${file.name} (${(file.size/1024).toFixed(1)} KB)`;
    previewContainer.classList.remove('d-none');
  }
});

// Remover archivo seleccionado
btnRemoveFile.addEventListener('click', () => {
  clearFileInput();
});

function clearFileInput() {
  fileInput.value = '';
  previewContainer.classList.add('d-none');
  previewName.innerText = '';
}

document.getElementById('chat-form').addEventListener('submit', async function(e) {
  e.preventDefault();
  
  const inputField = document.getElementById('user-input');
  const chatBox = document.getElementById('chat-box');
  const userMessage = inputField.value.trim();
  const hasFile = fileInput.files.length > 0;
  
  if (!userMessage && !hasFile) return;

  // 1. Mostrar mensaje en pantalla indicando si lleva un adjunto
  let visibleText = userMessage;
  if (hasFile) {
    visibleText += `\n\n[📎 Archivo adjunto: ${fileInput.files[0].name}]`;
  }
  appendMessageBubble(visibleText, 'user');
  
  // Limpiar inputs inmediatamente en la UI
  inputField.value = '';
  const fileToSend = hasFile ? fileInput.files[0] : null;
  clearFileInput();
  chatBox.scrollTop = chatBox.scrollHeight;

  // 2. Placeholder de espera
  const tempBotId = 'waiting-node-' + Date.now();
  appendMessageBubble('LexSight analizando tu consulta y documentos...', 'bot', tempBotId, true);
  chatBox.scrollTop = chatBox.scrollHeight;

  try {
    // 3. Construcción de Multipart Form Data
    // 3. Construcción de Multipart Form Data
    const formData = new FormData();
    formData.append('message', userMessage);
    formData.append('session_id', SESSION_ID);
    
    // NUEVO: Capturar el estado del modo de investigación
    const isDeepResearch = document.getElementById('deep-research-toggle').checked;
    formData.append('mode', isDeepResearch ? 'deep' : 'fast');

    if (fileToSend) {
      formData.append('file', fileToSend);
    }

    // 4. Petición AJAX enviando el formulario binario
    const response = await fetch(API_URL, {
      method: 'POST',
      body: formData // No añadimos 'Content-Type' en los headers, el navegador lo calcula automáticamente con los boundaries del archivo
    });

    if (!response.ok) throw new Error('Error al conectar con la API de Flask');

    const data = await response.json();
    
    const loadingPlaceholder = document.getElementById(tempBotId);
    if (loadingPlaceholder) {
      loadingPlaceholder.classList.remove('typing-dots');
      const textoLimpio = data.response ? data.response.replace(/\n/g, '<br>') : '';
      loadingPlaceholder.innerHTML = textoLimpio;
      
      if (data.buttons_html) {
        const botonesDiv = document.createElement('div');
        botonesDiv.innerHTML = data.buttons_html;
        botonesDiv.style.marginTop = '0.75rem';
        loadingPlaceholder.appendChild(botonesDiv);
      }
    }

  } catch (error) {
    console.error('Fetch error:', error);
    const loadingPlaceholder = document.getElementById(tempBotId);
    if (loadingPlaceholder) {
      loadingPlaceholder.classList.remove('typing-dots');
      loadingPlaceholder.innerHTML = '<span class="text-danger"><i class="fa-solid fa-triangle-exclamation me-1"></i> Error en la transferencia del documento hacia Flask.</span>';
    }
  }

  chatBox.scrollTop = chatBox.scrollHeight;
});

function appendMessageBubble(text, sender, id = null, isLoading = false) {
  const chatBox = document.getElementById('chat-box');
  const msgDiv = document.createElement('div');
  
  if (sender === 'user') {
    msgDiv.className = 'message user p-3 rounded align-self-end text-white shadow-sm';
    msgDiv.style.backgroundColor = '#1a434e';
    msgDiv.style.borderRadius = '16px 16px 0px 16px';
    msgDiv.style.whiteSpace = 'pre-line'; // Permite saltos de línea para el texto del clip
  } else {
    msgDiv.className = 'message bot p-3 rounded align-self-start shadow-sm';
    msgDiv.style.backgroundColor = '#f4f8f9';
    msgDiv.style.color = '#0b2329';
    msgDiv.style.borderLeft = '4px solid #539ca8';
    msgDiv.style.borderRadius = '16px 16px 16px 0px';
    if (isLoading) msgDiv.className += ' typing-dots';
  }

  if (id) msgDiv.id = id;
  msgDiv.style.maxWidth = '80%';
  msgDiv.style.fontSize = '0.95rem';
  msgDiv.innerText = text;
  
  chatBox.appendChild(msgDiv);
}

document.getElementById('clear-chat').addEventListener('click', function() {
  document.getElementById('chat-box').innerHTML = `
    <div class="message bot p-3 rounded align-self-start shadow-sm msg-welcome">
      Consola reiniciada con éxito. Listo para un nuevo análisis de documentos.
    </div>
  `;
});

/**
 * Función global para invocar el Modal y cargar el informe PDF
 * sin interrumpir la sesión de chat activa del usuario.
 */
window.abrirModalPDF = function(urlDocumento) {
  // Configurar la ruta en el iframe
  const iframe = document.getElementById('iframePDF');
  iframe.src = urlDocumento;
  
  // Instanciar y mostrar el Modal
  const modalElement = document.getElementById('modalVisorPDF');
  const visorModal = new bootstrap.Modal(modalElement);
  visorModal.show();
  
  // Limpiar el src al cerrar para evitar sobrecarga de memoria
  modalElement.addEventListener('hidden.bs.modal', function () {
    iframe.src = '';
  }, { once: true });
};