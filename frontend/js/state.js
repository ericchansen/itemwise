// Shared application state
export const API_URL = window.location.origin;
export const PAGE_SIZE = 50;

export let searchTimeout = null;
export let authMode = 'login';
export let activeInventoryId = null;
export let currentOffset = 0;
export let deferredPrompt = null;

export function setSearchTimeout(v) { searchTimeout = v; }
export function setAuthMode(v) { authMode = v; }
export function setActiveInventoryId(v) { activeInventoryId = v; }
export function setCurrentOffset(v) { currentOffset = v; }
export function setDeferredPrompt(v) { deferredPrompt = v; }
