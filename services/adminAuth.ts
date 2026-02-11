export type AdminRole = 'admin' | 'operator' | 'viewer';

const ADMIN_TOKEN_KEY = 'admin_token';
const ADMIN_ROLE_KEY = 'admin_role';

const storage = {
  get: (key: string) => {
    try {
      return sessionStorage.getItem(key) || localStorage.getItem(key);
    } catch {
      return null;
    }
  },
  set: (key: string, value: string, persist: boolean) => {
    try {
      if (persist) {
        localStorage.setItem(key, value);
      } else {
        sessionStorage.setItem(key, value);
      }
    } catch {
      // ignore
    }
  },
  remove: (key: string) => {
    try {
      sessionStorage.removeItem(key);
      localStorage.removeItem(key);
    } catch {
      // ignore
    }
  }
};

export const getAdminToken = (): string | null => storage.get(ADMIN_TOKEN_KEY);

export const getAdminRole = (): AdminRole | null => {
  const role = storage.get(ADMIN_ROLE_KEY) as AdminRole | null;
  return role || null;
};

export const setAdminSession = (token: string, role: AdminRole, persist = false) => {
  storage.set(ADMIN_TOKEN_KEY, token, persist);
  storage.set(ADMIN_ROLE_KEY, role, persist);
};

export const clearAdminSession = () => {
  storage.remove(ADMIN_TOKEN_KEY);
  storage.remove(ADMIN_ROLE_KEY);
};

export const canEditAdmin = (role?: AdminRole | null) => {
  const r = role || getAdminRole();
  return r === 'admin' || r === 'operator';
};

export const isAdminRole = (role?: AdminRole | null) => {
  const r = role || getAdminRole();
  return r === 'admin';
};
