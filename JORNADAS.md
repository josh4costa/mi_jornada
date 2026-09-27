# Edición y anulación de jornadas

Versión `workdays-20260921-r1`, migración 0004. En Administración > Jornadas aparecen Editar, Eliminar e Historial, en escritorio y móvil.

- Editar permite corregir entrada y salida, o dejar la salida vacía para reabrir. Las horas se interpretan en America/Monterrey. Se recalcula la duración. La fecha de entrada conserva el día de la jornada para no cambiar la asociación de tareas por fecha.
- Eliminar anula de forma reversible con motivo obligatorio. Se excluye de horas y días trabajados, inicio/cierre, panel operativo e historial del técnico. Las tareas no se borran ni se excluyen de sus propios totales.
- Mostrar también jornadas anuladas + Buscar permite encontrarlas y restaurarlas. La restauración comprueba duplicados y conflictos horarios.
- Se conservan autor, fecha, motivo, valores anteriores y nuevos de cada cambio. Se bloquean cambios con una versión desactualizada, horarios futuros o inconsistentes y jornadas superpuestas.
- Las incidencias se reconcilian; una salida corregida que sigue siendo anticipada requiere revisión. Si se anula una jornada pasada dentro del período de control, se revisa la posible falta de entrada.

Respaldo: `/opt/mi_jornada_backups/workdays-20260921-r1/`. Fuentes: `/opt/mi_jornada_releases/workdays-20260921-r1/`. No se modifican credenciales ni ajustes de WhatsApp.
