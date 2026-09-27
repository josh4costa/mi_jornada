/**
 * src/store/authStore.ts  —  CORREGIDO
 *
 * - setTokens(): necesario porque el backend ahora rota el refresh token.
 * - logout() avisa al backend para revocar la sesión del servidor (antes el refresh
 *   token seguía siendo válido 30 días después de "cerrar sesión").
 * - Se versiona el storage para no arrastrar sesiones con el formato viejo.
 *
 * NOTA: los tokens viven en localStorage (accesible por JS). Es aceptable para una
 * PWA interna, pero si más adelante se expone a internet público conviene mover el
 * refresh token a una cookie httpOnly + SameSite=Strict.
 */
import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import { AuthState, User } from '../types';

interface AuthStore extends AuthState {
  login: (user: User, accessToken: string, refreshToken: string) => void;
  logout: () => void;
  setTokens: (accessToken: string, refreshToken: string) => void;
  /** @deprecated usa setTokens */
  updateAccessToken: (token: string) => void;
}

export const useAuthStore = create<AuthStore>()(
  persist(
    (set, get) => ({
      user: null,
      accessToken: null,
      refreshToken: null,
      isAuthenticated: false,

      login: (user, accessToken, refreshToken) =>
        set({ user, accessToken, refreshToken, isAuthenticated: true }),

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
    },
  ),
);
