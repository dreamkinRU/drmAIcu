// Безопасная обёртка над localStorage с защитой от исключений.
// localStorage может быть недоступен (приватный режим, отключённое хранилище),
// поэтому все обращения завёрнуты в try/catch.

export const STORAGE_KEYS = {
  ACTIVE_TAB: 'drmActiveTab',
  SCROLL_PROJECT: 'drm_scroll_project',
  SCROLL_PATCHES: 'drm_scroll_patches',
} as const;

export const storage = {
  get(key: string): string | null {
    try {
      return localStorage.getItem(key);
    } catch {
      return null;
    }
  },
  set(key: string, value: string): void {
    try {
      localStorage.setItem(key, value);
    } catch {
      // Игнорируем ошибки хранилища.
    }
  },
  remove(key: string): void {
    try {
      localStorage.removeItem(key);
    } catch {
      // Игнорируем ошибки хранилища.
    }
  },
};
