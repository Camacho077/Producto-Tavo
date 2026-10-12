# Legal y datos personales (Colombia) — estado al 2026-09-30

> Todo lo de esta carpeta y los textos de la plataforma son **BORRADORES pendientes de revisión por abogado**. Los datos de la empresa están como marcadores `[POR COMPLETAR]` en `frontend/src/config/empresa.js` (un solo lugar: pie y documentos se actualizan juntos).

Contexto: JS Company es un ERP **detrás de login** que se vende a empresas. No es un sitio público de marketing; no aplican reseñas, SEO ni banners de landing.

## 1. Documentos

| Documento | Dónde vive | Dónde se ve |
|---|---|---|
| Política de tratamiento de datos (Ley 1581/2012, Decreto 1377/2013) | `frontend/src/modules/legal/textos/politica-datos.md` | `/legal/privacidad` — pie de todas las pantallas y casilla del registro |
| Términos y condiciones | `frontend/src/modules/legal/textos/terminos.md` | `/legal/terminos` — mismo acceso |
| Cláusula de transmisión de datos (Responsable → Encargado) | `docs/legal/clausula-transmision-datos.md` | Anexo del contrato con cada cliente |

**Versiones**: `backend/app/core/legal.py` (manda) y su espejo `frontend/src/config/legal.js`. Si se cambia un texto de forma sustancial, se sube la versión en los dos (lo exige `legal.test.jsx`).

**Prueba de la autorización**: el registro exige una casilla **desmarcada por defecto**. El backend rechaza el alta sin ella (422 con la causa) y guarda en `aceptaciones_legales` una fila por documento con versión, fecha y hora UTC, usuario y correo. Si el usuario se elimina, la fila se conserva (`usuario_id` pasa a NULL, queda el correo). Lo cubren `tests/test_aceptacion_legal.py` y `RegistroPage.test.jsx`. Verificado en vivo el 2026-09-30: registro real por la interfaz → 2 filas con versión `1.0-borrador-2026-09-30`.

Empresas creadas ANTES de esta función (y las creadas con `alta_tenant.py`) no tienen fila: su aceptación debe recogerse por contrato o con una futura pantalla de "acepta la nueva versión".

## 2. Roles frente a la Ley 1581

- **JS Company es Responsable** de los datos de las cuentas (usuarios de la plataforma) y de los contactos comerciales de sus clientes.
- **Cada empresa cliente es Responsable** de los datos que registra (proveedores, clientes, pedidos, direcciones, documentos), y **JS Company es su Encargado**. Por eso la cláusula de transmisión va en el contrato.

## 3. ¿Hay que inscribir bases de datos en el RNBD de la SIC?

El criterio **no es el volumen de registros sino el tamaño de la empresa Responsable**. Desde el Decreto 090 de 2018 (que modificó el Decreto 1074 de 2015), solo están obligados a inscribir sus bases en el Registro Nacional de Bases de Datos:

- las sociedades y entidades sin ánimo de lucro con **activos totales superiores a 100.000 UVT**, y
- las personas jurídicas de naturaleza pública.

Consecuencias para este producto:

- **JS Company**: debe inscribir sus propias bases (cuentas, clientes) solo si sus activos superan 100.000 UVT. Como Encargado **no** inscribe las bases de sus clientes.
- **Cada cliente**: decide su propia obligación según sus activos. La plataforma no lo hace por él.
- Valor de referencia: con la UVT de 2025 (49.799 COP), 100.000 UVT ≈ 4.980 millones de pesos. **Verificar la UVT vigente del año** y confirmar con el abogado.

Aunque no haya obligación de inscribir, sí aplican la política de tratamiento, la autorización y la atención de derechos.

## 4. Auditoría de almacenamiento en el navegador (cookies)

Medido en vivo el 2026-09-30 (build de producción, sesión por 7 pantallas, cambio de tema) y en el código:

```
Cookies (todas, incl. HttpOnly): ninguna
localStorage:  js_company_token (sesión, JWT) · js_company_modo (tema claro/oscuro)
sessionStorage, IndexedDB, Cache API, Service Workers: vacíos
Hosts contactados: solo el frontend propio y el backend propio
Backend: ningún set_cookie; el login devuelve el token en el cuerpo JSON
```

**Decisión**: sin banner de cookies. Lo guardado es estrictamente necesario (sesión) o una preferencia del propio usuario (tema), nada rastrea ni se comparte. Se informa en la sección 5 de la Política. Si algún día se agrega analítica o cualquier servicio de terceros en el navegador, esta decisión debe revisarse ANTES de publicarlo.

