// Items management
import { API_URL, PAGE_SIZE, currentOffset, setCurrentOffset, searchTimeout, setSearchTimeout } from './state.js';
import { authFetch } from './auth.js';
import { showConnectionError } from './utils.js';

export async function loadInventory() {
    const search = document.getElementById('search-input').value;
    const location = document.getElementById('location-filter').value;
    let url;
    if (search) {
        url = `${API_URL}/api/v1/search?q=${encodeURIComponent(search)}`;
        if (location) url += `&location=${encodeURIComponent(location)}`;
    } else {
        url = `${API_URL}/api/v1/items?limit=${PAGE_SIZE}&offset=${currentOffset}`;
        if (location) url += `&location=${encodeURIComponent(location)}`;
    }

    const list = document.getElementById('items-list');
    const empty = document.getElementById('empty-state');
    const pagination = document.getElementById('pagination-controls');
    list.innerHTML = '<div class="py-12 text-center pulsing"><span class="text-muted text-sm">Loading items...</span></div>';
    empty.classList.add('hidden');
    pagination.classList.add('hidden');

    try {
        const res = await authFetch(url);
        const data = await res.json();
        const items = data.items || data.results || [];

        if (!items.length && currentOffset === 0) { list.innerHTML = ''; empty.classList.remove('hidden'); return; }
        empty.classList.add('hidden');

        list.innerHTML = items.map(item => {
            // Calculate expiration display
            let expirationHTML = '';
            if (item.expiration_date) {
                const expiryDate = new Date(item.expiration_date);
                const today = new Date();
                today.setHours(0, 0, 0, 0);
                expiryDate.setHours(0, 0, 0, 0);
                const daysUntil = Math.ceil((expiryDate - today) / (1000 * 60 * 60 * 24));
                
                if (daysUntil < 0) {
                    expirationHTML = ` · <span class="expired">expired ${expiryDate.toLocaleDateString()}</span>`;
                } else if (daysUntil <= 7) {
                    expirationHTML = ` · <span class="expiring-soon">expires ${expiryDate.toLocaleDateString()}</span>`;
                } else {
                    expirationHTML = ` · expires ${expiryDate.toLocaleDateString()}`;
                }
            }
            
            return `
            <div class="group flex items-center gap-4 p-4 bg-surface border border-border rounded-xl hover:border-muted transition-all">
                <div class="w-10 h-10 bg-card rounded-lg flex items-center justify-center text-sm font-medium text-muted">${item.quantity}</div>
                <div class="flex-1 min-w-0">
                    <div class="font-medium truncate">${item.name}</div>
                    <div class="text-sm text-muted">${item.category}${item.location ? ' · ' + item.location : ''}${item.created_at ? ' · ' + new Date(item.created_at).toLocaleDateString() : ''}${expirationHTML}</div>
                </div>
                <button onclick="window._deleteItem(${item.id})" class="p-2 text-muted opacity-0 group-hover:opacity-100 hover:text-red-400 transition-all">
                    <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"/>
                    </svg>
                </button>
            </div>
        `;
        }).join('');

        // Show pagination for non-search results
        if (!search && data.total != null) {
            const start = currentOffset + 1;
            const end = Math.min(currentOffset + items.length, data.total);
            document.getElementById('pagination-info').textContent = `Showing ${start}–${end} of ${data.total} items`;
            document.getElementById('prev-btn').disabled = currentOffset === 0;
            document.getElementById('next-btn').disabled = currentOffset + PAGE_SIZE >= data.total;
            pagination.classList.remove('hidden');
        }
    } catch (e) {
        list.innerHTML = '<div class="py-12 text-center"><span class="text-red-400 text-sm">⚠️ Could not load items</span></div>';
        showConnectionError(e);
    }
}

export function prevPage() {
    setCurrentOffset(Math.max(0, currentOffset - PAGE_SIZE));
    loadInventory();
}

export function nextPage() {
    setCurrentOffset(currentOffset + PAGE_SIZE);
    loadInventory();
}

export async function loadLocations() {
    try {
        const res = await authFetch(`${API_URL}/api/v1/locations`);
        const data = await res.json();
        const select = document.getElementById('location-filter');
        const val = select.value;
        select.innerHTML = '<option value="">All locations</option>' +
            data.locations.map(l => `<option value="${l.name}">${l.name}</option>`).join('');
        select.value = val;
    } catch (e) { showConnectionError(e); }
}

export function debounceSearch() {
    clearTimeout(searchTimeout);
    setCurrentOffset(0);
    setSearchTimeout(setTimeout(loadInventory, 300));
}

export function showAddItemModal() {
    const modal = document.getElementById('add-item-modal');
    modal.classList.remove('hidden');
    modal.classList.add('flex');
}

export function hideAddItemModal() {
    const modal = document.getElementById('add-item-modal');
    modal.classList.add('hidden');
    modal.classList.remove('flex');
    ['item-name', 'item-category', 'item-location', 'item-expiration', 'item-description'].forEach(id => document.getElementById(id).value = '');
    document.getElementById('item-quantity').value = '1';
}

export async function handleAddItem(e) {
    e.preventDefault();
    const submitBtn = e.target.querySelector('button[type="submit"]');
    const expirationDate = document.getElementById('item-expiration').value;
    const item = {
        name: document.getElementById('item-name').value,
        quantity: parseInt(document.getElementById('item-quantity').value),
        category: document.getElementById('item-category').value,
        location: document.getElementById('item-location').value || null,
        description: document.getElementById('item-description').value || null,
        expiration_date: expirationDate || null
    };
    submitBtn.disabled = true;
    submitBtn.textContent = 'Adding...';
    try {
        const res = await authFetch(`${API_URL}/api/v1/items`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(item)
        });
        if (res.ok) { hideAddItemModal(); loadInventory(); loadLocations(); }
    } catch (e) {
        showConnectionError(e);
    } finally {
        submitBtn.disabled = false;
        submitBtn.textContent = 'Add';
    }
}

export async function deleteItem(id) {
    if (!confirm('Delete this item?')) return;
    try {
        const res = await authFetch(`${API_URL}/api/v1/items/${id}`, { method: 'DELETE' });
        if (res.ok) loadInventory();
    } catch (e) { showConnectionError(e); }
}
