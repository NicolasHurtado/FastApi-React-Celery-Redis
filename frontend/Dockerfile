# Etapa de construcción
FROM node:18-alpine as build

WORKDIR /app

# Copiar package.json y package-lock.json (o yarn.lock)
COPY package*.json ./
# COPY yarn.lock ./

# Instalar dependencias
RUN npm install
# RUN yarn install

# Copiar el resto del código fuente
COPY . .

# Construir la aplicación para producción
RUN npm run build
# RUN yarn build

# Etapa de producción
FROM nginx:1.25-alpine

# Copiar la build de la etapa anterior
COPY --from=build /app/build /usr/share/nginx/html

# Copiar configuración personalizada de Nginx si es necesario
# COPY nginx.conf /etc/nginx/conf.d/default.conf

# Exponer el puerto 80
EXPOSE 80

# Comando para iniciar Nginx
CMD ["nginx", "-g", "daemon off;"] 