## 5. Servicios externos que tocan datos

| Servicio | Qué datos | Estado |
|---|---|---|
| Hosting y base de datos de producción | Todos | **Por definir** (`EMPRESA.hosting`). Será subencargado: requiere contrato y, si está fuera de Colombia, transmisión internacional bajo el art. 25 del Decreto 1377. |
| Túnel de demostración (`loca.lt`, `automatizaciones/demo/`) | Lo que se muestre en la demo | Solo para demos. Usar con datos de prueba, nunca con datos reales de un cliente. |
| Analítica, publicidad, CDN, correo, IA externa | — | **No hay.** El backend no hace conexiones salientes y el navegador solo habla con los servidores propios. |

**Fuentes de Google**: evaluado. Ya se sirven **localmente** desde el propio paquete (`@fontsource/inter`, `@fontsource/playfair-display`, `@fontsource/jetbrains-mono`), sin pedir nada a `fonts.googleapis.com` ni a `fonts.gstatic.com`. No hay que cambiar nada.

## 6. Licencias de imágenes, iconos y fuentes

| Recurso | Origen | Licencia |
|---|---|---|
| Renders 3D (`frontend/src/assets/3d/*.svg`) | Generados para el proyecto (`frontend/scripts/generar-renders-3d.py`) | CC0 1.0 (ver `assets/3d/LICENSE.md`) |
| `frontend/public/fondo-auth.jpg` | "Green leaves and foliage", Łukasz Rawa, Unsplash; duotono propio de la paleta | Licencia Unsplash (uso comercial, sin atribución obligatoria). **Ya no se descarga**: el login no lleva foto desde el 2026-09-30. |
| Iconos (`lucide-react`) | Lucide | ISC |
| Inter, Playfair Display, JetBrains Mono (`@fontsource`) | Google Fonts / JetBrains, servidas localmente | SIL Open Font License 1.1 |
| **`frontend/public/favicon.svg`** | Exportado de Figma; ya estaba en el primer commit del repositorio | **ORIGEN POR VERIFICAR.** No hay registro de quién lo diseñó ni bajo qué licencia. Confirmar que es propio o reemplazarlo por una marca propia antes de vender. |

## 7. Pendientes para el abogado y para completar

1. Todos los `[POR COMPLETAR]`: razón social, NIT, dirección, ciudad, correos, teléfono, área responsable, fecha de vigencia, proveedor y país de hosting.
2. Términos: precios y módulos por plan, periodicidad de pago, días de gracia, prueba gratuita, disponibilidad (%), tiempos de soporte, plazo de portabilidad, tope de responsabilidad, mecanismo de solución de controversias.
3. Si al Cliente le aplica el Estatuto del Consumidor (Ley 1480 de 2011), en particular el derecho de retracto del artículo 47.
4. Recoger la aceptación de las empresas que ya existen.
5. Exportación CSV de los listados (los Términos la anuncian como "en desarrollo"; es la tarea técnica n.º 3 de `CLAUDE.md`).
6. Origen y licencia del favicon.

## 2026-10-02 — Versión 1.1 de los borradores

- **Política 1.1**: §9 aclara que las Sugerencias IA se calculan dentro de la
  plataforma, sin proveedores de IA ni datos personales de los clientes del
  Cliente (detalle técnico en `docs/ia/README.md`).
- **Términos 1.1**: §2 planes con módulos adicionales y acceso por plan
  exigido también en la API; §8 portabilidad con exportación CSV de los
  nueve listados en cualquier momento y sin costo; §10 las Sugerencias IA
  son apoyo estadístico, no asesoría.
- Versiones en `backend/app/core/legal.py` (`1.1-borrador-2026-10-02`) y su
  espejo `frontend/src/config/legal.js`. Las aceptaciones anteriores
  conservan la versión 1.0 que se aceptó.
- **Auditoría de cookies repetida en vivo** (tras el rediseño, la precarga y
  la IA): `document.cookie` vacío, ninguna `Set-Cookie` en un login real ni
  en el código, `localStorage` solo con `js_company_token` y
  `js_company_modo`, sin `sessionStorage`, IndexedDB ni service workers, y
  el navegador solo contacta al frontend y al backend propios. **Sigue sin
  requerirse banner de cookies.**
- Pendiente del cliente (no se inventa): razón social, NIT, correo y ciudad
  en `frontend/src/config/empresa.js`, módulos por plan y plazos entre
  corchetes. Todo sigue siendo BORRADOR pendiente de abogado.
