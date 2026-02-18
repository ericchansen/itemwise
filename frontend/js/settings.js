// Settings and admin functionality
import { API_URL, activeInventoryId, setActiveInventoryId, setCurrentOffset } from './state.js';
import { authFetch } from './auth.js';
import { loadInventory, loadLocations } from './items.js';

export async function loadInventories() {
    try {
        const res = await authFetch(`${API_URL}/api/v1/inventories`);
        const data = await res.json();
        const sel = document.getElementById('inventory-selector');
        sel.innerHTML = data.inventories.map(inv =>
            `<option value="${inv.id}" ${inv.id === activeInventoryId ? 'selected' : ''}>${inv.name}</option>`
        ).join('');
        if (data.inventories.length > 0) {
            if (!activeInventoryId || !data.inventories.find(inv => inv.id === activeInventoryId)) {
                setActiveInventoryId(parseInt(data.inventories[0].id));
            }
        }
        if (data.inventories.length > 1) {
            document.getElementById('inventory-selector-row').classList.remove('hidden');
        } else {
            document.getElementById('inventory-selector-row').classList.add('hidden');
        }
    } catch (e) { console.error('Failed to load inventories', e); }
}

export function switchInventory() {
    setActiveInventoryId(parseInt(document.getElementById('inventory-selector').value));
    setCurrentOffset(0);
    loadInventory();
    loadLocations();
}

export async function loadProfile() {
    try {
        const res = await authFetch(`${API_URL}/api/v1/auth/me`);
        const data = await res.json();
        document.getElementById('profile-email').textContent = data.email;
    } catch(e) { console.error('Failed to load profile', e); }
}

export async function handleChangePassword(event) {
    event.preventDefault();
    const fb = document.getElementById('password-feedback');
    const newPw = document.getElementById('new-password').value;
    const confirmPw = document.getElementById('confirm-password').value;
    const submitBtn = event.target.querySelector('button[type="submit"]');

    if (newPw !== confirmPw) {
        fb.className = 'mt-3 px-4 py-2.5 rounded-lg text-sm bg-red-500/10 border border-red-500/20 text-red-400';
        fb.textContent = 'New passwords do not match';
        return;
    }

    submitBtn.disabled = true;
    submitBtn.textContent = 'Saving...';
    try {
        const res = await authFetch(`${API_URL}/api/v1/auth/password`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                current_password: document.getElementById('current-password').value,
                new_password: newPw
            })
        });
        if (res.ok) {
            fb.className = 'mt-3 px-4 py-2.5 rounded-lg text-sm bg-green-500/10 border border-green-500/20 text-green-400';
            fb.textContent = 'Password updated successfully';
            event.target.reset();
        } else {
            const err = await res.json();
            fb.className = 'mt-3 px-4 py-2.5 rounded-lg text-sm bg-red-500/10 border border-red-500/20 text-red-400';
            fb.textContent = typeof err.detail === 'string' ? err.detail : Array.isArray(err.detail) ? err.detail.map(d => d.msg || JSON.stringify(d)).join(', ') : 'Failed to update password';
        }
    } catch(e) {
        fb.className = 'mt-3 px-4 py-2.5 rounded-lg text-sm bg-red-500/10 border border-red-500/20 text-red-400';
        fb.textContent = 'Network error';
    } finally {
        submitBtn.disabled = false;
        submitBtn.textContent = 'Update Password';
    }
}

export async function loadMembers() {
    if (!activeInventoryId) return;
    try {
        const res = await authFetch(`${API_URL}/api/v1/inventories/${activeInventoryId}/members`);
        const data = await res.json();
        document.getElementById('members-list').innerHTML = data.members.map(m => `
            <div class="flex items-center justify-between p-3 bg-card border border-border rounded-lg">
                <span class="text-sm">${m.email || 'Unknown'}</span>
                <span class="text-xs text-muted">${m.joined_at ? new Date(m.joined_at).toLocaleDateString() : ''}</span>
            </div>
        `).join('') || '<p class="text-muted text-sm">No members yet</p>';
    } catch (e) { console.error(e); }
}

