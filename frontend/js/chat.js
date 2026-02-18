// Chat functionality
import { API_URL } from './state.js';
import { authFetch } from './auth.js';
import { renderMarkdown } from './utils.js';

export function addMessage(content, isUser = false) {
    const container = document.getElementById('chat-messages');
    const div = document.createElement('div');
    div.className = `message-enter ${isUser ? 'text-right' : ''}`;
    const rendered = isUser ? content : renderMarkdown(content);
    div.innerHTML = `<div class="inline-block max-w-[85%] px-4 py-2.5 rounded-2xl ${isUser ? 'bg-accent text-white' : 'bg-card border border-border text-white/90'}">${rendered}</div>`;
    container.appendChild(div);
    container.scrollTop = container.scrollHeight;
}

function addConfirmation(actionId, description) {
    const container = document.getElementById('chat-messages');
    const div = document.createElement('div');
    div.className = 'message-enter';
    div.id = `confirm-${actionId}`;
    div.innerHTML = `<div class="inline-block max-w-[85%] px-4 py-3 rounded-2xl bg-yellow-900/30 border border-yellow-700/50 text-white/90">
        <p class="text-sm mb-2">⚠️ ${description}</p>
        <button onclick="window._confirmAction('${actionId}', true)" class="px-3 py-1 text-sm rounded-lg bg-red-600 hover:bg-red-500 text-white mr-2">Confirm</button>
        <button onclick="window._confirmAction('${actionId}', false)" class="px-3 py-1 text-sm rounded-lg bg-surface border border-border text-muted hover:text-white">Cancel</button>
    </div>`;
    container.appendChild(div);
    container.scrollTop = container.scrollHeight;
}

async function confirmAction(actionId, confirmed) {
    const confirmDiv = document.getElementById(`confirm-${actionId}`);
    if (confirmDiv) {
        confirmDiv.querySelectorAll('button').forEach(b => b.disabled = true);
    }
    try {
        const res = await authFetch(`${API_URL}/api/v1/chat/confirm`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ action_id: actionId, confirmed })
        });
        const data = await res.json();
        if (res.ok) {
            addMessage(data.response.replace(/\n/g, '<br>'));
        } else {
            addMessage(data.detail || 'Action failed.');
        }
    } catch (e) {
        if (e.message !== 'Unauthorized') addMessage('Connection error. Try again.');
    }
    if (confirmDiv) confirmDiv.remove();
}

// Expose to global scope for inline onclick handlers
window._confirmAction = confirmAction;

export async function sendMessage(text) {
    if (!text.trim()) return;
    const sendBtn = document.getElementById('chat-send-btn');
    const chatInput = document.getElementById('chat-input');
    sendBtn.disabled = true;
    sendBtn.innerHTML = '<span class="spinner"></span>';
    chatInput.disabled = true;
    addMessage(text, true);
    chatInput.value = '';
    try {
        const res = await authFetch(`${API_URL}/api/v1/chat`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ message: text })
        });
        const data = await res.json();
        addMessage(data.response.replace(/\n/g, '<br>'));
        if (data.pending_action) {
            addConfirmation(data.pending_action.action_id, data.pending_action.description);
        }
    } catch (e) {
        if (e.message !== 'Unauthorized') addMessage('Connection error. Try again.');
    } finally {
        sendBtn.disabled = false;
        sendBtn.innerHTML = '<svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M5 12h14M12 5l7 7-7 7"/></svg>';
        chatInput.disabled = false;
        chatInput.focus();
    }
}

export function handleChatSubmit(e) {
    e.preventDefault();
    sendMessage(document.getElementById('chat-input').value);
}
