# Personal unificado

Versión: personal-20260920-r1.

La navegación administrativa reúne Usuarios y Técnicos en Personal, con filtros por rol, búsqueda y paginación. Un único formulario administra acceso y datos del técnico (teléfono y número de empleado). Los perfiles conservan su identidad y sus referencias a jornadas y tareas, incluso cuando cambia el rol o se desactiva la cuenta.

Las rutas anteriores redirigen a Personal. El detalle del técnico permite editar y consultar tareas e historial de jornadas.

La API administrativa de usuarios incluye el perfil técnico, permite filtrar por rol y actualiza ambos registros en una transacción. Un número de empleado duplicado devuelve conflicto sin guardar cambios parciales. No requiere cambios de esquema.

Validación local: 25 pruebas de backend, 9 pruebas de navegador, TypeScript, build y ESLint. La versión también se valida en PostgreSQL aislado restaurado desde un respaldo de producción antes de su activación.

Respaldo del despliegue: `/opt/mi_jornada_backups/personal-20260920-r1/`. Fuentes e imágenes candidatas: `/opt/mi_jornada_releases/personal-20260920-r1/`. Las imágenes anteriores quedan etiquetadas con `rollback-personal-20260920-r1`.
