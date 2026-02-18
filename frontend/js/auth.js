// Authentication logic
import { API_URL, authMode, activeInventoryId, setAuthMode, setActiveInventoryId } from './state.js';
import { showAlert } from './utils.js';
import { loadInventories } from './settings.js';

export function getRefreshToken() { return localStorage.getItem('refreshToken'); }

export function getCsrfToken() {
    const match = document.cookie.match(/csrf_token=([^;]+)/);
    return match ? match[1] : null;
}

export async function authFetch(url, opts = {}) {
    opts.credentials = 'include';
    const csrfToken = getCsrfToken();
    if (csrfToken) {
        opts.headers = { ...opts.headers, 'X-CSRF-Token': csrfToken };
    }
    if (activeInventoryId) {
        opts.headers = { ...opts.headers, 'X-Inventory-Id': activeInventoryId.toString() };
    }
    let res = await fetch(url, opts);
    if (res.status === 401 && getRefreshToken()) {
        const refreshed = await tryRefresh();
        if (refreshed) {
            // Re-capture CSRF token after refresh (cookie may have changed)
            const newCsrfToken = getCsrfToken();
            if (newCsrfToken) {
                opts.headers = { ...opts.headers, 'X-CSRF-Token': newCsrfToken };
            }
            res = await fetch(url, opts);
        } else { logout(); }
    }
    if (res.status === 401) { logout(); throw new Error('Unauthorized'); }
    return res;
}

export async function tryRefresh() {
    try {
        const res = await fetch(`${API_URL}/api/v1/auth/refresh`, {
            method: 'POST',
            credentials: 'include',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ refresh_token: getRefreshToken() })
        });
        if (!res.ok) return false;
        return true;
    } catch { return false; }
}

export function showAuthTab(tab) {
    setAuthMode(tab);
    document.getElementById('auth-tab-login').classList.toggle('bg-white/10', tab === 'login');
    document.getElementById('auth-tab-login').classList.toggle('text-white', tab === 'login');
    document.getElementById('auth-tab-login').classList.toggle('text-muted', tab !== 'login');
    document.getElementById('auth-tab-register').classList.toggle('bg-white/10', tab === 'register');
    document.getElementById('auth-tab-register').classList.toggle('text-white', tab === 'register');
    document.getElementById('auth-tab-register').classList.toggle('text-muted', tab !== 'register');
    document.getElementById('auth-submit').textContent = tab === 'login' ? 'Login' : 'Register';
    document.getElementById('auth-error').classList.add('hidden');
}

export async function handleAuth(e) {
    e.preventDefault();
    const email = document.getElementById('auth-email').value;
    const password = document.getElementById('auth-password').value;
    const errorEl = document.getElementById('auth-error');
    const submitBtn = document.getElementById('auth-submit');
    const origText = submitBtn.textContent;
    errorEl.classList.add('hidden');
    submitBtn.disabled = true;
    submitBtn.textContent = 'Loading...';

    try {
        let res;
        if (authMode === 'register') {
            res = await fetch(`${API_URL}/api/v1/auth/register`, {
                method: 'POST',
                credentials: 'include',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ email, password })
            });
        } else {
            const formData = new URLSearchParams();
            formData.append('username', email);
            formData.append('password', password);
            res = await fetch(`${API_URL}/api/v1/auth/login`, {
                method: 'POST',
                credentials: 'include',
                headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
                body: formData
            });
        }

        if (!res.ok) {
            const err = await res.json();
            showAlert(errorEl, err.detail || 'Authentication failed');
            return;
        }

        const data = await res.json();
        localStorage.setItem('refreshToken', data.refresh_token);
        showApp();
    } catch {
        showAlert(errorEl, 'Connection error');
    } finally {
        submitBtn.disabled = false;
        submitBtn.textContent = origText;
    }
}

export function logout() {
    fetch(`${API_URL}/api/v1/auth/logout`, { method: 'POST', credentials: 'include' }).catch(() => {});
    localStorage.removeItem('refreshToken');
    setActiveInventoryId(null);
    // Clear DOM state
    document.getElementById('chat-messages').innerHTML = '';
    document.getElementById('inventory-selector').innerHTML = '';
    document.getElementById('inventory-selector-row').classList.add('hidden');
    const itemsList = document.getElementById('items-list');
    if (itemsList) itemsList.innerHTML = '';
    const membersList = document.getElementById('members-list');
    if (membersList) membersList.innerHTML = '';
    const memberFeedback = document.getElementById('member-feedback');
    if (memberFeedback) { memberFeedback.textContent = ''; memberFeedback.classList.add('hidden'); }
    showAuthScreen();
}

