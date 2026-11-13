# Envío automático del reporte en PDF a los alumnos — diseño

Fecha: 2026-11-12 · Rama: `envio-automatico-reportes`

## Intención y motivo

Hoy el alumno ve sus resultados en pantalla y puede descargar el PDF, pero la coordinación no tiene forma de
asegurar que cada alumno conserve su reporte, y entregarlo a mano a ~174 alumnos no escala. Se quiere que, al
terminar su último test, el alumno reciba su «Reporte de Evaluación Integral» (el mismo PDF de `pdf_individual`)
en su correo, sin intervención de la coordinación.

## Metas

- Al terminar el último test, el PDF llega por correo al alumno sin que nadie haga nada.
- Un envío fallido no se pierde: queda registrado con su motivo y la coordinación lo reintenta desde `/admin`.
- Un alumno nunca recibe el mismo reporte dos veces por reejecuciones de Streamlit.
- La coordinación ve en `/admin` el estado del envío de cada alumno.

## No metas

- Rebotes de correo, seguimiento de aperturas, plantillas HTML, boletines o cualquier otro correo al alumno.
- Cambiar a un proveedor de correo con API (Resend, Brevo). Se deja la puerta abierta, no se implementa.
- Enviar al tutor o a la coordinación una copia de los reportes.

## Anti-metas (sería un fracaso aunque «funcione»)

- Mandar resultados vocacionales a una dirección equivocada: por eso el correo se pide dos veces.
- Que un fallo del servidor de correo impida al alumno ver o descargar sus resultados.
- Guardar o registrar (logs, mensajes de error) la contraseña SMTP o el contenido del PDF.

## Decisiones del usuario

- **El correo se pide en el registro** (opción A), con campo de confirmación. Se guarda en `alumnos.correo`.
- **Cuándo:** al terminar el último test, con un botón «Enviar reportes pendientes» en `/admin` como respaldo.
- **Cómo:** SMTP desde una cuenta de Gmail creada solo para esto (verificación en dos pasos + contraseña de
  aplicación), credenciales en `st.secrets`. El usuario crea la cuenta; el código no puede hacerlo.
- El aviso de privacidad se actualiza para mencionar el correo y su único uso.

## Diseño

### Datos (migración `sql/06_correo_y_envio_reporte.sql`, segura de repetir)

`alumnos` gana: `correo text` (nulo en alumnos ya registrados), `reporte_estado text` (`pendiente` por defecto |
`enviando` | `enviado` | `error`), `reporte_enviado_en timestamptz`, `reporte_reservado_en timestamptz` (cuándo se
tomó la reserva; sirve para vencerla), `reporte_error text`. Check de formato básico del correo. RLS y revocaciones sin cambios.

### Registro (`modules/security.py`, `modules/acceso.py`, `views/alumno.py`)

- Campos «Correo electrónico» y «Confirma tu correo». Validación en `security.validar_datos`: formato razonable,
  minúsculas y sin espacios, y ambos campos iguales (los textos de error son mostrables al alumno).
- `DatosAcceso`, `Alumno`, `Repositorio.crear_alumno` y `actualizar_datos` incorporan `correo`.
- Al reanudar, el correo se actualiza si cambió, igual que edad, tutor y semestre. Un alumno ya registrado sin
  correo debe escribirlo antes de continuar (mismo formulario). **Cambia** `tests/test_db_repo.py:42`, que hoy
  exige que el correo no se envíe a la base.

### Envío (`modules/envio.py`, nuevo)

- `enviar_reporte(destino, nombre, pdf, config) -> None` envía por `smtplib` (SMTP_SSL, tiempo de espera de
  20 s) un correo de texto plano corto, sin datos de resultados en el cuerpo, con el PDF adjunto
  `resultados_<matricula>.pdf`. Lanza `EnvioError` con un mensaje que no incluye credenciales.
- `ConfigCorreo` se lee de `st.secrets["correo"]` (`servidor`, `puerto`, `usuario`, `contrasena`, `remitente`).
  Si falta, el envío se omite: el alumno no ve error, el estado queda `pendiente` y `/admin` avisa que falta
  configurar el correo.
- Lógica de estado (`modules/envio.py` o `modules/reporte_envio.py`, mismo estilo `Repositorio` que `acceso`):
  1. **Reservar:** `UPDATE alumnos SET reporte_estado='enviando' WHERE id=… AND reporte_estado IN
     ('pendiente','error') RETURNING id`. Si no devuelve fila, otro proceso ya lo tomó o ya se envió: no hacer nada.
  2. Generar el PDF con `pdf_individual` y enviar.
  3. Éxito → `enviado` + `reporte_enviado_en`. Fallo → `error` + `reporte_error` (mensaje corto y fijo en
     español; nunca el texto crudo de la excepción).
  4. Un `enviando` con más de 10 minutos se trata como fallido (proceso caído) y puede reservarse de nuevo.
- «Rehacer el Test N» (`reiniciar_alumno`) devuelve `reporte_estado` a `pendiente`, para que el PDF nuevo se
  envíe al terminar.

### Pantalla final (`views/test.py`, `_fin`)

Tras guardar resultados y generar el PDF, intenta el envío una sola vez por reserva. Mensajes bajo el reporte:
éxito «Te enviamos el reporte a x@… Revisa también la carpeta de spam.»; fallo «No pudimos enviarte el correo; tu
tutor podrá reenviártelo. Puedes descargar tu PDF aquí.» El botón de descarga existente no se toca. El envío no
puede lanzar excepciones hacia la vista.

### Panel `/admin` (`views/admin.py`, `modules/panel.py`)

Columna «Reporte» en la tabla de alumnos (`Enviado` / `Pendiente` / `Error` con el motivo). Botón «Enviar reportes
pendientes» con confirmación, que recorre a los alumnos con `estado='terminado'`, correo y envío `pendiente` o
`error`, y muestra el resumen (enviados / fallidos). Si falta la configuración, el botón está desactivado con la
razón.

### Aviso de privacidad (`config/aviso_privacidad.md`, `docs/aviso_privacidad_propuesta.md`)

Se agrega que se recoge el correo, que solo se usa para enviar el reporte de resultados al alumno y que se
guarda con el resto de sus datos. `PLAN.md` y `README.md` se actualizan donde dicen «No se pide correo».

## Decisiones mías (a confirmar al leer)

- Correo de texto plano, sin datos de resultados en el cuerpo.
- Tiempo de espera de 20 s y reserva vencida a los 10 minutos.
- Si no hay configuración de correo, el envío se omite en silencio para el alumno.
- Si `MOSTRAR_RESULTADO_AL_ALUMNO` es false, no se envía al terminar (sería entregar resultados que la
  coordinación decidió no mostrar); la coordinación los envía desde `/admin`.
- Puerto 465 = SMTP_SSL, 587 = STARTTLS, otro = SMTP sin cifrar (solo para pruebas locales). El login se hace
  solo si hay contraseña.
- El estado del envío se muestra en `/admin` como texto bajo el nombre del alumno (el campo `nota` de la fila),
  no como columna nueva: la lista usa filas a medida, no una tabla.
- Los 20 registros piloto se borran aparte (es una tarea previa del usuario, no parte de este cambio).

## Pruebas

Doble en memoria del repositorio (en `tests/fakes.py`) y un servidor SMTP falso (`smtplib` parcheado) para: formato
y coincidencia del correo, no duplicar el envío, éxito y fallo con su estado, reserva vencida, reinicio de test,
botón del panel con configuración ausente, y que ningún mensaje de error contenga la contraseña.
