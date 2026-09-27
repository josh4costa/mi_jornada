# Revisión técnica — Mi Jornada

Revisión completa del código que está en el proyecto (backend FastAPI + frontend React/PWA + despliegue Docker/Traefik) y parches listos para aplicar.

**Antes que nada:** el `.env` del repositorio trae la contraseña de Postgres y el `SECRET_KEY` reales. Rota ambos y sácalo del historial de Git. Al cambiar el `SECRET_KEY` todos los tokens emitidos dejan de ser válidos (todos vuelven a iniciar sesión, una sola vez).

Los archivos corregidos están en `parches/`, con la misma ruta que deben tener en el repo. Cada uno lleva arriba un comentario con lo que cambió y por qué.

---

## Resumen

| Prioridad | Qué es | Cuántos |
|---|---|---|
| **P0** | Rompe en producción o es hueco de seguridad | 8 |
| **P1** | Funcionalidad que se ve bien pero no funciona | 9 |
| **P2** | Robustez, rendimiento y mantenimiento | 12 |

Lo más importante en una línea: **tal como está, un despliegue limpio en el VPS no arranca** (nadie crea las tablas) y **nginx no reenvía `/api`**, así que el frontend queda sin backend. Encima hay varios contratos front↔back que no coinciden y hacen que pantallas completas del panel admin se vean vacías.

---

## P0 — Bloqueantes

### 1. Nadie ejecuta las migraciones en producción
`alembic/versions/0001_initial.py` existe, pero nada lo corre. El seed de `main.py` solo se ejecuta con `ENVIRONMENT=development`, y en Compose el backend arranca con `ENVIRONMENT=production`. En un VPS nuevo: base vacía, cero tablas, 500 en el primer login.
→ `parches/backend/Dockerfile` arranca con `alembic upgrade head && uvicorn ...`.

### 2. El frontend no puede hablar con el backend
Traefik enruta solo al contenedor `frontend` (puerto 80) y el backend no está expuesto. El cliente llama a `/api/v1`, que es una ruta relativa: nginx tiene que reenviarla.
→ `parches/frontend/nginx.conf` (proxy `/api/` → `backend:8000`, fallback SPA, caché correcta).

### 3. Un refresh token servía como token de acceso
`create_access_token` no marcaba el tipo y `deps.get_current_user` aceptaba cualquier JWT firmado. Un refresh token —válido **30 días** y guardado en `localStorage`— entraba como Bearer en cualquier endpoint, saltándose por completo la expiración de 15 minutos del access token.
→ `parches/backend/app/core/security.py` + `api/deps.py` (campo `type` y validación).

### 4. `/auth/refresh` no validaba el JWT
Solo buscaba el hash en la tabla: no verificaba firma, expiración ni tipo, ni que el usuario siguiera activo. Desactivar a alguien en el panel **no lo sacaba del sistema**: seguía renovando tokens. Tampoco había rotación, así que un token robado servía un mes.
→ `parches/backend/app/api/v1/auth.py` (validación, rotación, detección de reuso, revocación al desactivar/cambiar contraseña).

### 5. El rate limit de login responde 500 y es global
`Limiter` se creaba dentro de `auth.py` y nunca se asignaba a `app.state.limiter`; el handler de slowapi lo necesita, así que al superar el límite devuelve 500 en vez de 429. Peor: `get_remote_address()` detrás de Traefik ve la IP del proxy, o sea que **los 5 intentos / 15 min son compartidos por todos los usuarios**: un técnico equivocándose de contraseña bloquea el login de toda la empresa.
→ `parches/backend/app/core/limiter.py` + `main.py`.

### 6. CORS `*` con credenciales
`allow_origins=['*']` + `allow_credentials=True` es una combinación que el navegador rechaza, y además abre la API a cualquier origen.
→ `config.py` ahora falla al arrancar si en producción el `SECRET_KEY` es el de ejemplo o el CORS es `*`. Mejor reventar en el despliegue que quedar abierto.

### 7. El `.env` versionado (y el `.gitignore` equivocado)
El `.gitignore` del repo es el que genera pytest dentro de `.pytest_cache` (su contenido es `*`), y el `README.md` también es el de `.pytest_cache`. El README real del proyecto se perdió.
→ `parches/.gitignore` y `parches/.env.example`.

