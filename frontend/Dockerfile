FROM node:20-alpine

WORKDIR /app

COPY package*.json ./
RUN npm install

COPY . .

EXPOSE 5175

# Vite directo, sin el "predev" de npm: liberar-puerto.mjs usa lsof, y el de
# busybox (Alpine) ignora sus filtros, lista TODOS los procesos y el script
# terminaba matándose a sí mismo (SIGKILL). En un contenedor nuevo no hay
# ningún Vite viejo que cerrar.
CMD ["npx", "vite", "--host"]
