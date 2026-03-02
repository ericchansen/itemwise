// Chat functionality
import { API_URL } from './state.js';
import { authFetch } from './auth.js';
import { renderMarkdown, showConnectionError } from './utils.js';

// Track selected image for upload
let _pendingImage = null;
// Track identified items from last image analysis
let _identifiedItems = null;

// Defensively re-enable chat input controls after a send completes
function resetChatInput() {
    const sendBtn = document.getElementById('chat-send-btn');
    const chatInput = document.getElementById('chat-input');
    sendBtn.disabled = false;
    sendBtn.innerHTML = '<svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M5 12h14M12 5l7 7-7 7"/></svg>';
    chatInput.disabled = false;
    chatInput.focus();
    // Safety net: guarantee re-enable on next tick in case a concurrent
    // DOM update (e.g. clearImagePreview) interferes with this frame
    setTimeout(() => {
        sendBtn.disabled = false;
        chatInput.disabled = false;
    }, 0);
}

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
        showConnectionError(e);
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
        showConnectionError(e);
    } finally {
        resetChatInput();
    }
}

export function handleChatSubmit(e) {
    e.preventDefault();
    if (_pendingImage) {
        sendImageMessage();
    } else {
        sendMessage(document.getElementById('chat-input').value);
    }
}

export function handleImageSelect(e) {
    const file = e.target.files[0];
    if (!file) return;

    const maxSize = 10 * 1024 * 1024;
    if (file.size > maxSize) {
        addMessage('Image too large. Maximum size is 10 MB.');
        return;
    }

    _pendingImage = file;
    const reader = new FileReader();
    reader.onload = (ev) => {
        const preview = document.getElementById('image-preview');
        preview.src = ev.target.result;
        document.getElementById('image-preview-container').classList.remove('hidden');
    };
    reader.readAsDataURL(file);

    document.getElementById('chat-input').placeholder = 'Add a note (optional)...';
    document.getElementById('chat-input').focus();
}

export function clearImagePreview() {
    _pendingImage = null;
    document.getElementById('image-preview-container').classList.add('hidden');
    document.getElementById('image-preview').src = '';
    document.getElementById('image-input').value = '';
    document.getElementById('chat-input').placeholder = 'Ask anything...';
}

async function sendImageMessage() {
    const sendBtn = document.getElementById('chat-send-btn');
    const chatInput = document.getElementById('chat-input');
    const noteText = chatInput.value.trim();

    sendBtn.disabled = true;
    sendBtn.innerHTML = '<span class="spinner"></span>';
    chatInput.disabled = true;

    // Show image in chat
    const reader = new FileReader();
    reader.onload = (ev) => {
        const container = document.getElementById('chat-messages');
        const div = document.createElement('div');
        div.className = 'message-enter text-right';
        div.innerHTML = `<div class="inline-block max-w-[85%]">
            <img src="${ev.target.result}" class="max-h-48 rounded-2xl border border-border mb-1" alt="Uploaded">
            ${noteText ? `<div class="px-4 py-2 rounded-2xl bg-accent text-white text-sm">${noteText}</div>` : ''}
        </div>`;
        container.appendChild(div);
        container.scrollTop = container.scrollHeight;
    };
    reader.readAsDataURL(_pendingImage);

    chatInput.value = '';

    const formData = new FormData();
    formData.append('image', _pendingImage);
    if (noteText) formData.append('message', noteText);

    try {
        const res = await authFetch(`${API_URL}/api/v1/chat/image`, {
            method: 'POST',
            body: formData,
        });
        const data = await res.json();
        if (res.ok && data.items && data.items.length > 0) {
            _identifiedItems = data.items;
            addMessage(data.response);
            showAddFromImagePrompt(data.items);
        } else {
            addMessage(data.response || data.detail || 'Could not analyze image.');
        }
    } catch (e) {
        showConnectionError(e);
    } finally {
        clearImagePreview();
        resetChatInput();
    }
}

function showAddFromImagePrompt(items) {
    const container = document.getElementById('chat-messages');
    const div = document.createElement('div');
    div.className = 'message-enter';
    div.id = 'image-add-prompt';
    div.innerHTML = `<div class="inline-block max-w-[85%] px-4 py-3 rounded-2xl bg-card border border-border text-white/90">
        <p class="text-sm mb-2">Where should I add these items?</p>
        <div class="flex flex-wrap gap-2 mb-2">
            <input type="text" id="image-location-input" placeholder="e.g., Freezer, Pantry..." 
                   class="flex-1 min-w-[150px] px-3 py-1.5 text-sm bg-surface border border-border rounded-lg text-white placeholder-muted focus:border-accent transition-all">
        </div>
        <div class="flex gap-2">
            <button onclick="window._addImageItems()" class="px-3 py-1.5 text-sm rounded-lg bg-accent hover:bg-accent/80 text-white">Add items</button>
            <button onclick="window._dismissImagePrompt()" class="px-3 py-1.5 text-sm rounded-lg bg-surface border border-border text-muted hover:text-white">Skip</button>
        </div>
    </div>`;
    container.appendChild(div);
    container.scrollTop = container.scrollHeight;
    document.getElementById('image-location-input').focus();
}

async function addImageItems() {
    const locationInput = document.getElementById('image-location-input');
    const location = locationInput ? locationInput.value.trim() : '';
    if (!location) {
        locationInput.classList.add('border-red-500');
        locationInput.placeholder = 'Please enter a location';
        return;
    }
    if (!_identifiedItems || _identifiedItems.length === 0) return;

    const prompt = document.getElementById('image-add-prompt');
    if (prompt) {
        prompt.querySelectorAll('button').forEach(b => b.disabled = true);
    }

    try {
        const res = await authFetch(`${API_URL}/api/v1/chat/image/add`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ items: _identifiedItems, location }),
        });
        const data = await res.json();
        if (res.ok) {
            addMessage(data.response);
        } else {
            addMessage(data.detail || 'Failed to add items.');
        }
    } catch (e) {
        showConnectionError(e);
    }
    _identifiedItems = null;
    if (prompt) prompt.remove();
}

function dismissImagePrompt() {
    _identifiedItems = null;
    const prompt = document.getElementById('image-add-prompt');
    if (prompt) prompt.remove();
    addMessage('No items added.');
}

// Expose image functions to global scope
window._addImageItems = addImageItems;
window._dismissImagePrompt = dismissImagePrompt;