export async function handleAddMember(e) {
    e.preventDefault();
    const email = document.getElementById('member-email').value;
    const fb = document.getElementById('member-feedback');
    const submitBtn = e.target.querySelector('button[type="submit"]');
    if (!activeInventoryId) {
        await loadInventories();
        if (!activeInventoryId) {
            fb.textContent = 'No inventory selected';
            fb.className = 'mt-3 px-4 py-2.5 rounded-lg text-sm bg-red-500/10 border border-red-500/20 text-red-400';
            fb.classList.remove('hidden');
            return;
        }
    }
    submitBtn.disabled = true;
    submitBtn.textContent = 'Inviting...';
    try {
        const res = await authFetch(`${API_URL}/api/v1/inventories/${activeInventoryId}/members`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ email })
        });
        if (res.ok) {
            const data = await res.json();
            if (data.status === 'invite_failed') {
                fb.textContent = `Could not send invite email to ${email}`;
                fb.className = 'mt-3 px-4 py-2.5 rounded-lg text-sm bg-red-500/10 border border-red-500/20 text-red-400';
            } else if (data.status === 'added' && data.email_warning) {
                fb.textContent = `Added ${email} but notification email failed`;
                fb.className = 'mt-3 px-4 py-2.5 rounded-lg text-sm bg-amber-500/10 border border-amber-500/20 text-amber-400';
                loadMembers();
            } else if (data.status === 'invited') {
                fb.textContent = `Invite sent to ${email}`;
                fb.className = 'mt-3 px-4 py-2.5 rounded-lg text-sm bg-green-500/10 border border-green-500/20 text-green-400';
            } else {
                fb.textContent = `Added ${email}`;
                fb.className = 'mt-3 px-4 py-2.5 rounded-lg text-sm bg-green-500/10 border border-green-500/20 text-green-400';
                loadMembers();
            }
            fb.classList.remove('hidden');
            document.getElementById('member-email').value = '';
        } else {
            const err = await res.json();
            fb.textContent = typeof err.detail === 'string' ? err.detail : Array.isArray(err.detail) ? err.detail.map(d => d.msg || JSON.stringify(d)).join(', ') : 'Failed to add member';
            fb.className = 'mt-3 px-4 py-2.5 rounded-lg text-sm bg-red-500/10 border border-red-500/20 text-red-400';
            fb.classList.remove('hidden');
        }
    } catch (e) {
        fb.textContent = 'Connection error';
        fb.className = 'mt-3 px-4 py-2.5 rounded-lg text-sm bg-red-500/10 border border-red-500/20 text-red-400';
        fb.classList.remove('hidden');
    } finally {
        submitBtn.disabled = false;
        submitBtn.textContent = 'Invite';
    }
}

export async function handleSendExpirationReport() {
    const fb = document.getElementById('expiration-feedback');
    const btn = document.getElementById('expiration-report-btn');
    btn.disabled = true;
    btn.textContent = 'Sending...';
    try {
        const res = await authFetch(`${API_URL}/api/v1/notifications/expiration-digest`, { method: 'POST' });
        const data = await res.json();
        if (res.ok) {
            if (data.status === 'no_items') {
                fb.textContent = 'No items expiring soon — nothing to report.';
                fb.className = 'mt-3 px-4 py-2.5 rounded-lg text-sm bg-blue-500/10 border border-blue-500/20 text-blue-400';
            } else {
                fb.textContent = `Report sent! ${data.item_count} expiring item(s) emailed to you.`;
                fb.className = 'mt-3 px-4 py-2.5 rounded-lg text-sm bg-green-500/10 border border-green-500/20 text-green-400';
            }
        } else {
            const detail = data.detail || 'Failed to send report';
            fb.textContent = typeof detail === 'string' ? detail : 'Failed to send report';
            fb.className = 'mt-3 px-4 py-2.5 rounded-lg text-sm bg-red-500/10 border border-red-500/20 text-red-400';
        }
    } catch (e) {
        fb.textContent = 'Network error';
        fb.className = 'mt-3 px-4 py-2.5 rounded-lg text-sm bg-red-500/10 border border-red-500/20 text-red-400';
    }
    fb.classList.remove('hidden');
    btn.disabled = false;
    btn.textContent = 'Send Expiration Report';
}
