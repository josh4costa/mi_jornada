# Reportes semanales de asistencia

En **Reportes → Envío semanal y destinatarios**, un administrador puede activar o pausar el envío, editar Para/CC, definir el primer lunes y consultar el historial con el PDF exacto generado. El botón de PDF usa los filtros de fechas y técnico (máximo 31 días).

Configuración inicial autorizada: lunes 28 de septiembre de 2026, 09:00 America/Monterrey; Para oscar.moncada@pleg.com.mx; CC josue.acosta@pleg.com.mx y lupita.carrizales@pleg.com.mx. Primer período: 21–27 de septiembre. Cada envío cubre lunes a domingo anteriores, incluyendo sábado laborable. El remitente es GRUPO EXPO - Recursos Humanos <notificaciones@pleg.com.mx>.

El PDF incluye resumen por técnico y detalle diario, horarios, horas de jornadas cerradas, entradas después de las 09:00, salidas anticipadas, vacaciones y permisos aprobados, inasistencias justificadas y faltas revisadas. Los días sin entrada quedan pendientes de revisión; no se transforman automáticamente en faltas confirmadas. Las jornadas anuladas no se cuentan. No se calculan salarios ni descuentos de comida. Un registro nocturno muestra la fecha de salida. Las cuentas inactivas sin registro requieren revisar su vigencia histórica.

## Operación

- El worker del backend revisa la programación cada 30 segundos; no requiere una PC o Codex abiertos.
- Fecha de envío única en PostgreSQL y toma atómica del envío evitan duplicación entre los procesos del backend. Cada PDF y destinatarios quedan congelados al generarse.
- Puede recuperar el envío durante las 24 horas siguientes al lunes 09:00. Los errores seguros de conexión/rechazo permiten hasta tres intentos separados por 10 minutos.
- ACEPTADO significa que SMTP aceptó el mensaje, no confirma llegada a bandeja ni lectura. PARCIAL o SIN CONFIRMAR requieren comprobar recepción antes de cualquier reenvío manual. Nunca se reintentan automáticamente esos estados. Una toma interrumpida pasa a SIN CONFIRMAR después de cinco minutos.
- Los reportes vencidos quedan descargables; no se envían correos antiguos de forma masiva. Pausar no genera reportes durante la pausa. Al reactivar, puede recuperar la semana vigente si sigue dentro de las 24 horas.
- Cambios de destinatarios aplican a futuros reportes; las copias ya generadas mantienen sus destinatarios. La edición se audita y detecta cambios simultáneos.
- Ante un fallo final, un administrador puede descargar el PDF desde el historial y enviarlo manualmente tras revisar la recepción.

## Correo saliente

Variables privadas de servidor: SMTP_HOST, SMTP_PORT, SMTP_SECURITY (SSL o STARTTLS), SMTP_USER, SMTP_PASSWORD, SMTP_FROM, SMTP_FROM_NAME. No hay contraseñas en el frontend, respuestas API o repositorio. Los certificados TLS se verifican.

IONOS autenticó desde el VPS por smtp.ionos.mx:587 con STARTTLS; el puerto 465 agotó el tiempo de conexión. La contraseña se guarda entre comillas simples en `.env` para conservar sus caracteres especiales en Docker Compose. No se enviaron correos reales durante las pruebas automatizadas.

La migración 0005 agrega configuración e historial sin cambiar jornadas existentes. Respaldo de base y código antes del despliegue; imagen de reversión compatible con la migración. Los PDF son internos y solo accesibles para administradores autenticados.
