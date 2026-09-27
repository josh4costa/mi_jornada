# Despliegue de producción

Versión: `audit-20260920-r1`. Aplicada el 20 de septiembre de 2026 (México).

- Servidor: `49.12.67.202`.
- Aplicación: https://myjornada.pleg.com.mx
- Directorio activo: `/opt/mi_jornada`.
- Migración activa: `0002`.
- Backend, frontend y PostgreSQL: saludables después del despliegue.
- `.env`, dominio, configuración de Cloudflare/Traefik y volumen de producción conservados.

## Verificación realizada

1. Respaldo inicial de código y base; segundo respaldo de base inmediatamente antes del cambio.
2. Restauración del respaldo en PostgreSQL 16 aislado, sin puertos publicados y sin acceso a la red de producción.
3. Migración 0001 → 0002 sobre la copia, con los mismos conteos de usuarios, técnicos, jornadas y tareas antes/después.
4. Pruebas sobre PostgreSQL de sesiones, creación de técnicos, jornada del día anterior, solicitudes simultáneas de entrada/salida y cancelación/finalización de tareas. Pasaron.
5. Suite de 23 pruebas aprobada dentro de la imagen Linux que se desplegó.
6. Comprobación pública por HTTPS de HTML, JS/CSS nuevos, service worker versionado, `/health` y rechazo 401 de API sin credenciales.
7. Navegador Edge: pantalla de acceso móvil renderizada sin errores JavaScript ni recursos del dominio fallidos. No se iniciaron sesiones con cuentas reales para esta comprobación.
8. Reparación de perfiles: cero faltantes. No fue necesario crear perfiles.
9. Contenedor y red de PostgreSQL de validación eliminados al terminar; datos sintéticos usados exclusivamente en esa copia.

Durante el reemplazo del frontend hubo una respuesta 404 transitoria de enrutamiento; las comprobaciones posteriores por Cloudflare y navegador fueron satisfactorias.

## Recuperación

Respaldos, accesibles solo al operador del servidor:

`/opt/mi_jornada_backups/audit-20260920-r1/`

Incluyen `source-before.tar.gz`, `database.dump`, `database-cutover.dump`, fuentes anteriores y `SHA256SUMS` verificado. Las imágenes anteriores están etiquetadas:

- `mi_jornada-backend:rollback-audit-20260920-r1`
- `mi_jornada-frontend:rollback-audit-20260920-r1`

La migración 0002 añade la tabla de entregas; no modifica los datos históricos. Para una reversión de aplicación, usar las fuentes y las imágenes anteriores; no restaurar automáticamente la base, porque se perderían operaciones posteriores al respaldo. La restauración de datos requiere un procedimiento de recuperación específico.

Fuentes empaquetadas y scripts utilizados: `/opt/mi_jornada_releases/audit-20260920-r1/`.

Las funcionalidades de registro offline y cookies HttpOnly continúan pendientes para una actualización independiente. Para que una PWA ya abierta tome su nuevo service worker, cerrar todas sus ventanas y volver a abrirla.
