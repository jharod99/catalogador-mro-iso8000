document.addEventListener('DOMContentLoaded', () => {
    const chatForm = document.getElementById('chat-form');
    const userInput = document.getElementById('user-input');
    const chatMessages = document.getElementById('chat-messages');
    const sendBtn = document.getElementById('send-btn');
    const resetBtn = document.getElementById('reset-btn'); // Botón para resetear carrito

    if(resetBtn) {
        resetBtn.addEventListener('click', async () => {
            setLoadingState(true);
            try {
                await fetch('/api/classify', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({ query: 'reset', reset_session: true })
                });
                chatMessages.innerHTML = ''; // Limpiar chat
                appendMessage('bot', '🛒 He vaciado tu carrito. ¿Qué productos necesitas cotizar ahora?');
            } catch(e) {
                console.error(e);
            }
            setLoadingState(false);
        });
    }

    async function sendChatMessage(queryText, showInChat = true) {
        if (!queryText) return;
        setLoadingState(true);

        if (showInChat) {
            appendMessage('user', queryText);
        }
        const typingIndicator = appendTypingIndicator();

        try {
            const response = await fetch('/api/classify', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ query: queryText })
            });

            if (!response.ok) throw new Error('Error en el servidor');
            
            const data = await response.json();
            typingIndicator.remove();
            renderBotResponse(data);
        } catch (error) {
            console.error('Error:', error);
            typingIndicator.remove();
            appendMessage('bot', `❌ Error: ${error.message}`);
        } finally {
            setLoadingState(false);
        }
    }

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
                <div class="item-card glass-panel">
                    <div class="item-header">
                        <span class="badge success">Clasificado</span>
                        <span class="item-code">${i.codigo_exacto}</span>
                    </div>
                    <div class="item-body">
                        <h4>${i.nombre_producto}</h4>
                        <p class="hierarchy">${i.ruta_jerarquica.replace(/->/g, '›')}</p>
                        <div class="one-line-spec">
                            <span class="spec-label">Spec:</span>
                            <code>${i.one_line_desc || 'Generando...'}</code>
                        </div>
                    </div>
                </div>`;
            }).join('');

            contentHTML = `
                <div class="message-content" style="width: 100%; max-width: 800px;">
                    <p class="success-text">He procesado tu canasta. Aquí están los códigos listos para tu orden de compra:</p>
                    <div class="items-grid">
                        ${itemsList}
                    </div>
                    <button class="copy-all-btn glass-btn" onclick="copyAllSpecs()">📋 Copiar Especificaciones</button>
                </div>
            `;
        } else if (data.estado === 'Ambig\u00fcedad' || data.estado === 'Baja') {
            let itemsHTML = '';
            if (data.items && data.items.length > 0) {
                itemsHTML = data.items.map((item, itemIdx) => {
                    let fieldsHTML = '';
                    if (!item.atributos_faltantes || item.atributos_faltantes.length === 0) {
                        fieldsHTML = `
                            <div class="form-field" data-atributo="modelo_o_especificacion" data-tipo="texto">
                                <label>ESPECIFICACIÓN / DETALLES:</label>
                                <div class="text-input-container">
                                    <input type="text" placeholder="Ingrese el modelo o especificaciones adicionales..." class="field-text-input" onkeydown="if(event.key==='Enter') { event.preventDefault(); submitCardAclaraciones(this, '${item.sustantivo_principal}'); }" />
                                </div>
                            </div>`;
                    } else {
                        fieldsHTML = item.atributos_faltantes.map(field => {
                            let fieldHTML = '';
                            if (field.tipo_interfaz === 'botones' && field.opciones) {
                                let buttons = field.opciones.map(opt => {
                                    return `<button class="option-chip" data-value="${opt}" onclick="selectChip(this)">${opt}</button>`;
                                }).join('');
                                fieldHTML = `
                                    <div class="form-field" data-atributo="${field.atributo}" data-tipo="botones">
                                        <label>${field.atributo.replace(/_/g, ' ').toUpperCase()}:</label>
                                        <div class="option-chips-container">${buttons}</div>
                                    </div>`;
                            } else if (field.tipo_interfaz === 'texto') {
                                fieldHTML = `
                                    <div class="form-field" data-atributo="${field.atributo}" data-tipo="texto">
                                        <label>${field.atributo.replace(/_/g, ' ').toUpperCase()}:</label>
                                        <div class="text-input-container">
                                            <input type="text" placeholder="${field.placeholder || ''}" class="field-text-input" onkeydown="if(event.key==='Enter') { event.preventDefault(); submitCardAclaraciones(this, '${item.sustantivo_principal}'); }" />
                                        </div>
                                    </div>`;
                            }
                            return fieldHTML;
                        }).join('');
                    }

                    return `
                        <div class="clarification-card glass-panel" id="card-${itemIdx}">
                            <h4>${item.original_query}</h4>
                            ${(item.atributos_faltantes && item.atributos_faltantes.length > 0) ? '' : `<p class="item-question">${item.pregunta_aclaratoria}</p>`}
                            <div class="form-fields">${fieldsHTML}</div>
                            <div class="card-actions" style="margin-top: 15px; text-align: right;">
                                <button class="confirm-card-btn glass-btn" onclick="submitCardAclaraciones(this, '${item.sustantivo_principal}')">✓ Confirmar</button>
                            </div>
                        </div>`;
                }).join('');
            }

            contentHTML = `
                <div class="message-content" style="width: 100%; max-width: 600px;">
                    ${(data.items && data.items.length > 0) ? '' : `
                    <div class="question-card glass-panel alert">
                        <div class="icon-pulse">🤔</div>
                        <p>${data.mensaje.replace(/\n/g, '<br>')}</p>
                    </div>`}
                    ${itemsHTML}
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
