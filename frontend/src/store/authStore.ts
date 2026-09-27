/** Session storage follows the user's persistence choice; refresh tokens rotate. */
import { create } from 'zustand';
import { persist, createJSONStorage } from 'zustand/middleware';
import { AuthState, User } from '../types';

interface AuthStore extends AuthState {
  login: (user: User, accessToken: string, refreshToken: string, rememberMe?: boolean) => void;
  rememberMe: boolean;
  logout: () => void;
  setTokens: (accessToken: string, refreshToken: string) => void;
  /** @deprecated usa setTokens */
  updateAccessToken: (token: string) => void;
}

export const useAuthStore = create<AuthStore>()(
  persist(
    (set, get) => ({
      rememberMe: true,
      user: null,
      accessToken: null,
      refreshToken: null,
      isAuthenticated: false,

      login: (user, accessToken, refreshToken, rememberMe = true) =>
        set({ user, accessToken, refreshToken, rememberMe, isAuthenticated: true }),

      setTokens: (accessToken, refreshToken) => set({ accessToken, refreshToken }),

      updateAccessToken: (accessToken) => set({ accessToken }),

      logout: () => {
        const { refreshToken } = get();
        if (refreshToken) {
          // Revocación best-effort: no bloquea el cierre de sesión local.
          const url = `${import.meta.env.VITE_API_BASE_URL || '/api/v1'}/auth/logout`;
          fetch(url, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ refresh_token: refreshToken }),
            keepalive: true,
          }).catch(() => undefined);
        }
        set({ user: null, accessToken: null, refreshToken: null, isAuthenticated: false });
      },
    }),
    {
      name: 'mi-jornada-auth',
      version: 2,
      storage: createJSONStorage(() => ({
        getItem: (name) => sessionStorage.getItem(name) ?? localStorage.getItem(name),
        setItem: (name, value) => {
          const remember = JSON.parse(value).state.rememberMe !== false;
          (remember ? sessionStorage : localStorage).removeItem(name);
          (remember ? localStorage : sessionStorage).setItem(name, value);
        },
        removeItem: (name) => { localStorage.removeItem(name); sessionStorage.removeItem(name); },
      })),
    },
  ),
);

window.addEventListener('storage', (event) => {
  if (event.key === 'mi-jornada-auth' && !sessionStorage.getItem('mi-jornada-auth')) {
    void useAuthStore.persist.rehydrate();
  }
});
