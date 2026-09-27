# Horarios, ausencias y recordatorios

Versión `attendance-20260921-r1`. Zona horaria: America/Monterrey.

- Lunes a viernes: 09:00–18:00; sábados: 09:00–13:00; domingos: descanso.
- La entrada puede registrarse antes del horario. Una salida anterior a la hora programada requiere motivo y genera una incidencia pendiente, conservando la hora real. Las jornadas de días anteriores pueden cerrarse sin bloquear el nuevo día.
- Vacaciones y permisos de día completo se solicitan con rango de fechas y motivo. Incluyen sábados y excluyen domingos. Solo un administrador aprueba o rechaza. Los técnicos pueden cancelar solicitudes pendientes; solo un administrador puede cancelar una aprobada. Las revisiones conservan autor, fecha y motivo.
- El calendario no descuenta días festivos adicionales ni calcula saldo legal de vacaciones. No aplica permisos por horas.
- Al terminar cada día laboral, las entradas ausentes se marcan pendientes de revisión; nunca se confirma automáticamente una falta injustificada. La fecha de inicio del control se configura con `ATTENDANCE_START_DATE`. No se generan incidencias anteriores al despliegue. El cursor persistente recupera días no procesados tras una interrupción.

## WhatsApp

Credenciales solo en `.env` del servidor: `ULTRAMSG_INSTANCE`, `ULTRAMSG_TOKEN`, `REMINDERS_ENABLED=true`, `APP_URL`. No se incluyen en el frontend ni se muestran por la API. El número y el interruptor de cada técnico se administran en Personal. Los números habilitados deben ser únicos y tener formato internacional.

El servidor verifica cada 30 segundos: entrada 09:10, salida 18:10 (sábado 13:10). Cada aviso tiene una ventana de recuperación de 30 minutos; después vence. Se excluyen cuentas inactivas, domingos, ausencias aprobadas y registros ya realizados. Se comprueba la conexión de UltraMsg antes del envío.

Una restricción única por técnico, día y tipo impide duplicados. Se registra la intención antes de llamar al proveedor; si hay un timeout o reinicio incierto no se reenvía automáticamente. El administrador consulta los últimos 50 intentos en Ausencias y asistencia > WhatsApp. `ACCEPTED` significa aceptado por UltraMsg, no entregado ni leído. No se recopilan respuestas de WhatsApp.

Plantilla de entrada: saludo, horario de las 9:00, enlace a la app y advertencia de posible falta injustificada pendiente de revisión cuando no existe registro ni autorización. Plantilla de salida: jornada abierta y enlace para registrar al terminar.

## Operación

Requiere migración Alembic 0003 (tablas nuevas y un campo en técnicos, sin borrar jornadas). Respaldo y archivos de despliegue en `/opt/mi_jornada_backups/attendance-20260921-r1/` y `/opt/mi_jornada_releases/attendance-20260921-r1/`.

Las pruebas usan transportes simulados para WhatsApp y PostgreSQL aislado restaurado desde un respaldo. No se envían mensajes reales de prueba a los técnicos. La verificación de credenciales consulta únicamente el estado de la instancia.
