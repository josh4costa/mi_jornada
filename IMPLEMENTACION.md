# Resultado de la implementación

> Actualización: esta versión ya fue desplegada y comprobada con PostgreSQL. Ver [DESPLIEGUE.md](DESPLIEGUE.md). Los límites descritos abajo corresponden a la entrega local previa al despliegue.

Los diez hallazgos funcionales de AUDITORIA.md tienen correcciones en el código local.

| Área | Cambio |
|---|---|
| Sesión | Response compatible con el limitador, bloqueo de rotación en PostgreSQL, timeout, renovación compartida entre peticiones/pestañas y conservación de sesión ante errores temporales. |
| Jornadas | Se conserva la jornada abierta del día anterior, se muestra en técnico y administrador y se exige cerrarla antes de otra entrada. Entrada/salida se serializan por técnico. |
| Usuarios | Alta y cambios de rol sincronizan el perfil técnico, se respeta is_active y se permite editar username. Se incorpora búsqueda y paginación. |
| Tareas | Solo pendientes pueden completarse. Edición/cancelación/finalización bloquean la misma fila. El formulario usa description y envía null para horario vacío. |
| Interfaz | Etiquetas compatibles, errores de jornada y tareas separados, botones con variantes válidas y recuperación de errores sin indicar falsamente una entrada pendiente. |
| Reportes | Formato único de hora, minutos conservados, ausencias con null, promedios relativos a la fecha de jornada, inclusión de técnicos inactivos, validación del rango en CSV y JSON. |
| Integraciones | Cola transaccional persistente de webhooks, identificador estable, reintentos y comandos de consulta/reactivación. Requiere migración 0002. |
| Instalación | Comando para el primer administrador y reparación explícita de perfiles faltantes. Guía con dominio consistente. |
| PWA | Caché versionada por contenido, precarga de bundles y actualización sin activación forzada sobre ventanas abiertas. |
| Calidad y accesibilidad | TypeScript antes del build, lint, lockfile, separación de bundles, colores faltantes, foco y Escape en modales, etiquetas de controles de acceso y botones de usuarios. |

Además, el checkbox de persistencia de sesión ahora selecciona localStorage o sessionStorage. Se añadieron rangos válidos para GPS y scripts para respaldo/restauración de prueba sin sobrescribir archivos ni bases existentes.

## Validación

- Backend: **23 pruebas aprobadas**. Incluyen 11 pruebas nuevas, migraciones sobre SQLite vacío y creación del primer administrador. Cada prueba parte de datos aislados en memoria.
- Frontend: **8 pruebas de navegador aprobadas** sobre el build de producción, con Edge. Incluyen dos pestañas renovando sesión, recarga offline real del service worker, reportes, paginación, modales y errores de API simulados.
- TypeScript, build de producción y ESLint: aprobados.
- Captura móvil de 390 × 844 revisada; corregidos los colores faltantes del encabezado.
- `pnpm audit`: **0 vulnerabilidades reportadas** en el conjunto frontend resuelto. Axios, React Router y Vite actualizados. Esto no constituye un análisis de dependencias Python ni garantiza ausencia de vulnerabilidades desconocidas.
- El comando de respaldo compila y muestra ayuda; no se ha ejecutado contra una base real.

## Alcance pendiente fuera de esta entrega local

- No se desplegó en el VPS ni se modificaron datos reales. Docker/PostgreSQL no están disponibles en este entorno: quedan pendientes las pruebas de contenedores, bloqueos concurrentes en PostgreSQL y restauración real.
- Las pruebas de navegador simulan la API; las del backend verifican por separado los endpoints reales. Falta un recorrido integrado contra el entorno de despliegue.
- Cookie HttpOnly, registros de asistencia offline y alertas/respaldos programados eran mejoras condicionadas a requisitos operativos. No están implementados como funcionalidades nuevas. El modo offline indica sus límites y los procedimientos de operación explican los siguientes pasos.
- Los perfiles antiguos requieren ejecutar explícitamente la reparación. Las jornadas que ya quedaron en cero necesitan revisión humana; no se inventan horarios para rellenarlas.

Ver [OPERACION.md](OPERACION.md) para migración, primer administrador, reparación, webhooks, respaldo y recuperación.