export function showApp() {
    document.getElementById('auth-screen').classList.add('hidden');
    document.getElementById('app-tabs').classList.remove('hidden');
    document.getElementById('logout-btn').classList.remove('hidden');
    document.querySelectorAll('main').forEach(el => el.classList.remove('hidden'));
    loadInventories();
}

export function showAuthScreen() {
    document.getElementById('auth-screen').classList.remove('hidden');
    document.getElementById('app-tabs').classList.add('hidden');
    document.getElementById('logout-btn').classList.add('hidden');
    document.getElementById('inventory-selector-row').classList.add('hidden');
    document.querySelectorAll('main').forEach(el => el.classList.add('hidden'));
}

export function showForgotPassword() {
    document.getElementById('auth-login-register').classList.add('hidden');
    document.getElementById('auth-forgot-password').classList.remove('hidden');
    document.getElementById('auth-reset-password').classList.add('hidden');
    document.getElementById('forgot-error').classList.add('hidden');
    document.getElementById('forgot-success').classList.add('hidden');
}

export function showLoginFromForgot() {
    document.getElementById('auth-login-register').classList.remove('hidden');
    document.getElementById('auth-forgot-password').classList.add('hidden');
    document.getElementById('auth-reset-password').classList.add('hidden');
}

export function showResetPasswordForm() {
    document.getElementById('auth-login-register').classList.add('hidden');
    document.getElementById('auth-forgot-password').classList.add('hidden');
    document.getElementById('auth-reset-password').classList.remove('hidden');
    document.getElementById('reset-error').classList.add('hidden');
}

export async function handleForgotPassword(e) {
    e.preventDefault();
    const email = document.getElementById('forgot-email').value;
    const errorEl = document.getElementById('forgot-error');
    const successEl = document.getElementById('forgot-success');
    const submitBtn = e.target.querySelector('button[type="submit"]');
    errorEl.classList.add('hidden');
    successEl.classList.add('hidden');
    submitBtn.disabled = true;
    submitBtn.textContent = 'Sending...';
    try {
        const res = await fetch(`${API_URL}/api/v1/auth/forgot-password`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ email })
        });
        const data = await res.json();
        showAlert(successEl, 'If an account exists with that email, a reset link has been sent.');
    } catch {
        showAlert(errorEl, 'Connection error. Please try again.');
    } finally {
        submitBtn.disabled = false;
        submitBtn.textContent = 'Send Reset Link';
    }
}

export async function handleResetPassword(e) {
    e.preventDefault();
    const password = document.getElementById('reset-password').value;
    const confirm = document.getElementById('reset-password-confirm').value;
    const errorEl = document.getElementById('reset-error');
    const submitBtn = e.target.querySelector('button[type="submit"]');
    errorEl.classList.add('hidden');
    if (password !== confirm) {
        showAlert(errorEl, 'Passwords do not match');
        return;
    }
    const params = new URLSearchParams(window.location.search);
    const token = params.get('reset_token');
    submitBtn.disabled = true;
    submitBtn.textContent = 'Resetting...';
    try {
        const res = await fetch(`${API_URL}/api/v1/auth/reset-password`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ token, new_password: password })
        });
        if (!res.ok) {
            const err = await res.json();
            showAlert(errorEl, err.detail || 'Reset failed');
            return;
        }
        window.history.replaceState({}, '', window.location.pathname);
        document.getElementById('auth-reset-password').classList.add('hidden');
        document.getElementById('auth-login-register').classList.remove('hidden');
        const successEl = document.getElementById('auth-success');
        showAlert(successEl, 'Password reset successfully. Please log in.');
    } catch {
        showAlert(errorEl, 'Connection error. Please try again.');
    } finally {
        submitBtn.disabled = false;
        submitBtn.textContent = 'Reset Password';
    }
}

export async function checkAuth() {
    const urlParams = new URLSearchParams(window.location.search);
    if (urlParams.has('reset_token')) {
        showAuthScreen();
        showResetPasswordForm();
    } else {
        try {
            const r = await fetch(`${API_URL}/api/v1/auth/me`, { credentials: 'include' });
            if (r.ok) showApp(); else showAuthScreen();
        } catch { showAuthScreen(); }
    }
}
