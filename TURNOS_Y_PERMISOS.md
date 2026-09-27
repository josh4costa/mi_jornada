# Turnos nocturnos y acceso de consulta

Versión shifts-20260921-r1 · migración 0007.

## Solo lectura
Personal permite asignar Solo lectura. Consulta Operación, Tareas, Jornadas, Ausencias y asistencia y Reportes; genera PDF/CSV. No modifica jornadas, tareas, personal, sucursales, ausencias, programación nocturna ni destinatarios. La API aplica permisos independientemente de los botones. Conserva cambio y recuperación de su propia contraseña.

Mi cuenta muestra nombre, usuario, correo y rol. Cambiar contraseña abre un formulario separado. La configuración obligatoria de primera contraseña se mantiene.

## Noche
En Ausencias y asistencia > Turnos nocturnos, el administrador programa o el técnico avisa una noche. Se indica fecha real de inicio, hora del recordatorio y si sustituye o se suma al turno diurno de esa fecha. La hora del aviso no impone un horario nocturno. Si la entrada será después de medianoche, se programa esa nueva fecha.

Cuando sustituye el turno diurno, tanto un aviso pendiente como una programación aprobada suspenden los recordatorios diurnos de esa fecha. Solo la aprobación justifica el descanso diurno en asistencia. El técnico no puede autoaprobar ni autorizar descanso al día siguiente. La aprobación y rechazo requieren motivo y conservan historial. No se anulan resoluciones de falta ya confirmadas. La cancelación se permite antes de iniciar la noche y desde la fecha actual.

WhatsApp: un aviso NIGHT_ENTRY por técnico/fecha, en la hora elegida con ventana de 30 minutos, incluso domingos, solo con teléfono válido y recordatorios activados. Se omite si ya registró entrada nocturna o tiene ausencia aprobada. Los avisos vencidos no se mandan retroactivamente. No hay alerta de salida nocturna a hora fija. Ni el aviso ni la programación registran asistencia.

Ejemplo: lunes descanso diurno + entrada nocturna 22:00; martes Continuar con turno diurno a las 09:00. La operación guarda salida nocturna y entrada diurna con la misma hora/GPS en una transacción. Si no puede abrir la diurna, la nocturna queda abierta. No se cierra automáticamente a medianoche. Solo una jornada abierta por técnico y como máximo una diurna y una nocturna no anuladas por fecha. El día siguiente mantiene su horario salvo descanso explícitamente autorizado por administrador.

El técnico puede cerrar la noche a cualquier hora. Las reglas y motivos de salida anticipada aplican solo a jornada diurna. No se crean descuentos automáticamente. Una noche programada sin entrada genera incidencia por revisar. Las tareas de la jornada abierta siguen disponibles al cruzar medianoche.

PDF muestra filas separadas diurna/nocturna, fechas completas de entrada y salida y suma minutos. Días con entrada cuenta fechas únicas, no turnos. Tareas se cuentan por fecha; no sumar manualmente sus subtotales repetidos entre ambos turnos. CSV conserva días únicos y horas totales. Promedios de entrada/salida comprenden los turnos cerrados del período.

## Despliegue y recuperación
Respaldo de código y PostgreSQL en /opt/mi_jornada_backups/shifts-20260921-r1. Se valida migración y concurrencia contra una copia aislada antes de activar. No usar downgrade automático: preserva nuevas jornadas. La imagen anterior de recuperación incluye el enum READ_ONLY y el archivo de migración para arrancar sin eliminar información; no ofrece funcionalidades nocturnas y debe usarse solo como contingencia hasta restaurar esta versión.
