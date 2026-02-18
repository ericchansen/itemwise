// Main app initialization
import { setCurrentOffset, deferredPrompt, setDeferredPrompt } from './state.js';
import {
    showAuthTab, handleAuth, logout, showForgotPassword, showLoginFromForgot,
    handleForgotPassword, handleResetPassword, checkAuth
} from './auth.js';
import { sendMessage, handleChatSubmit } from './chat.js';
import {
    loadInventory, loadLocations, debounceSearch, showAddItemModal,
    hideAddItemModal, handleAddItem, deleteItem, prevPage, nextPage
} from './items.js';
import {
    switchInventory, loadProfile, loadMembers, handleChangePassword,
    handleAddMember, handleSendExpirationReport
} from './settings.js';

// ===== Tab switching =====
function showTab(tab) {
    document.querySelectorAll('.tab-content').forEach(el => el.classList.add('hidden'));
    document.querySelectorAll('.tab-btn').forEach(el => {
        el.classList.remove('bg-white/10', 'text-white');
        el.classList.add('text-muted');
    });
    document.getElementById(`${tab}-tab`).classList.remove('hidden');
    const btn = document.getElementById(`tab-${tab}`);
    btn.classList.add('bg-white/10', 'text-white');
    btn.classList.remove('text-muted');
    if (tab === 'inventory') { loadInventory(); loadLocations(); }
    if (tab === 'settings') { loadProfile(); loadMembers(); }
    const selectorRow = document.getElementById('inventory-selector-row');
    if (tab === 'settings') {
        selectorRow.classList.add('hidden');
    } else {
        const selector = document.getElementById('inventory-selector');
        if (selector.options.length > 1) {
            selectorRow.classList.remove('hidden');
        }
    }
}

// ===== PWA =====
if ('serviceWorker' in navigator) {
    navigator.serviceWorker.register('/sw.js').catch(() => {});
}

window.addEventListener('beforeinstallprompt', (e) => {
    e.preventDefault();
    setDeferredPrompt(e);
    document.getElementById('pwa-install-banner').classList.remove('hidden');
});

function installPWA() {
    if (!deferredPrompt) return;
    deferredPrompt.prompt();
    deferredPrompt.userChoice.then(() => { setDeferredPrompt(null); });
    document.getElementById('pwa-install-banner').classList.add('hidden');
}

function dismissInstall() {
    document.getElementById('pwa-install-banner').classList.add('hidden');
}

// ===== Expose to window for HTML onclick handlers =====
window.showTab = showTab;
window.showAuthTab = showAuthTab;
window.handleAuth = handleAuth;
window.logout = logout;
window.showForgotPassword = showForgotPassword;
window.showLoginFromForgot = showLoginFromForgot;
window.handleForgotPassword = handleForgotPassword;
window.handleResetPassword = handleResetPassword;
window.sendMessage = sendMessage;
window.handleChatSubmit = handleChatSubmit;
window.loadInventory = loadInventory;
window.debounceSearch = debounceSearch;
window.showAddItemModal = showAddItemModal;
window.hideAddItemModal = hideAddItemModal;
window.handleAddItem = handleAddItem;
window._deleteItem = deleteItem;
window._resetOffsetAndLoad = function() { setCurrentOffset(0); loadInventory(); };
window.prevPage = prevPage;
window.nextPage = nextPage;
window.switchInventory = switchInventory;
window.handleChangePassword = handleChangePassword;
window.handleAddMember = handleAddMember;
window.handleSendExpirationReport = handleSendExpirationReport;
window.installPWA = installPWA;
window.dismissInstall = dismissInstall;

// ===== Init =====
checkAuth();
