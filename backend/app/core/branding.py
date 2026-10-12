"""
BRANDING DEL PRODUCTO (2026-10-12) — nombre del producto en el backend.

El producto se vende a varios restaurantes: su nombre NO es el de ningún
cliente. Lo que cada restaurante configura (nombre, NIT, dirección, logo de
la comanda y la factura) vive en `Tenant` y se edita en Ajustes.

El archivo de branding del producto es `frontend/src/config/branding.jsx`
(nombre + logo provisional). Este módulo es su espejo para lo que arma el
backend (PDF, título de la API); `tests/test_branding.py` exige que el nombre
coincida en los dos lados.
"""

# Nombre provisional del producto (decisión del 2026-10-12).
NOMBRE_PRODUCTO = "JS Restaurante"

# Empresa que presta el servicio (responsable de las cuentas en la política
# de datos). No cambia con el nombre del producto.
EMPRESA_PROVEEDORA = "JS Company"
