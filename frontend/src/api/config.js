/** API base URL; empty string uses Vite dev proxy to the backend. */
export const API_BASE = (import.meta.env.VITE_API_URL || '').replace(/\/$/, '')
