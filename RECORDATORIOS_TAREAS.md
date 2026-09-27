# Recordatorio de tareas

Versión tasks-reminder-20260921-r1. Conserva esquema 0007.

Se evalúa cada 30 segundos. Al cumplirse 30 minutos desde la entrada real, si la jornada sigue abierta, no anulada y no tiene tareas vigentes asignadas/registradas, manda un WhatsApp. Incluye tareas pendientes y completadas; excluye canceladas. Solo técnico y cuenta activos, con WhatsApp válido y recordatorios habilitados. Respeta ausencias aprobadas. Funciona de día, de noche, domingos y al cruzar medianoche.

Un aviso por fecha/tipo de jornada (TASKS_DAY / TASKS_NIGHT), protegido con restricción única en PostgreSQL y comprobación inmediatamente antes de enviar. No se reintenta una entrega rechazada o incierta automáticamente. No genera incidencias ni sanciones. Si el servicio no pudo evaluar durante los 30 minutos posteriores al vencimiento, el aviso expira: no se mandan avisos atrasados a jornadas antiguas.

Las tareas se relacionan con técnico/fecha en la app. Se consideran la fecha de entrada y la fecha local actual. Al usar Continuar con turno diurno, se heredan la fecha y tareas de la noche anterior y se omite un segundo aviso si ya se intentó durante la noche.

Los envíos aparecen en Ausencias y asistencia > WhatsApp como Registrar tareas (diurna/nocturna). Se mantienen interruptores y teléfono existentes en Personal.

Mensaje: Hola, {nombre} 👋 Ya registraste tu entrada, pero aún no aparecen tareas para tu jornada. Entra a Mi Jornada y registra las actividades que realizarás para mantener actualizado tu trabajo: [URL de la app]. Si todavía estás esperando asignación de actividades, comunícalo a tu supervisor.

Respaldo /opt/mi_jornada_backups/tasks-reminder-20260921-r1. Pruebas de proveedor simuladas, sin mensajes de prueba reales.
