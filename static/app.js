document.addEventListener('DOMContentLoaded', () => {
    const chatForm = document.getElementById('chat-form');
    const userInput = document.getElementById('user-input');
    const chatMessages = document.getElementById('chat-messages');
    const sendBtn = document.getElementById('send-btn');


    async function sendChatMessage(queryText, showInChat = true, isOptionSelection = false) {
        if (!queryText) return;
        setLoadingState(true);

        if (showInChat) {
            appendMessage('user', queryText);
        }
        const typingIndicator = appendTypingIndicator();

        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), 25000);

        try {
            const response = await fetch('/api/classify', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                signal: controller.signal,
                body: JSON.stringify({ 
                    query: queryText,
                    is_new_query: !isOptionSelection
                })
            });
            clearTimeout(timeoutId);

            if (!response.ok) throw new Error('Error en el servidor');
            
            const data = await response.json();
            typingIndicator.remove();
            renderBotResponse(data);
        } catch (error) {
            clearTimeout(timeoutId);
            console.error('Error:', error);
            typingIndicator.remove();
            const errText = error.name === 'AbortError' ? 'La consulta tardó demasiado tiempo en responder. Por favor, reintenta.' : error.message;
            appendMessage('bot', `❌ Error: ${errText}`);
        } finally {
            setLoadingState(false);
        }
    }

    window.sendOptionSelection = function(queryText, originalProduct, btnElement) {
        // Deshabilitar todos los botones de opciones para evitar clics dobles
        const allOptionBtns = document.querySelectorAll('.option-choice-btn');
        allOptionBtns.forEach(btn => {
            btn.disabled = true;
            btn.style.opacity = '0.5';
            btn.style.cursor = 'not-allowed';
            btn.style.pointerEvents = 'none';
        });

        if (btnElement) {
            btnElement.style.opacity = '1';
            btnElement.style.border = '2px solid #38bdf8';
        }

        const baseQuery = originalProduct || window.lastQuery || '';
        const fullContext = baseQuery ? `${baseQuery} destinado a: ${queryText}` : `Producto destinado a: ${queryText}`;
        sendChatMessage(fullContext, true, true);
    };

    chatForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        const queryText = userInput.value.trim();
        if (!queryText) return;

        window.lastQuery = queryText; 
        userInput.value = '';
        await sendChatMessage(queryText);
    });

    function setLoadingState(isLoading) {
        userInput.disabled = isLoading;
        sendBtn.disabled = isLoading;
        if (isLoading) {
            sendBtn.classList.add('loading');
        } else {
            sendBtn.classList.remove('loading');
            userInput.focus();
        }
    }

    function getBotAvatar() {
        return `
        <div class="avatar bot-avatar">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M12 2a2 2 0 0 1 2 2c0 .74-.4 1.39-1 1.73V7h1a7 7 0 0 1 7 7h1a1 1 0 0 1 1 1v3a1 1 0 0 1-1 1h-1v1a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-1H2a1 1 0 0 1-1-1v-3a1 1 0 0 1 1-1h1a7 7 0 0 1 7-7h1V5.73c-.6-.34-1-.99-1-1.73a2 2 0 0 1 2-2z"></path>
            </svg>
        </div>`;
    }

    function getUserAvatar() {
        return `
        <div class="avatar user-avatar">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"></path>
                <circle cx="12" cy="7" r="4"></circle>
            </svg>
        </div>`;
    }

    function appendMessage(sender, text) {
        const messageDiv = document.createElement('div');
        messageDiv.className = `message ${sender} slide-in`;
        
        messageDiv.innerHTML = `
            ${sender === 'bot' ? getBotAvatar() : getUserAvatar()}
            <div class="message-content">
                <p>${text}</p>
            </div>
        `;
        
        chatMessages.appendChild(messageDiv);
        scrollToBottom();
        return messageDiv;
    }

    function appendTypingIndicator() {
        const messageDiv = document.createElement('div');
        messageDiv.className = 'message bot typing-msg fade-in';
        messageDiv.innerHTML = `
            ${getBotAvatar()}
            <div class="message-content">
                <div class="typing-indicator">
                    <span></span><span></span><span></span>
                </div>
            </div>
        `;
        chatMessages.appendChild(messageDiv);
        scrollToBottom();
        return messageDiv;
    }

    function renderBotResponse(data) {
        const messageDiv = document.createElement('div');
        messageDiv.className = 'message bot pop-in';
        let contentHTML = '';

        if (data.estado === 'Alta' && data.items) {
            let itemsList = data.items.map(i => {
                return `
                <div class="item-card glass-panel" style="padding: 16px; border-left: 4px solid var(--accent-light, #10b981); margin-bottom: 10px;">
                    <div class="item-header" style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
                        <span class="badge success" style="background: rgba(16, 185, 129, 0.15); color: #10b981; padding: 4px 10px; borderRadius: 6px; font-weight: 600; font-size: 12px;">CÓDIGO UNSPSC</span>
                        <span class="item-code" style="font-family: monospace; font-size: 18px; font-weight: 700; color: #38bdf8;">${i.codigo_exacto}</span>
                    </div>
                    <div class="item-body">
                        <h4 style="margin: 4px 0 8px 0; font-size: 16px; color: #f8fafc;">${i.nombre_producto}</h4>
                        <p class="hierarchy" style="font-size: 13px; color: #94a3b8; line-height: 1.4; margin: 0;">${i.ruta_jerarquica.replace(/->/g, ' › ')}</p>
                    </div>
                </div>`;
            }).join('');

            contentHTML = `
                <div class="message-content" style="width: 100%; max-width: 800px;">
                    <p class="success-text" style="font-weight: 600; color: #38bdf8; margin-bottom: 12px;">✅ Código UNSPSC Identificado:</p>
                    <div class="items-grid">
                        ${itemsList}
                    </div>
                </div>
            `;
        } else if (data.estado === 'Ambig\u00fcedad' || data.estado === 'Baja') {
            let optionsButtonsHTML = '';
            const opcionesList = data.opciones || (data.items && data.items[0] && data.items[0].opciones ? data.items[0].opciones : []);
            if (opcionesList && opcionesList.length > 0) {
                const currentOrigQuery = (data.items && data.items[0] && data.items[0].original_query) ? data.items[0].original_query : (window.lastQuery || '');
                const safeOrig = currentOrigQuery.replace(/'/g, "\\'");
                
                let buttons = opcionesList.map(opt => {
                    const title = typeof opt === 'string' ? opt : (opt.titulo || opt.nombre || JSON.stringify(opt));
                    const desc = typeof opt === 'object' && opt.descripcion ? `<span style="display:block; font-size:12px; opacity:0.8; margin-top:2px;">${opt.descripcion}</span>` : '';
                    const safeTitle = title.replace(/'/g, "\\'");
                    return `<button class="glass-btn option-choice-btn" style="margin: 6px 0; padding: 12px 16px; text-align: left; display: block; width: 100%; cursor: pointer;" onclick="window.sendOptionSelection('${safeTitle}', '${safeOrig}', this)">
                        <strong>👉 ${title}</strong>
                        ${desc}
                    </button>`;
                }).join('');

                optionsButtonsHTML = `<div class="options-container glass-panel" style="margin-top: 12px; padding: 12px;">
                    <p style="font-size: 13px; font-weight: 600; margin-bottom: 8px; color: var(--accent-light, #3b82f6);">Selecciona una opción para clasificar directamente:</p>
                    ${buttons}
                </div>`;
            }

            contentHTML = `
                <div class="message-content" style="width: 100%; max-width: 600px;">
                    <div class="question-card glass-panel alert">
                        <div class="icon-pulse">🤔</div>
                        <p>${(data.mensaje || 'Por favor, elige una de las opciones para clasificar el producto:').replace(/\n/g, '<br>')}</p>
                    </div>
                    ${optionsButtonsHTML}
                </div>
            `;
        } else if (data.estado === 'Rechazado') {
            contentHTML = `
                <div class="message-content" style="width: 100%; max-width: 600px;">
                    <div class="question-card glass-panel alert error" style="border-left: 4px solid #ef4444;">
                        <div class="icon-pulse">❌</div>
                        <p>${data.mensaje.replace(/\n/g, '<br>')}</p>
                    </div>
                </div>
            `;
        } else {
            contentHTML = `
                <div class="message-content" style="width: 100%; max-width: 600px;">
                    <div class="question-card glass-panel alert error" style="border-left: 4px solid #ef4444;">
                        <div class="icon-pulse">⚠️</div>
                        <p>${data.mensaje ? data.mensaje.replace(/\n/g, '<br>') : 'Error procesando la solicitud.'}</p>
                    </div>
                </div>
            `;
        }

        messageDiv.innerHTML = `
            ${getBotAvatar()}
            ${contentHTML}
        `;
        chatMessages.appendChild(messageDiv);
        scrollToBottom();
    }

    function scrollToBottom() {
        chatMessages.scrollTop = chatMessages.scrollHeight;
    }

    function showToast(message) {
        let container = document.getElementById('toast-container');
        if (!container) {
            container = document.createElement('div');
            container.id = 'toast-container';
            container.className = 'toast-container';
            document.body.appendChild(container);
        }
        
        const toast = document.createElement('div');
        toast.className = 'toast';
        toast.innerHTML = `
            <svg viewBox="0 0 24 24" fill="none" stroke="#10b981" stroke-width="2.5" style="width:20px;height:20px;">
                <polyline points="20 6 9 17 4 12"></polyline>
            </svg>
            <span>${message}</span>
        `;
        container.appendChild(toast);
        
        setTimeout(() => {
            toast.remove();
            if (container.children.length === 0) {
                container.remove();
            }
        }, 3000);
    }

    // Export function to global to be used in HTML onclick
    window.copyAllSpecs = function() {
        const codes = Array.from(document.querySelectorAll('.one-line-spec code')).map(c => c.innerText).join('\n');
        navigator.clipboard.writeText(codes).then(() => {
            showToast('¡Especificaciones copiadas al portapapeles!');
        });
    }

    window.selectChip = function(btn) {
        const container = btn.parentElement;
        Array.from(container.querySelectorAll('.option-chip')).forEach(c => {
            c.classList.remove('active');
        });
        btn.classList.add('active');
    }

    window.submitCardAclaraciones = function(element, sustantivo) {
        const card = element.closest('.clarification-card');
        if (!card) return;
        
        const fields = Array.from(card.querySelectorAll('.form-field'));
        const respuestas = [];
        
        for (const field of fields) {
            const attr = field.getAttribute('data-atributo');
            const tipo = field.getAttribute('data-tipo');
            
            if (tipo === 'botones') {
                const activeChip = field.querySelector('.option-chip.active');
                if (activeChip) {
                    const val = activeChip.getAttribute('data-value');
                    respuestas.push(`${attr}: ${val}`);
                }
            } else if (tipo === 'texto') {
                const input = field.querySelector('.field-text-input');
                if (input && input.value.trim()) {
                    respuestas.push(`${attr}: ${input.value.trim()}`);
                }
            }
        }
        
        if (respuestas.length === 0) {
            showToast('Por favor, selecciona o ingresa al menos un atributo.');
            return;
        }
        
        // Deshabilitar la tarjeta para evitar doble envío
        Array.from(card.querySelectorAll('input, button')).forEach(el => {
            el.disabled = true;
        });
        card.style.opacity = '0.6';
        card.style.pointerEvents = 'none';
        
        const msg = `Para ${sustantivo}, ${respuestas.join(', ')}`;
        sendChatMessage(msg, false);
    }

});
