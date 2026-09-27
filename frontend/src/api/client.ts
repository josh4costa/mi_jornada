/** Authenticated client with bounded requests and coordinated token rotation. */
import axios, { AxiosError, AxiosRequestConfig } from 'axios';
import { useAuthStore } from '../store/authStore';
import { User } from '../types';

const BASE_URL = import.meta.env.VITE_API_BASE_URL || '/api/v1';

const client = axios.create({
  baseURL: BASE_URL,
  timeout: 20000,
});

/** Rutas que nunca deben intentar refrescar el token. */
const AUTH_PATHS = ['/auth/login', '/auth/refresh', '/auth/logout', '/auth/change-password', '/auth/forgot-password', '/auth/reset-password'];
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

async function refreshAccessToken(failedToken?: string): Promise<string> {
  const renew = async () => {
    await useAuthStore.persist.rehydrate();
    const current = useAuthStore.getState();
    if (failedToken && current.accessToken && current.accessToken !== failedToken) return current.accessToken;
    const refreshToken = useAuthStore.getState().refreshToken;
    if (!refreshToken) { forceLogout(); throw new Error('La sesión ha terminado'); }

    const { data } = await axios.post(`${BASE_URL}/auth/refresh`, {
      refresh_token: refreshToken,
    }, { timeout: 20000 });

    // El backend ahora rota el refresh token: hay que guardar el nuevo.
    await useAuthStore.persist.rehydrate();
    if (useAuthStore.getState().refreshToken !== refreshToken) throw new Error('La sesión cambió durante la renovación');
    useAuthStore.getState().setTokens(data.access_token, data.refresh_token ?? refreshToken);
    return data.access_token as string;
  };
  return navigator.locks ? navigator.locks.request('mi-jornada-refresh', renew) : renew();
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
    if (status === 403 && (error.response?.data as any)?.detail?.code === 'PASSWORD_CHANGE_REQUIRED') {
      const user = useAuthStore.getState().user;
      if (user) useAuthStore.setState({user: {...user, must_change_password: true}});
      error.friendlyMessage = 'Establece tu contraseña personal para continuar.';
      return Promise.reject(error);
    }

    if (
      status === 401 &&
      originalRequest &&
      !originalRequest._retry &&
      !isAuthPath(originalRequest.url)
    ) {
      originalRequest._retry = true;
      try {
        const failedToken = String(originalRequest.headers?.Authorization ?? '').replace(/^Bearer /, '');
        refreshPromise = refreshPromise ?? refreshAccessToken(failedToken).finally(() => {
          refreshPromise = null;
        });
        const newToken = await refreshPromise;
        originalRequest.headers = {
          ...(originalRequest.headers as object),
          Authorization: `Bearer ${newToken}`,
        };
        return client(originalRequest);
      } catch (refreshError) {
        if (axios.isAxiosError(refreshError) && [401, 403].includes(refreshError.response?.status ?? 0)) forceLogout();
        return Promise.reject(refreshError);
      }
    }

    let friendlyMessage = 'Ocurrió un error inesperado. Inténtalo de nuevo.';
    const rawDetail = (error.response?.data as { detail?: unknown } | undefined)?.detail;
    const detail = typeof rawDetail === 'string' ? rawDetail : Array.isArray(rawDetail)
      ? rawDetail.map((item: { msg?: string }) => item.msg ?? 'Dato inválido').join('. ') : undefined;

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
    } else if (status && status >= 500) {
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
