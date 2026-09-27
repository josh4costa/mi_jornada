# Auditoría de Mi Jornada

> Este documento describe el estado previo. Las correcciones posteriores y sus pruebas están en [IMPLEMENTACION.md](IMPLEMENTACION.md).

Fecha: 20 de septiembre de 2026. Alcance: código local React/Vite, API FastAPI, modelos, migración inicial, pruebas y configuración Docker/PWA. No se modificó la aplicación ni se accedió al servidor desplegado. No se realizó inspección visual en navegador, compilación del frontend ni análisis actualizado de vulnerabilidades de dependencias.

## Verificación

- `python -m pytest -q` en backend: **12 pruebas correctas**, una advertencia por redefinición de event_loop.
- Las pruebas usan SQLite en memoria cuando TESTING=1; no ejecutan sus borrados sobre PostgreSQL. La sospecha inicial sobre borrado de datos queda descartada.
- Comprobaciones adicionales mediante ASGITransport y una base SQLite en memoria independiente reprodujeron los hallazgos 1, 3 y 4.
- Las pruebas crean tablas con Base.metadata.create_all, no mediante Alembic: no verifican el esquema real de producción. Por ejemplo, la migración incluye un índice único parcial para jornadas abiertas que el modelo no declara.

## Hallazgos prioritarios

### 1. Alta: la renovación de sesión falla

Ubicación: backend/app/api/v1/auth.py:142 y backend/app/core/limiter.py:28.

El limiter tiene headers_enabled=True, pero refresh no recibe un parámetro Response y devuelve un diccionario. Una renovación válida reproduce la excepción `parameter response must be an instance of starlette.responses.Response`. La rotación ya puede haberse confirmado en la base antes de fallar la respuesta. El cliente cierra sesión al fallar el refresh, por lo que la renovación al expirar el acceso queda rota.

Propuesta: proporcionar Response al endpoint, probar el ciclo login → refresh → recurso protegido → rechazo del token anterior, y cubrir errores de red sin convertirlos automáticamente en cierre de sesión. Después, hacer atómica la rotación y coordinar renovaciones entre pestañas; el single-flight actual solo coordina peticiones en una misma instancia de la página.

### 2. Alta: una jornada anterior se cierra con cero minutos

Ubicación: backend/app/services/workday.py:35–37 y backend/app/api/v1/workdays.py.

Al iniciar una jornada nueva, una anterior todavía abierta se cierra asignando salida igual a entrada y duración cero. Además, /today busca únicamente la fecha actual, así que una jornada nocturna anterior deja de aparecer como abierta en la pantalla del técnico.

Propuesta: devolver la jornada abierta aunque sea del día anterior; permitir cerrarla o marcarla como incidencia pendiente de corrección. No inventar una hora de salida. Registrar responsable, motivo y valores anteriores en cualquier corrección administrativa. Cubrir cambio de fecha y solicitudes simultáneas con pruebas sobre PostgreSQL y migraciones reales.

### 3. Alta: crear un técnico desde Usuarios produce una cuenta incompleta

Ubicación: backend/app/api/v1/admin/users.py:88–116; frontend/src/pages/admin/Users.tsx; backend/app/api/deps.py.

La pantalla permite crear TECHNICIAN, pero el endpoint solo crea User y no Technician. Reproducción: creación devuelve 201 y /workdays/today con ese usuario devuelve 403 por falta de perfil técnico. Cambiar un administrador sin perfil a TECHNICIAN tiene el mismo problema.

Propuesta: centralizar altas y cambios de rol con creación del perfil en la misma transacción, o dirigir explícitamente las altas de técnicos al flujo de Técnicos. Añadir una reparación de cuentas existentes previa revisión de datos.

### 4. Media: una tarea cancelada puede completarse por API

Ubicación: backend/app/services/task.py:22–25.

Solo se rechaza COMPLETED. Reproducción: enviar la finalización de una tarea propia CANCELLED devuelve 200 y cambia su estado a COMPLETED. Ocultar el botón en la interfaz no protege la regla ante peticiones antiguas o directas.

Propuesta: aceptar únicamente la transición PENDING → COMPLETED, con actualización condicional para proteger también la concurrencia con una cancelación administrativa.

### 5. Media: las etiquetas de estado del técnico usan un contrato incompatible

Ubicación: frontend/src/components/ui/Badge.tsx:4–12; frontend/src/pages/technician/Home.tsx:292 y siguientes; frontend/src/pages/technician/History.tsx:115.

Badge espera type/value y muestra String(value), pero esas páginas envían variant/children. Por lectura del código, el texto resultante es `undefined` y se ignoran los textos suministrados. No se comprobó visualmente en navegador.