### 8. El service worker deja la app "congelada" tras cada deploy
`sw.js` guarda `/` e `index.html` con estrategia caché-primero y nunca borra cachés viejas. Después de un `docker compose up --build`, los técnicos siguen recibiendo el `index.html` anterior, que pide bundles con hash que ya no existen: **pantalla en blanco** hasta borrar los datos del navegador. En una PWA instalada en el celular esto es soporte telefónico garantizado.
→ `parches/frontend/public/sw.js` (red primero para navegación, caché versionada, limpieza en `activate`).

---

## P1 — Se ve terminado, pero no funciona

### 9. Un 401 de login recarga la página y borra el error
En `client.ts` el interceptor trata el 401 de `/auth/login` como "token vencido": intenta refrescar, falla, hace `logout()` y `window.location.href = '/login'`. El usuario escribe mal la contraseña y lo único que ve es la pantalla parpadeando: nunca aparece "Usuario o contraseña incorrectos".
→ `parches/frontend/src/api/client.ts` (excluye rutas de auth, refresh único compartido, mensajes por código).

### 10. El admin no puede programar tareas a futuro
`POST /admin/tasks` ignora `body.assigned_date` y fuerza `today_local()`. El formulario pide la fecha, la manda... y todo cae en el día de hoy.
→ `parches/backend/app/api/v1/admin/tasks.py`.
⚠️ Requiere agregar `assigned_date: date` al esquema `TaskCreate` (`app/schemas/task.py`, que no venía en la copia del proyecto).

### 11. El filtro de fecha en Tareas no hace nada
El front manda `?date=`, el backend lee `?task_date=`. FastAPI ignora el parámetro desconocido en silencio. Lo mismo: el front manda `notes`, que no existe en el modelo, y el `setattr()` ciego del PATCH lo escribía en un atributo fantasma.

### 12. No se puede reactivar a un usuario
`PATCH /admin/users/{id}/disable` siempre pone `is_active = False`, y `Users.tsx` usa ese mismo endpoint para activar. Desactivas a alguien y ya no hay forma de revivirlo desde la interfaz.
→ El endpoint ahora acepta `{"is_active": true|false}`.

### 13. Cambiar la contraseña de un usuario no cambia nada
El front manda `password` en el PATCH; el `setattr()` lo asigna a un atributo inexistente (la columna es `password_hash`). No truena, no avisa, y el usuario sigue con la contraseña vieja. Este es de los que se descubren tarde y feo.

### 14. El panel admin muestra "Invalid Date" en Entrada/Salida
`dashboard.py` devuelve la hora ya formateada (`"7:58 AM"`) y `Dashboard.tsx` hace `new Date(iso)` sobre eso.
→ Ahora el backend manda ISO-8601 y el front sigue formateando a America/Monterrey.

### 15. Los selectores de técnicos salen vacíos en 4 pantallas
`adminApi.ts` espera objetos planos con `full_name`; `GET /admin/technicians` devuelve el usuario anidado, y el detalle devuelve `{technician, workday, tasks}` cuando el front espera `full_name`, `current_workday` y `today_tasks`. Resultado: dropdowns en blanco en Tareas, Jornadas y Reportes, y ficha del técnico vacía.
→ `parches/backend/app/api/v1/admin/technicians.py`.

### 16. La tabla de Jornadas no tiene nombre ni conteos
`Workdays.tsx` pinta `technician_name`, `tasks_assigned` y `tasks_completed`; el backend no enviaba ninguno.
→ Agregados con una sola consulta agrupada.

### 17. Los promedios de entrada/salida están en la zona horaria equivocada
`reports.py` usaba `t.astimezone()`, que convierte a la hora local **del contenedor** (UTC en el VPS): los promedios salen 6 horas adelantados. Además promediaba en aritmética circular (07:50 y 23:50 daban 15:50), y el CSV exportaba "—" en esas dos columnas.
→ `parches/backend/app/api/v1/admin/reports.py` (usa `to_local()`, una sola función para JSON y CSV).

---

