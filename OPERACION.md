# Operación y verificación

## Preparar una instalación nueva

1. Configurar `.env` desde `.env.example` con secretos propios. No utilizar credenciales demo.
2. Verificar la red externa `traefik-network`, DNS y el dominio `myjornada.pleg.com.mx` en Compose y CORS; adaptarlos juntos si cambia el dominio.
3. Ejecutar `docker compose up -d --build`. El backend aplica Alembic, incluida la migración 0002 para entregas de webhooks.
4. Crear el primer administrador:

```sh
docker compose exec backend python -m app.manage create-admin --username administrador --email administrador@example.com --name "Administrador"
```

La contraseña se solicita sin mostrarla y no queda en el comando. El alta se rechaza si ya existe un administrador activo.

## Actualizar una instalación existente

Antes de actualizar, generar y verificar un respaldo. Guardar también la versión anterior del código y la configuración fuera del repositorio.

```sh
python scripts/database_backup.py backup backups/antes_actualizacion.dump
python scripts/database_backup.py restore-check backups/antes_actualizacion.dump --database restore_check_actualizacion
docker compose up -d --build
docker compose exec backend python -m app.manage repair-technicians
```

El último comando solo cuenta técnicos sin perfil. Revisar el resultado y aplicar la reparación cuando corresponda:

```sh
docker compose exec backend python -m app.manage repair-technicians --apply
```

No borra jornadas ni tareas, ni cambia contraseñas. No recalcula automáticamente jornadas que versiones anteriores dejaron en cero: esas horas necesitan evidencia y revisión humana.

El script de respaldo no sobrescribe archivos existentes. Si falla pg_dump, considerar el archivo incompleto y repetir con otro nombre. `restore-check` solo crea una base nueva con prefijo `restore_check_`; no reemplaza la base operativa. La copia de restauración contiene datos personales: protegerla igual que producción y administrarla con la política de retención de la organización.

Para recuperación real, restaurar en una base nueva, verificar conteos y registros, y cambiar la configuración de conexión bajo una ventana de mantenimiento. No ejecutar `docker compose down -v`. Mantener respaldos cifrados fuera del servidor y comprobar restauraciones periódicamente. Los scripts no instalan una programación automática.

## Webhooks

Configurar las URL existentes WEBHOOK_CHECK_IN_URL, WEBHOOK_CHECK_OUT_URL y WEBHOOK_TASK_COMPLETED_URL. Se guarda el evento en la misma transacción que la operación; los procesos de backend consumen la cola con bloqueo de filas. No se envía nada si la URL correspondiente está vacía.

El receptor recibe `{id, event, data}` y la cabecera `Idempotency-Key` con el mismo id en todos los intentos. Debe deduplicar por ese identificador: la entrega es al menos una vez, no exactamente una vez. Hay hasta 10 intentos con espera creciente y timeout de cinco segundos. No se siguen redirecciones. Usar destinos HTTPS controlados por la organización.

```sh
docker compose exec backend python -m app.manage webhooks
docker compose exec backend python -m app.manage webhooks --retry-failed
docker compose logs --tail 100 backend
```

El segundo comando reactiva solamente las entregas que agotaron reintentos. Los errores de entrega se registran sin incluir URL ni payload. Supervisar `/health`, reinicios y entregas agotadas con el sistema de alertas de la organización.

## PWA y sesión

El build genera una versión de caché basada en contenido y precarga los recursos de esa versión. Una actualización del service worker se activa cuando se cierran las ventanas que usan la anterior. No borrar los datos del navegador para actualizar normalmente.

El modo sin conexión permite cargar la interfaz previamente preparada; las operaciones necesitan conexión y la pantalla lo indica. No hay registros de asistencia diferidos: permitirlos requiere definir cómo validar la hora del dispositivo y resolver conflictos. La auditoría planteaba esa función condicionada a la necesidad operativa.

La renovación usa timeout, comparte solicitudes en la pestaña y coordina pestañas mediante Web Locks cuando el navegador lo soporta. Los fallos temporales conservan la sesión para reintentar. Sin “Mantener sesión iniciada”, se usa sessionStorage; con esa opción, localStorage. El traslado a cookie HttpOnly requiere una migración específica del contrato de autenticación y su protección CSRF; no se presenta como implementado en esta entrega.

## Comprobaciones locales

```sh
cd backend
python -m pytest -q --show-capture=no
cd ../frontend
corepack enable
pnpm install --frozen-lockfile
pnpm run lint
pnpm run build
pnpm run test:e2e
pnpm audit --prod
```

En Windows las pruebas de navegador usan Edge. En otros sistemas instalar Chromium con `pnpm exec playwright install chromium`, o elegir un canal instalado con PLAYWRIGHT_CHANNEL. Las pruebas del navegador usan respuestas de API simuladas; las de backend ejercitan la aplicación real sobre SQLite en memoria y una prueba aplica las migraciones a una base vacía. Verificar también las migraciones y la concurrencia con PostgreSQL antes de desplegar en producción.
