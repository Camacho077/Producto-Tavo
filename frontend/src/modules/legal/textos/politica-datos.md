> **BORRADOR PENDIENTE DE REVISIÓN POR ABOGADO.** Este documento no es definitivo ni constituye asesoría jurídica. Los datos entre corchetes deben completarse antes de publicarlo.

# Política de tratamiento de datos personales

Versión {{version}}. Elaborada conforme a la Ley Estatutaria 1581 de 2012, el Decreto 1377 de 2013 (compilado en el Decreto Único 1074 de 2015) y demás normas que los modifiquen o complementen.

## 1. Quiénes somos

{{razonSocial}}, identificada con NIT {{nit}}, con domicilio en {{direccion}}, {{ciudad}}, Colombia (en adelante, "{{marca}}"), presta un software de gestión empresarial en la nube (ERP) a empresas.

Canal de atención para titulares de datos: **{{correoDatos}}** · Teléfono: {{telefono}}.

## 2. En qué calidad tratamos los datos

{{marca}} actúa en dos calidades distintas, y es importante diferenciarlas:

- **Como Responsable**, sobre los datos de las personas que crean y usan una cuenta en la plataforma (nombre, correo electrónico, empresa a la que pertenecen, rol y registros de acceso), y sobre los datos de contacto de nuestros clientes para facturación y soporte.
- **Como Encargado**, sobre los datos que cada empresa cliente registra en la plataforma para su operación: proveedores, clientes, pedidos, direcciones de entrega, teléfonos, números de documento y similares. **Esos datos pertenecen a la empresa cliente, que es su Responsable**: ella decide qué datos registra, para qué y por cuánto tiempo, y debe contar con la autorización de sus titulares. {{marca}} solo los trata por cuenta de la empresa cliente y siguiendo sus instrucciones, bajo el contrato de transmisión de datos que hace parte de los Términos y condiciones.

## 3. Datos que tratamos como Responsable

- **Datos de cuenta**: nombre completo, correo electrónico, contraseña (guardada solo como huella cifrada con bcrypt, nunca en texto plano), empresa, rol y permisos.
- **Datos de uso**: registro de las operaciones hechas en la plataforma (quién creó, anuló o modificó un documento y cuándo), necesario para la trazabilidad del inventario.
- **Prueba de la autorización**: documento aceptado, versión y fecha y hora de la aceptación.

No recolectamos datos sensibles (artículo 5 de la Ley 1581) ni datos de niñas, niños o adolescentes. La plataforma no está dirigida a menores de edad.

## 4. Finalidades

Tratamos los datos de los que somos Responsables para:

1. Crear y administrar la cuenta, autenticar el acceso y aplicar los permisos de cada rol.
2. Prestar el servicio contratado, incluida la trazabilidad de las operaciones.
3. Brindar soporte técnico y atender solicitudes.
4. Facturar y gestionar el contrato.
5. Enviar comunicaciones operativas sobre el servicio (cambios, mantenimientos, seguridad).
6. Cumplir obligaciones legales y atender requerimientos de autoridades competentes.

No vendemos ni cedemos datos personales a terceros con fines comerciales.

## 5. Datos guardados en el navegador

La plataforma **no usa cookies** ni herramientas de analítica, publicidad o seguimiento de terceros. En el almacenamiento local del navegador (`localStorage`) se guardan únicamente:

- **`js_company_token`**: la credencial de la sesión iniciada. Es estrictamente necesaria para que la plataforma funcione; se borra al cerrar sesión.
- **`js_company_modo`**: la preferencia de modo claro u oscuro.

Ninguno de los dos se comparte con terceros. Pueden borrarse en cualquier momento desde la configuración del navegador.

## 6. Derechos de los titulares

Conforme al artículo 8 de la Ley 1581 de 2012, el titular tiene derecho a:

1. **Conocer, actualizar y rectificar** sus datos personales.
2. **Solicitar prueba de la autorización** otorgada.
3. **Ser informado** sobre el uso que se ha dado a sus datos.
4. **Presentar quejas** ante la Superintendencia de Industria y Comercio (SIC) por infracciones a la ley, una vez agotado el trámite de consulta o reclamo ante {{marca}}.
5. **Revocar la autorización y/o solicitar la supresión** de sus datos cuando no se respeten los principios, derechos y garantías legales, siempre que no exista un deber legal o contractual de conservarlos.
6. **Acceder en forma gratuita** a sus datos personales.

Si sus datos fueron registrados por una empresa cliente (por ejemplo, como proveedor o cliente de esa empresa), la solicitud debe dirigirse a esa empresa, que es la Responsable. Si nos llega a nosotros, la trasladaremos a la empresa cliente e informaremos al titular.

## 7. Cómo ejercer los derechos

Escriba a **{{correoDatos}}** indicando nombre, número de identificación, la solicitud concreta y un medio de respuesta. Puede actuar el titular, su causahabiente, su representante o apoderado, acreditando esa calidad.

- **Consultas**: se responden en un máximo de **diez (10) días hábiles** desde su recibo. Si no es posible en ese plazo, se informará el motivo y la nueva fecha, que no superará **cinco (5) días hábiles** adicionales (artículo 14 de la Ley 1581).
- **Reclamos** (corrección, actualización, supresión o incumplimiento): se atienden en un máximo de **quince (15) días hábiles**, prorrogables hasta **ocho (8) días hábiles** más informando el motivo. Si el reclamo está incompleto, se pedirá completarlo dentro de los cinco (5) días siguientes; si pasan dos (2) meses sin respuesta del interesado, se entenderá desistido (artículo 15 de la Ley 1581).

## 8. Seguridad

Aplicamos medidas técnicas, humanas y administrativas para proteger los datos: contraseñas cifradas con bcrypt, acceso solo con sesión autenticada, separación lógica de los datos de cada empresa cliente en todas las consultas, permisos por rol verificados en el servidor y conexiones cifradas en producción. Ningún sistema es infalible; ante un incidente de seguridad informaremos a los afectados y a la SIC en los términos de ley.

## 9. Transmisión de datos y proveedores

Los servidores y la base de datos de la plataforma están alojados con {{hosting}}, en {{paisHosting}}, que actúa como subencargado bajo contrato que le exige las mismas medidas de seguridad y confidencialidad. Si los servidores se ubican fuera de Colombia, la transmisión se rige por el contrato de transmisión previsto en el artículo 25 del Decreto 1377 de 2013.

El módulo de Sugerencias IA se calcula **dentro de la plataforma**: no se envía información a proveedores de inteligencia artificial ni a ningún otro tercero, y no usa datos personales de los clientes del Cliente (solo cantidades, montos, fechas y productos). Si en el futuro se incorporara un proveedor externo, esta política se actualizará antes y se informará a los titulares.

## 10. Conservación

Los datos de cuenta se conservan mientras la cuenta esté activa y, después, durante el tiempo necesario para cumplir obligaciones legales, contables o contractuales. Los datos de la empresa cliente se conservan y se eliminan según lo previsto en los Términos y condiciones (portabilidad y eliminación al terminar el contrato).

## 11. Área responsable

La atención de peticiones, consultas y reclamos está a cargo de [CARGO O ÁREA RESPONSABLE POR COMPLETAR], a través de {{correoDatos}}.

## 12. Vigencia y cambios

Esta política rige desde [FECHA DE ENTRADA EN VIGENCIA POR COMPLETAR]. Cualquier cambio sustancial se informará antes de aplicarse y, cuando cambie la finalidad del tratamiento, se pedirá una nueva autorización. Cada versión queda identificada con su número; la plataforma registra qué versión aceptó cada usuario.
