# Contraseñas personales y sucursales

Release accounts-20260921-r1, migración 0006.

## Acceso

Las cuentas existentes conservan la contraseña actual, pero deben establecer una personal para continuar. Las nuevas cuentas y los restablecimientos desde Personal usan una contraseña temporal. El cambio se exige en el servidor y en la interfaz para ambos roles; no basta con ocultar una pantalla. Mi cuenta permite cambios posteriores indicando la contraseña actual.

Las contraseñas personales requieren 12 caracteres como mínimo y un máximo de 72 bytes UTF-8, sin reglas arbitrarias de símbolos. Se permite pegar y usar gestores de contraseñas; se confirma la nueva contraseña y se permite mostrarla. No se admiten contraseñas idénticas a la anterior. Los administradores no pueden consultar contraseñas guardadas.

Cada cambio/restablecimiento incrementa la versión de credenciales y revoca los refresh tokens. Los access tokens anteriores dejan de funcionar inmediatamente. El usuario inicia sesión nuevamente con su contraseña personal. Las operaciones de cambio, restablecimiento y administración se auditan sin registrar claves ni enlaces.

## Recuperación

Desde Olvidé mi contraseña se solicita un enlace al correo registrado. Requiere un correo real y accesible, que se administra en Personal. Si no tiene acceso al correo, el administrador puede restablecer una contraseña temporal.

El enlace aleatorio vence en 30 minutos. Solo se guarda su hash; un uso invalida los demás enlaces de la versión anterior. La solicitud no cambia la contraseña ni cierra sesiones. Se devuelve el mismo mensaje para cuentas inexistentes o inactivas; se limita por IP y por cuenta. Cambiar el correo registrado invalida enlaces anteriores. La URL lleva el token en el fragmento, no en la petición HTTP, y la pantalla lo retira de la barra al abrirlo. Abrir el enlace no lo consume: se requiere enviar la nueva contraseña.

Correo por IONOS con TLS y configuración privada existente del VPS. Un fallo se registra sin revelar dirección, token o credenciales. No hay reintentos automáticos del correo de recuperación; el usuario puede solicitar otro enlace después de dos minutos, respetando el límite por IP. No se envían invitaciones masivas al desplegar.

## Catálogo

19 ubicaciones iniciales: 14 de EL POLLO LOCO, tres de TACO PALENQUE, TP Cocina y Oficinas Centrales. El administrador puede agregar y activar/desactivar desde Sucursales. Duplicados dentro del mismo grupo se rechazan. Cambios de estado concurrentes se detectan por revisión.

Crear tareas administrativas o actividades del técnico requiere elegir una ubicación activa. El backend resuelve y guarda el nombre oficial; no confía en texto enviado por el cliente. Los dos Santiago se distinguen por marca.

Las tareas existentes no se reasignan automáticamente. Conservan ubicación original y pueden completarse/cancelarse. Al editar una tarea antigua se requiere elegir una ubicación del catálogo. Desactivar una sucursal no borra sus tareas ni cambia el historial.

## Despliegue

Respaldar base, código e imágenes; migrar y verificar en clon PostgreSQL sin correo externo antes de activar. La migración agrega dos campos de usuarios, la tabla de recuperación, catálogo y referencia opcional en tareas. No modifica contraseñas ni registros de jornadas/tareas.

La imagen de reversión incluye la migración para reconocer el esquema; regresar a la versión anterior suspendería la exigencia de contraseña personal y la validación del catálogo. Conservar el nuevo código para la operación normal.
