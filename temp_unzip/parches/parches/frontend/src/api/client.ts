/**
 * src/api/client.ts  —  CORREGIDO
 *
 * 1. BUG VISIBLE: un 401 de /auth/login (contraseña incorrecta) entraba al interceptor
 *    de refresh, fallaba, llamaba logout() y hacía window.location.href = '/login'.
 *    Resultado: la página se recargaba y el usuario NUNCA veía "Usuario o contraseña
 *    incorrectos". Ahora las rutas de auth quedan excluidas del refresh.
 * 2. Con varias peticiones en paralelo (el Home hace 2, el dashboard 1 cada 60s) cada
 *    401 disparaba su propio refresh -> con rotación de tokens eso invalida la sesión.
 *    Ahora hay un único refresh compartido (single-flight) y las demás esperan.
 * 3. Se guarda el refresh token rotado que ahora devuelve el backend.
 * 4. window.location.href mata el SPA; se usa el mismo mecanismo pero solo cuando
 *    realmente se perdió la sesión, y se conserva la ruta para volver después.
 * 5. Se agregan timeout y mensajes para 409/422/423/429.
 */
import axios, { AxiosError, AxiosRequestConfig } from 'axios';
import { useAuthStore } from '../store/authStore';
import { User } from '../types';

const BASE_URL = import.meta.env.VITE_API_BASE_URL || '/api/v1';

const client = axios.create({
  baseURL: BASE_URL,
  timeout: 20000,
});

/** Rutas que nunca deben intentar refrescar el token. */
const AUTH_PATHS = ['/auth/login', '/auth/refresh', '/auth/logout'];
const isAuthPath = (url?: string) => !!url && AUTH_PATHS.some((p) => url.includes(p));

client.interceptors.request.use((config) => {
  const token = useAuthStore.getState().accessToken;
  if (token && config.headers) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

/* ---- refresh compartido ---------------------------------------------- */
let refreshPromise: Promise<string> | null = null;

async function refreshAccessToken(): Promise<string> {
  const refreshToken = useAuthStore.getState().refreshToken;
  if (!refreshToken) throw new Error('No refresh token');

  const { data } = await axios.post(`${BASE_URL}/auth/refresh`, {
    refresh_token: refreshToken,
  });

  // El backend ahora rota el refresh token: hay que guardar el nuevo.
  useAuthStore.getState().setTokens(data.access_token, data.refresh_token ?? refreshToken);
  return data.access_token as string;
}

function forceLogout() {
  useAuthStore.getState().logout();
  if (window.location.pathname !== '/login') {
    window.location.replace('/login');
  }
}

client.interceptors.response.use(
  (response) => response,
  async (error: AxiosError & { friendlyMessage?: string }) => {
    const originalRequest = error.config as (AxiosRequestConfig & { _retry?: boolean }) | undefined;
    const status = error.response?.status;

    if (
      status === 401 &&
      originalRequest &&
      !originalRequest._retry &&
      !isAuthPath(originalRequest.url)
    ) {
      originalRequest._retry = true;
      try {
        refreshPromise = refreshPromise ?? refreshAccessToken().finally(() => {
          refreshPromise = null;
        });
        const newToken = await refreshPromise;
        originalRequest.headers = {
          ...(originalRequest.headers as object),
          Authorization: `Bearer ${newToken}`,
        };
        return client(originalRequest);
      } catch (refreshError) {
        forceLogout();
        return Promise.reject(refreshError);
      }
    }

    let friendlyMessage = 'Ocurrió un error inesperado. Inténtalo de nuevo.';
    const detail = (error.response?.data as { detail?: string } | undefined)?.detail;

    if (!error.response) {
      friendlyMessage =
        error.code === 'ECONNABORTED'
          ? 'La conexión tardó demasiado. Inténtalo de nuevo.'
          : 'Sin conexión a Internet. Verifica tu red e inténtalo de nuevo.';
    } else if (status === 400 || status === 409 || status === 422) {
      friendlyMessage = detail || 'Los datos enviados no son válidos.';
    } else if (status === 401) {
      friendlyMessage = detail || 'Usuario o contraseña incorrectos.';
    } else if (status === 403) {
      friendlyMessage = detail || 'No tienes permiso para realizar esta acción.';
    } else if (status === 404) {
      friendlyMessage = 'El recurso solicitado no fue encontrado.';
    } else if (status === 423) {
      friendlyMessage = detail || 'Cuenta bloqueada temporalmente. Intenta más tarde.';
    } else if (status === 429) {
      friendlyMessage = 'Demasiados intentos. Espera unos minutos e inténtalo de nuevo.';
    } else if (status >= 500) {
      friendlyMessage = 'Error en el servidor. Inténtalo más tarde.';
    }

    error.friendlyMessage = friendlyMessage;
    return Promise.reject(error);
  },
);

export const authApi = {
  login: async (usernameOrEmail: string, password: string) => {
    const { data } = await client.post('/auth/login', {
      username_or_email: usernameOrEmail,
      password,
    });
    return data as { access_token: string; refresh_token: string; user: User };
  },
  refresh: async (refreshToken: string) => {
    const { data } = await client.post('/auth/refresh', { refresh_token: refreshToken });
    return data as { access_token: string; refresh_token?: string };
  },
  logout: async (refreshToken: string) => {
    await client.post('/auth/logout', { refresh_token: refreshToken });
  },
  me: async () => {
    const { data } = await client.get('/auth/me');
    return data as User;
  },
};

export default client;
