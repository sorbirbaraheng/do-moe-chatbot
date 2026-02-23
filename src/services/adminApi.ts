import { getAdminToken } from './adminAuth';

const normalizeBase = (base: string) => base.replace(/\/$/, '');

const isPrivateHost = (host: string) => {
  return host === 'localhost' || host.startsWith('127.') || host.startsWith('192.168.') || host.startsWith('10.') || /^172\.(1[6-9]|2\d|3[0-1])\./.test(host);
};

export const getBackendBaseUrl = (port = 5001) => {
  if (typeof window === 'undefined') return `http://127.0.0.1:${port}`;
  const currentPort = window.location.port;
  // Docker nginx (port 3001/80) — use relative URL, nginx proxies /api/ → backend
  if (currentPort === '3001' || currentPort === '80' || currentPort === '') return '';
  const envUrl = (import.meta as any)?.env?.VITE_BACKEND_URL || (import.meta as any)?.env?.VITE_FLASK_API_URL;
  if (envUrl) return normalizeBase(envUrl);
  const host = window.location.hostname;
  if (host === 'localhost' || host === '127.0.0.1') return `http://127.0.0.1:${port}`;
  return `http://${host}:${port}`;
};

const withAuth = (headers: HeadersInit = {}) => {
  const token = getAdminToken();
  if (!token) return headers;
  return { ...headers, Authorization: `Bearer ${token}` };
};

export const adminLogin = async (password: string): Promise<{ success: true; token: string; role: 'admin' | 'operator' | 'viewer' } | { success: false; error: any }> => {
  const url = `${getBackendBaseUrl()}/api/admin/login`;
  const response = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ password })
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok || !data?.success) {
    return { success: false, error: data?.error || `HTTP ${response.status}` };
  }
  return data as { success: true; token: string; role: 'admin' | 'operator' | 'viewer' };
};

export const fetchAdminConfig = async () => {
  const url = `${getBackendBaseUrl()}/api/admin/config`;
  const response = await fetch(url, { headers: withAuth() });
  const data = await response.json().catch(() => ({}));
  if (!response.ok || !data?.success) {
    throw new Error(data?.error || `HTTP ${response.status}`);
  }
  return data.config;
};

export const fetchPublicConfig = async () => {
  const url = `${getBackendBaseUrl()}/api/config/public`;
  const response = await fetch(url);
  const data = await response.json().catch(() => ({}));
  if (!response.ok || !data?.success) {
    throw new Error(data?.error || `HTTP ${response.status}`);
  }
  return data.config;
};

export const updateAdminConfig = async (payload: any) => {
  const url = `${getBackendBaseUrl()}/api/admin/config`;
  const response = await fetch(url, {
    method: 'POST',
    headers: withAuth({ 'Content-Type': 'application/json' }),
    body: JSON.stringify(payload)
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok || !data?.success) {
    throw new Error(data?.error || `HTTP ${response.status}`);
  }
  return data;
};

export const fetchAuditLogs = async (limit = 50, cursor?: string) => {
  const params = new URLSearchParams();
  params.set('limit', String(limit));
  if (cursor) params.set('cursor', cursor);
  const url = `${getBackendBaseUrl()}/api/admin/audit?${params.toString()}`;
  const response = await fetch(url, { headers: withAuth() });
  const data = await response.json().catch(() => ({}));
  if (!response.ok || !data?.success) {
    throw new Error(data?.error || `HTTP ${response.status}`);
  }
  return data as { success: true; logs: any[]; nextCursor?: string; hasMore?: boolean };
};

export const adminFetch = async (path: string, init: RequestInit = {}) => {
  const base = getBackendBaseUrl();
  const url = `${base}${path.startsWith('/') ? '' : '/'}${path}`;
  const headers = withAuth(init.headers || {});
  return fetch(url, { ...init, headers });
};