## P2 — Robustez, rendimiento, mantenimiento

18. **UUID mal formado = 500.** `Workday.id == "abc"` explota en asyncpg. Los parches validan y devuelven 422.
19. **`setattr()` ciego** en tareas y usuarios permitía escribir `created_by`, `password_hash`, `failed_login_attempts`. Ahora hay lista blanca.
20. **Nada impide quedarse sin administradores**: un admin podía desactivarse a sí mismo o al último admin activo. Bloqueado.
21. **`pool_pre_ping` faltante**: cuando Postgres reinicia, la app queda tirando `connection was closed` hasta reiniciarla. Agregado, con `pool_recycle`.
22. **`/health` no tocaba la base**: respondía "ok" con la base caída. Ahora hace `SELECT 1` y devuelve 503, y Compose lo usa como healthcheck.
23. **`DATABASE_URL` del entorno se ignoraba**: `config.py` la calculaba como propiedad y Compose la mandaba de todos modos. Funcionaba de chiripa porque también se pasa `POSTGRES_HOST`.
24. **N+1 en el historial del técnico**: 2 consultas por jornada mostrada (60 consultas en una página de 30). Igual el dashboard, que contaba tareas en Python. Consolidado en `GROUP BY`.
25. **Paginación inestable**: `ORDER BY work_date DESC` sin desempate hace que en la página 2 se repitan o falten registros. Agregado segundo criterio.
26. **`/docs` abierta en producción**: publica el esquema completo de la API. Cerrada cuando `ENVIRONMENT=production`.
27. **Tests acoplados al orden**: `test_check_out_success` cierra la jornada de Juan y `test_tasks` completa una tarea del seed; si pytest cambia el orden o se corre un test solo, falla. Conviene una fixture que reconstruya el seed por test (`Base.metadata.create_all` por función, o transacción con rollback). También `conftest.py` redefine `event_loop`, deprecado en pytest-asyncio 0.24 — ver `parches/backend/pytest.ini`.
28. **`npm run build` no valida tipos** (`vite build` solo) y `npm run lint` invoca ESLint sin configuración ni plugins de TypeScript: el script falla. O se configura, o se quita.
29. **`user-scalable=no`** en `index.html` impide el zoom: mala accesibilidad para técnicos en campo (y lo penaliza Lighthouse).
30. **La PWA promete offline que no existe**: hay banner de "sin conexión" y service worker, pero el check-in no se encola. Si un técnico llega a una sucursal sin señal, no puede registrar entrada. Es el siguiente paso natural del producto: cola en IndexedDB + Background Sync, con la hora real del evento mandada desde el cliente.

---

## Orden sugerido para aplicar

1. Rotar `SECRET_KEY` y contraseña de Postgres; sacar `.env` del repo (P0-7).
2. `Dockerfile` backend + `nginx.conf` + `docker-compose.yml` → que el despliegue funcione (P0-1, P0-2).
3. `security.py`, `deps.py`, `auth.py`, `limiter.py`, `main.py`, `config.py` → seguridad (P0-3 a P0-6).
4. `sw.js` y `client.ts` → los dos bugs que más golpean al usuario final (P0-8, P1-9).
5. Routers admin (`dashboard`, `technicians`, `workdays`, `tasks`, `users`, `reports`) + `adminApi.ts` → el panel deja de mentir (P1-10 a P1-17).
6. P2 conforme haya tiempo.

## Dos cosas que necesito de tu lado

- **`app/schemas/*.py` no venía en la copia del proyecto.** Los parches asumen que `TaskCreate` gana `assigned_date: date`, que `UserUpdate` acepta `password: str | None`, y que `RefreshTokenResponse` incluye `refresh_token: str | None` (si no, FastAPI lo recorta de la respuesta y la rotación se rompe en silencio).
- **Los endpoints del lado técnico** (`/workdays/check-in`, `/check-out`, `/tasks/today`, `/tasks/unplanned`, `/tasks/{id}/complete`) tampoco venían, aunque los tests y el front los usan. No los revisé: ahí es donde vive la regla de negocio más delicada (una jornada abierta por técnico, cálculo de `duration_minutes`, y qué pasa con una jornada que cruza la medianoche).
