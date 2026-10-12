# Automatizaciones

Esta carpeta agrupa los scripts que **no son parte del producto en sí**,
sino de la operación interna (Producto Tavo, derivado del Producto JS) y de cada despliegue a cliente.

## /deploy
- `alta_tenant.py`: crea un `Tenant` con su rol Administrador y su primer
  usuario desde la línea de comandos.
- `seed_demo.py`: carga datos de ejemplo (categorías, proveedores,
  productos, una compra confirmada, una venta y un pedido) en un tenant ya
  existente, de forma idempotente.

## /dev
- `verificar-puertos.ps1`: revisa los puertos del producto (frontend 5175,
  preview 4175, backend 8002, Postgres 5433, n8n 5679) antes de arrancar y
  dice si alguno está reservado por Windows u ocupado, y por qué proceso o
  contenedor. `-Servicios backend,frontend` revisa solo esos.
- `start-backend.ps1` / `start-frontend.ps1`: arrancan cada servicio en su
  puerto fijo (8002 / 5175) cerrando antes la instancia vieja DE ESTE
  producto, y solo esa: nunca "todo uvicorn" o "todo vite", porque el
  Producto JS corre a la vez en la misma máquina (5173 / 8001).
- `comun.ps1`: mapa de puertos y cierre acotado, compartido por los scripts.

## /demo
- `start-demo-tunel.ps1`: levanta en un solo comando la demo compartible
  por internet (backend 8002 + túnel, build del frontend en modo `tunnel`,
  `vite preview` 4175 + túnel), verifica MIME y CORS por el túnel e imprime
  la URL a compartir. `-Forzar` libera los puertos; `-SoloProbar` hace el
  flujo completo y cierra (para verificar). Logs en `demo/logs/`.

## /ci
- `pre-deploy.ps1`: corre tests de backend y frontend, `alembic check`,
  lint y build. Debe pasar en verde antes de cualquier despliegue.

Cada script debe ser autocontenido y documentar en un comentario inicial:
qué hace, cuándo se espera que corra y qué variables de entorno necesita.
