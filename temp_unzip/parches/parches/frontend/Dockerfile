# frontend/Dockerfile  —  build de Vite + nginx que además hace de proxy de /api
FROM node:20-alpine AS build
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
# tsc primero: que un error de tipos rompa el build, no la producción.
RUN npm run build

FROM nginx:1.27-alpine
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 80