Propuesta: unificar la interfaz de Badge y sus consumidores. El script build solo ejecuta vite build, aunque el Dockerfile afirma comprobar TypeScript; añadir comprobación de tipos real antes del empaquetado.

### 6. Media: los errores de carga se presentan como jornada no iniciada

Ubicación: frontend/src/pages/technician/Home.tsx:104–119.

Si falla cualquiera de las dos consultas de Promise.all, se muestra not_started. Un fallo de tareas, permisos o servidor puede sugerir incorrectamente al técnico que debe registrar otra entrada.

Propuesta: estado de error con reintento y carga independiente de jornada y tareas. Tras registrar una entrada correctamente, un fallo posterior al recargar tareas debe informar sobre las tareas, sin afirmar que falló la entrada.

### 7. Media: reportes formatean dos veces las horas y omiten minutos

Ubicación: backend/app/api/v1/admin/reports.py:40; frontend/src/pages/admin/Reports.tsx:83–100 y 194–195.

La API devuelve texto como `1:30 PM`; la pantalla lo interpreta como HH:MM y vuelve a agregar AM/PM, produciendo texto como `1:30 PM AM`. El marcador `—` tampoco se procesa correctamente. La duración descarta los minutos: 8 h 59 min se muestra como 8 h.

Propuesta: un único contrato horario, representar ausencia con null y mostrar horas y minutos. Definir el promedio para turnos que cruzan medianoche y decidir cómo incluir técnicos inactivos en reportes históricos; actualmente se filtran fuera por Technician.is_active.

### 8. Media: la lista de Usuarios queda limitada a los primeros 50

Ubicación: backend/app/api/v1/admin/users.py:55–56; frontend/src/pages/admin/Users.tsx:35.

El backend pagina con tamaño 50; la pantalla no solicita más páginas ni ofrece paginación. Los usuarios adicionales quedan inaccesibles desde esta lista.

Propuesta: conservar total/page/pages en el cliente e incorporar paginación y búsqueda del servidor.

### 9. Media: los webhooks configurables no se ejecutan

Ubicación: backend/app/services/webhook.py y backend/app/services/workday.py:11.

Existe send_webhook y variables de configuración, pero la búsqueda de referencias no encuentra invocaciones. El comentario sobre ejecución en segundo plano no corresponde a una implementación.

Propuesta: si estas integraciones forman parte del alcance, conectar los eventos con una cola persistente de entregas, reintentos e identificadores para evitar duplicados.

### 10. Media: el despliegue limpio no tiene un alta inicial de administrador documentada

Ubicación: backend/app/main.py:32; backend/app/db/init_db.py; README_DEPLOY.md; docker-compose.yml.

El seed corre solo en development; Docker fija production y las migraciones crean tablas sin usuario inicial. Los endpoints de altas requieren un administrador. La guía no resuelve este paso y contiene un dominio distinto del Compose.

Propuesta: comando explícito de inicialización del primer administrador con credenciales proporcionadas por el operador, sin credenciales demo; actualizar la guía y probar el arranque sobre una base vacía.

## Mejoras posteriores

- PWA: definir si el alcance es solo abrir la interfaz offline o también registrar operaciones. Hoy el service worker excluye la API y no hay cola de sincronización. Si se necesitan registros offline, distinguir claramente pendientes y confirmados, con idempotencia y tratamiento de hora del dispositivo.
- Accesibilidad: los modales carecen de role=dialog, aria-modal, gestión de foco y cierre con Escape; varios botones de iconos no tienen nombre accesible.
- Seguridad de sesión: evaluar refresh token en cookie HttpOnly con protecciones CSRF apropiadas. Actualmente ambos tokens persisten en localStorage. No se demostró una vulnerabilidad XSS en esta auditoría.
- Validación: comprobar latitud, longitud y precisión; actualmente el esquema acepta floats opcionales sin rangos. Si GPS es obligatorio, la API debe reflejar esa regla, no solo la pantalla.
- Operación: documentar y probar respaldos/restauración, alertas de errores y recuperación de despliegues. El volumen de PostgreSQL por sí solo no demuestra que exista una política de respaldo.
- Calidad: lockfile, comprobación TypeScript, lint configurado y pruebas integrales de sesión, altas, jornada nocturna, estados de tareas, reportes y actualización de PWA. Revisar dependencias contra avisos vigentes antes de desplegar; no se afirma aquí que una versión concreta sea vulnerable.

## Orden propuesto

1. Corregir renovación de sesión, jornadas anteriores y altas de técnicos, con pruebas de regresión.
2. Corregir estados de tareas, etiquetas visuales, errores de carga, reportes y paginación.
3. Verificar despliegue limpio y migraciones sobre PostgreSQL; después abordar offline, integraciones, accesibilidad y operación según necesidades reales.
