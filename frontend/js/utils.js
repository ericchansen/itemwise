// Shared utility functions

export function showAlert(el, msg, autoDismissMs = 8000) {
    el.innerHTML = `<span>${msg}</span><span class="alert-close" onclick="window._dismissAlert(this.parentElement)">&times;</span>`;
    el.classList.remove('hidden', 'hiding');
    el.classList.add('alert-banner');
    clearTimeout(el._dismissTimer);
    if (autoDismissMs > 0) {
        el._dismissTimer = setTimeout(() => dismissAlert(el), autoDismissMs);
    }
}

export function dismissAlert(el) {
    clearTimeout(el._dismissTimer);
    el.classList.add('hiding');
    setTimeout(() => { el.classList.add('hidden'); el.classList.remove('hiding', 'alert-banner'); }, 300);
}

export function renderMarkdown(text) {
    return text
        .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
        .replace(/\*(.+?)\*/g, '<em>$1</em>')
        .replace(/\n/g, '<br>');
}

export function showConnectionError(error) {
    if (error?.message === 'Unauthorized') return;
    const el = document.getElementById('connection-error');
    if (!el) return;
    const msg = (error instanceof TypeError)
        ? "⚠️ Can't connect to server. Please try again later."
        : "⚠️ Something went wrong. Please try again later.";
    showAlert(el, msg);
}

// Expose dismissAlert globally for onclick in showAlert
window._dismissAlert = dismissAlert;
