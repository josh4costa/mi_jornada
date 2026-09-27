# Guía de Despliegue en VPS (Con Traefik preexistente)

Esta guía asume que estás subiendo la plataforma al VPS `49.12.67.202` que ya tiene `Traefik` corriendo y expuesto al puerto 80/443.

## Paso 1: Subir el código
Sube el código de este proyecto al servidor (puedes copiar la carpeta completa usando `scp` o Git). 
Ponlo junto a tus otras apps (por ejemplo, `/opt/mi_jornada/` o la ruta equivalente donde tengas `asistencias`).

## Paso 2: Configurar las variables de entorno
Dentro de la carpeta del proyecto en el servidor, copia el `.env`:

```bash
cp .env.example .env
nano .env
```
Asegúrate de llenar `POSTGRES_PASSWORD` y `SECRET_KEY`.

## Paso 3: Configurar el Subdominio (Importante)
Abre el archivo `docker-compose.yml` e identifica la línea de Traefik:
```yaml
- "traefik.http.routers.myjornada.rule=Host(`myjornada.pleg.com.mx`)"
```
Cámbiala por el dominio/subdominio que vayas a usar. (¡Y asegúrate de que el DNS de ese subdominio apunte a la IP `49.12.67.202`!).

## Paso 4: Construir y Levantar
Ejecuta el siguiente comando para construir y enlazar el stack de Mi Jornada a Traefik:

```bash
docker compose up -d --build
```

**¡Eso es todo!** 
Traefik automáticamente detectará el nuevo contenedor `mi_jornada_frontend`, solicitará el certificado SSL de Let's Encrypt y enrutará el tráfico del subdominio de forma segura sin afectar a `asistencias`, `metabase` ni las demás apps.


## Inicialización, actualización y recuperación

Consultar [OPERACION.md](OPERACION.md) para crear el primer administrador, aplicar la migración de webhooks, reparar perfiles existentes y generar/verificar respaldos. Una instalación nueva requiere crear su administrador antes de iniciar sesión.
