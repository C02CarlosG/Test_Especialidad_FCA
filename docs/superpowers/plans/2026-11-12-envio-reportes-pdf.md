# Envío automático del reporte en PDF — Plan de implementación

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Que el alumno reciba por correo su PDF de «Reporte de Evaluación Integral» al terminar el último test, con reintento desde `/admin`.

**Architecture:** El correo se captura en el registro y se guarda en `alumnos`. Un módulo nuevo `modules/envio.py` arma y manda el correo por `smtplib` y lleva el estado del envío (reservar → enviado | error) a través de un `Repositorio`, igual que `acceso.py`; `SupabaseRepo` y `FakeRepo` lo implementan. La pantalla final (`views/test.py`) y el panel (`views/admin.py`) solo llaman a ese módulo.

**Tech Stack:** Python 3.11 (`.venv`, `uv`), Streamlit ≥1.66 (`AppTest` en pruebas), Supabase (PostgREST), `smtplib`/`email.message.EmailMessage` (sin dependencias nuevas), pytest.

**Spec:** `docs/superpowers/specs/2026-11-12-envio-reportes-pdf-design.md`

Pruebas: `.venv/bin/python -m pytest -q` (la `.venv` del proyecto; la del directorio padre está vacía). Línea base: 566 pruebas verdes.

## Global Constraints

- Sin dependencias nuevas en `requirements.txt`.
- Textos para el alumno y el coordinador en español, con acentos.
- El correo se normaliza (sin espacios, en minúsculas) y se rechaza si tiene espacios, saltos de línea, más de 254 caracteres o no cumple `^[^@\s]+@[^@\s]+\.[^@\s]+$`.
- Estados de envío exactos: `pendiente` | `enviando` | `enviado` | `error`.
- Tiempo de espera SMTP: 20 s. Reserva vencida: 10 minutos.
- Puerto 465 = `SMTP_SSL`, 587 = `SMTP` + `starttls()`, otro = `SMTP` sin cifrar (solo pruebas locales). `login` solo si hay contraseña.
- `reporte_error` guarda un mensaje fijo en español; nunca el texto de la excepción ni la contraseña.
- Ninguna excepción del envío llega a la vista del alumno.
- Cada tarea termina con la suite completa en verde y un commit (mensajes en español, terminados con `Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>`).

## Review Focus

- Correo con salto de línea o espacios (inyección de cabeceras): se rechaza en el registro (Task 1) y `enviar_reporte` no lo manda (Task 3).
- Correo en mayúsculas o con espacios alrededor: se guarda normalizado (Task 1).
- Streamlit vuelve a ejecutar `_fin` o hay dos pestañas: sale un solo correo (Tasks 3 y 4).
- SMTP caído, timeout o contraseña mala: el alumno ve sus resultados y el PDF, el estado queda `error` y el mensaje guardado no contiene la contraseña (Tasks 3 y 4).
- Alumno terminado sin correo (registrado antes de este cambio) o sin `[correo]` en secretos: no truena; el panel lo muestra y el botón explica por qué no envía (Task 5).

---

### Task 1: Correo en el modelo, la validación y el acceso

**Files:**
- Create: `sql/06_correo_y_envio_reporte.sql`
- Modify: `modules/security.py` (`validar_datos`, líneas 50-81), `modules/acceso.py` (`Alumno`, `DatosAcceso`, `Repositorio`, `_con_datos_nuevos`, `iniciar_acceso`), `modules/db.py` (`_alumno`, `_COLS_ALUMNO`, `crear_alumno`, `actualizar_datos`), `tests/fakes.py`, `tests/test_db_repo.py:42`
- Test: `tests/test_security.py`, `tests/test_acceso.py`, `tests/test_db_repo.py`

**Interfaces:**
- Produces:
  - `Alumno` gana, al final y con valores por defecto: `correo: str | None = None`, `reporte_estado: str = "pendiente"`, `reporte_error: str | None = None`.
  - `DatosAcceso` gana al final `correo: str = ""`, `correo_confirmacion: str = ""`.
  - `security.validar_datos(..., semestre=None, *, correo: str, correo_confirmacion: str)` (keyword-only, obligatorios); el dict devuelto incluye `"correo"` normalizado; los errores usan la clave `"correo"`.
  - `Repositorio.crear_alumno(..., semestre=None, correo: str | None = None)` y `Repositorio.actualizar_datos(alumno_id, edad, tutor, semestre, correo)`.

- [ ] **Step 1: Escribir las pruebas que fallan**
  - `tests/test_security.py`: `test_correo_valido_se_normaliza` (`"  Ana@Mail.COM "` con la misma confirmación → `v["correo"] == "ana@mail.com"`, sin errores); `test_correo_invalido_da_error` parametrizada con `""`, `"sin-arroba"`, `"a@b"`, `"a b@c.com"`, `"a@c.com\nBcc: x@y.com"`, `"a"*250 + "@c.com"` → `errores["correo"]` existe; `test_confirmacion_distinta_da_error` (`"a@c.com"` vs `"b@c.com"` → `errores["correo"] == "Los correos no coinciden."`).
  - `tests/test_acceso.py`: `test_el_correo_se_guarda_al_registrar` (el alumno creado en `FakeRepo` tiene `correo` normalizado); `test_reanudar_actualiza_el_correo` (reanuda con otro correo → `repo.alumnos[mat].correo` es el nuevo); `test_sin_correo_es_dato_invalido` (`DatosInvalidos` con `errores` que incluye `"correo"`).
  - `tests/test_db_repo.py`: reemplazar la aserción de la línea 42 (`"correo" not in enviado`) por `enviado["correo"] == "a@b.com"` llamando `crear_alumno(..., correo="a@b.com")`; añadir que `actualizar_datos` envía `correo` en el `update`.
  - Actualizar las llamadas existentes a `validar_datos`, `DatosAcceso(...)` y `actualizar_datos` en las pruebas con un correo válido (un helper `DATOS` o argumento por defecto en cada archivo de pruebas).

- [ ] **Step 2: Ejecutar y comprobar que fallan**

Run: `.venv/bin/python -m pytest tests/test_security.py tests/test_acceso.py tests/test_db_repo.py -q`
Expected: FAIL (`TypeError`/`KeyError` por los parámetros nuevos).

- [ ] **Step 3: Implementar**
  - `sql/06_correo_y_envio_reporte.sql` (seguro de repetir, con el encabezado de comentario en el estilo de `03_semestre.sql`): `alter table public.alumnos add column if not exists` para `correo text`, `reporte_estado text not null default 'pendiente' check (reporte_estado in ('pendiente','enviando','enviado','error'))`, `reporte_enviado_en timestamptz`, `reporte_reservado_en timestamptz`, `reporte_error text`; y una restricción `alumnos_correo_formato` (`correo is null or correo ~ '^[^@[:space:]]+@[^@[:space:]]+\.[^@[:space:]]+$'`) agregada de forma idempotente (`drop constraint if exists` + `add`).
  - `security.validar_datos`: normalizar con `.strip().lower()`; validar contra la regex y el máximo de 254; si el correo es válido y difiere de la confirmación (también normalizada) → `"Los correos no coinciden."`; mensajes: vacío/ inválido → `"Escribe un correo válido, por ejemplo nombre@dominio.com."`.
  - `acceso.py`: campos nuevos en `Alumno`/`DatosAcceso`; `iniciar_acceso` pasa `correo=` a `crear_alumno`; `_con_datos_nuevos` compara y actualiza también el correo con `repo.actualizar_datos(id, edad, tutor, semestre, correo)`.
  - `db.py`: `_alumno` lee `correo`, `reporte_estado`, `reporte_error` con `fila.get(...)`; `_COLS_ALUMNO` los incluye; `crear_alumno` y `actualizar_datos` envían `correo`.
  - `tests/fakes.py`: `FakeRepo.crear_alumno` y `actualizar_datos` aceptan y guardan `correo`.

- [ ] **Step 4: Ejecutar y comprobar que pasan**

Run: `.venv/bin/python -m pytest -q`
Expected: toda la suite en verde (las pruebas de vista del alumno aún no piden correo: se ajustan en la Task 2).

- [ ] **Step 5: Commit**

```bash
git add sql/06_correo_y_envio_reporte.sql modules tests
git commit -m "Guarda y valida el correo del alumno en el registro"
```

---

### Task 2: Campos de correo en el formulario y aviso de privacidad

**Files:**
- Modify: `views/alumno.py` (`_registro`, formulario en líneas 69-98), `config/aviso_privacidad.md`, `docs/aviso_privacidad_propuesta.md`
- Test: `tests/test_alumno_view.py`, `tests/test_app.py` (si arma el registro)

**Interfaces:**
- Consumes: `DatosAcceso(..., correo=..., correo_confirmacion=...)` de la Task 1.

- [ ] **Step 1: Escribir las pruebas que fallan** en `tests/test_alumno_view.py`: `test_el_registro_pide_correo_y_confirmacion` (existen `text_input` con etiquetas «Correo electrónico *» y «Confirma tu correo *»); `test_correos_distintos_muestran_error_y_no_registran` (aparece `"Los correos no coinciden."` y `repo.alumnos` sigue vacío); `test_registro_con_correo_guarda_al_alumno`. Ajustar el helper que llena el formulario (`_nuevo`) para escribir el correo en ambos campos.

- [ ] **Step 2: Ejecutar y comprobar que fallan**

Run: `.venv/bin/python -m pytest tests/test_alumno_view.py -q`
Expected: FAIL (no existen los campos).

- [ ] **Step 3: Implementar** en `_registro`: una fila `st.columns(2)` con `text_input("Correo electrónico *", max_chars=254, autocomplete="email", key="reg_correo", help="Aquí te llegará tu reporte en PDF al terminar.")` y `text_input("Confirma tu correo *", max_chars=254, key="reg_correo2")` entre la fila de semestre/edad y la del tutor; pasar ambos a `DatosAcceso`. Aviso de privacidad (ambos archivos): párrafo nuevo que diga que se recoge el correo electrónico, que solo se usa para enviar al alumno el reporte de sus resultados y que se conserva con el resto de sus datos. Respetar el tono y formato de los párrafos existentes.

- [ ] **Step 4: Ejecutar y comprobar que pasan**

Run: `.venv/bin/python -m pytest -q`
Expected: suite en verde.

- [ ] **Step 5: Commit**

```bash
git add views/alumno.py config/aviso_privacidad.md docs/aviso_privacidad_propuesta.md tests
git commit -m "Pide y confirma el correo en el registro; actualiza el aviso de privacidad"
```

---

### Task 3: Módulo de envío (SMTP y estado del envío)

**Files:**
- Create: `modules/envio.py`
- Modify: `modules/db.py` (métodos de envío; `reiniciar_alumno`), `tests/fakes.py`
- Test: `tests/test_envio.py` (nuevo), `tests/test_db_repo.py`

**Interfaces:**
- Consumes: `Alumno` de la Task 1.
- Produces, en `modules/envio.py`:
  - `@dataclass(frozen=True) class ConfigCorreo: servidor: str; puerto: int; usuario: str; contrasena: str; remitente: str`
  - `config_desde(secreto: Callable[[str, str, object], object]) -> ConfigCorreo | None` — usa `secreto("correo", clave, None)`; `None` si falta `servidor`, `puerto`, `usuario` o `remitente`; `contrasena` ausente = `""`.
  - `class EnvioError(Exception)` con el mensaje fijo en español.
  - `enviar_reporte(destino: str, alumno: Alumno, pdf: bytes, config: ConfigCorreo) -> None` — `EmailMessage` de texto plano; `To`: `destino`; `From`: `config.remitente`; asunto «Tu reporte de evaluación integral»; cuerpo corto con el nombre del alumno, sin resultados, y la línea «Si no esperabas este mensaje, ignóralo.»; adjunto `application/pdf` llamado `resultados_<matricula>.pdf`. Rechaza con `EnvioError` un `destino` con espacios o saltos de línea sin abrir conexión. Cualquier `smtplib.SMTPException`/`OSError` → `EnvioError` con mensaje fijo (autenticación, destinatario rechazado, o «No se pudo conectar con el servidor de correo.»).
  - `class RepositorioEnvio(Protocol)`: `reservar_envio(alumno_id: str, ahora: datetime, vencido_antes: datetime) -> bool`; `marcar_enviado(alumno_id: str, ahora: datetime) -> None`; `marcar_error(alumno_id: str, motivo: str) -> None`.
  - `entregar_reporte(repo: RepositorioEnvio, alumno: Alumno, generar_pdf: Callable[[], bytes], config: ConfigCorreo, ahora: datetime | None = None) -> str` — devuelve `"enviado"`, `"error"`, `"omitido"` (otro proceso tiene la reserva o ya se envió) o `"sin_correo"`. Nunca lanza. Orden: sin correo → `"sin_correo"` sin tocar el estado; `reservar_envio(alumno.id, ahora, ahora - 10 min)` falso → `"omitido"`; luego `generar_pdf()` y `enviar_reporte`; éxito → `marcar_enviado`; cualquier excepción → `marcar_error` con el mensaje de `EnvioError` o, para otra excepción, «No se pudo generar o enviar el reporte.».
  - `pendientes_de_envio(filas: Sequence[FilaAlumno]) -> list[FilaAlumno]` — alumnos con `estado == "terminado"`, `completo`, `correo` y `reporte_estado` en `pendiente`, `error` o `enviando`.
  - `enviar_pendientes(repo, tests, filas, config, fecha, ahora=None) -> tuple[int, int, int]` — (enviados, fallidos, omitidos) llamando a `entregar_reporte` con `pdf_individual(f.alumno, tests, list(f.resultados), fecha)`.
- `FakeRepo` y `SupabaseRepo` implementan `RepositorioEnvio`; `reiniciar_alumno` (sin borrar el registro) devuelve el alumno a `reporte_estado='pendiente'` con `reporte_enviado_en`, `reporte_reservado_en` y `reporte_error` en nulo.

- [ ] **Step 1: Escribir las pruebas que fallan** en `tests/test_envio.py`, con `smtplib.SMTP_SSL`/`SMTP` parcheados por una clase falsa que registra mensajes enviados y puede lanzar `SMTPAuthenticationError` o `OSError`:
  - `test_config_desde_devuelve_none_si_falta_servidor`; `test_config_desde_lee_todos_los_campos`.
  - `test_envio_arma_el_mensaje`: `To`, `From`, asunto, nombre del alumno en el cuerpo, adjunto `resultados_123456.pdf` con los bytes recibidos y cuerpo sin la palabra «Test».
  - `test_puerto_465_usa_ssl_587_usa_starttls_otro_sin_cifrar` y `test_no_hay_login_sin_contrasena`.
  - `test_destino_con_salto_de_linea_no_abre_conexion`.
  - `test_entregar_exitoso_marca_enviado` (estado final `enviado`); `test_entregar_dos_veces_envia_una_sola` (segunda llamada → `"omitido"`, un solo mensaje).
  - `test_fallo_smtp_marca_error_con_mensaje_fijo`: con contraseña `"S3creta!"` y fallo de autenticación, `reporte_error` no contiene `"S3creta!"` ni el texto de la excepción; estado `error`; la función no lanza.
  - `test_error_al_generar_el_pdf_marca_error`.
  - `test_error_se_puede_reintentar`; `test_reserva_vencida_se_puede_tomar` (`enviando` desde hace 11 min → se envía; desde hace 5 min → `"omitido"`).
  - `test_sin_correo_no_toca_el_estado`.
  - `test_reiniciar_devuelve_el_estado_a_pendiente`.
  - `test_pendientes_de_envio_filtra`, `test_enviar_pendientes_cuenta`.
  - En `tests/test_db_repo.py`: `reservar_envio` hace un `update` con el filtro de estado (`pendiente`/`error`, o `enviando` con `reporte_reservado_en` anterior a `vencido_antes`) y devuelve `True` solo si el `update` regresa filas.

- [ ] **Step 2: Ejecutar y comprobar que fallan**

Run: `.venv/bin/python -m pytest tests/test_envio.py tests/test_db_repo.py -q`
Expected: FAIL (`ModuleNotFoundError: modules.envio`).

- [ ] **Step 3: Implementar** `modules/envio.py` como se describe. `SupabaseRepo.reservar_envio`: `update({"reporte_estado": "enviando", "reporte_reservado_en": ahora.isoformat()}).eq("id", alumno_id).or_(...)` con la condición `reporte_estado.in.(pendiente,error)` o `and(reporte_estado.eq.enviando,reporte_reservado_en.lt.<vencido_antes ISO>)`, y `bool(r.data)`. `marcar_enviado`: estado `enviado`, `reporte_enviado_en`, `reporte_error` nulo. `marcar_error`: estado `error`, `reporte_error=motivo`. `FakeRepo` guarda `reporte_estado`, `reporte_error` y un dict de reservas; `reservar_envio` aplica la misma regla con atomicidad trivial. Importar `pdf_individual` de `modules.reports` solo en `enviar_pendientes`.

- [ ] **Step 4: Ejecutar y comprobar que pasan**

Run: `.venv/bin/python -m pytest -q`
Expected: suite en verde.

- [ ] **Step 5: Commit**

```bash
git add modules/envio.py modules/db.py tests
git commit -m "Agrega el envío del reporte por SMTP con control de estado"
```

---

### Task 4: Envío al terminar el último test

**Files:**
- Modify: `views/test.py` (`_fin`, `render`), `views/alumno.py` (`render`), `views/paginas.py` (`pagina_alumno`)
- Test: `tests/test_alumno_view.py`, `tests/test_paginas.py`

**Interfaces:**
- Consumes: `ConfigCorreo`, `config_desde`, `entregar_reporte` (Task 3).
- Produces: `alumno.render(repo, tests, aviso_md, cliente_ip, mostrar_resultados=True, correo: ConfigCorreo | None = None)`; `test.render(repo, alumno, tests, mostrar_resultados=True, correo=None)`; `test._fin(repo, alumno, tests, mostrar, correo)`. `pagina_alumno` calcula `config_desde(secreto)` y lo pasa.

- [ ] **Step 1: Escribir las pruebas que fallan** (el helper de la app de prueba recibe una `ConfigCorreo` y parchea `smtplib`; el alumno termina todos los tests):
  - `test_al_terminar_se_envia_el_reporte_y_se_avisa`: un mensaje enviado a su correo, `estado == enviado`, texto «Te enviamos tu reporte a …» y «spam».
  - `test_rerun_no_envia_dos_veces` (segundo `at.run()` → un solo mensaje).
  - `test_si_el_envio_falla_igual_ve_sus_resultados`: SMTP lanza; aparece el botón «Descargar PDF», el aviso «No pudimos enviarte el correo» y no hay traceback; `reporte_error` guardado.
  - `test_sin_configuracion_de_correo_no_envia_ni_avisa_error` (`correo=None`: estado queda `pendiente`, sin mensaje de error).
  - `test_si_no_se_muestran_resultados_no_se_envia` (`mostrar_resultados=False`).
  - En `tests/test_paginas.py`: `pagina_alumno` pasa la config leída de `secreto("correo", ...)`.

- [ ] **Step 2: Ejecutar y comprobar que fallan**

Run: `.venv/bin/python -m pytest tests/test_alumno_view.py tests/test_paginas.py -q`
Expected: FAIL (parámetro `correo` desconocido).

- [ ] **Step 3: Implementar.** En `_fin`, después de guardar `archivos["pdf"]` y solo si `correo is not None`: `if "envio" not in archivos: archivos["envio"] = entregar_reporte(repo, alumno, lambda: archivos["pdf"], correo)` y, bajo `st.success("¡Terminaste!…")`, mostrar según el valor: `enviado` → `st.info(f"Te enviamos tu reporte a {alumno.correo}. Revisa también la carpeta de spam.")`; `error` → `st.warning("No pudimos enviarte el correo; tu tutor podrá reenviártelo. Puedes descargar tu PDF aquí.")`; los demás valores no muestran nada. No tocar el botón de descarga. Con `mostrar == False` no se envía.

- [ ] **Step 4: Ejecutar y comprobar que pasan**

Run: `.venv/bin/python -m pytest -q`
Expected: suite en verde.

- [ ] **Step 5: Commit**

```bash
git add views tests
git commit -m "Envía el reporte por correo al terminar el último test"
```

---

### Task 5: Estado y botón «Enviar reportes pendientes» en /admin

**Files:**
- Modify: `views/admin.py` (`_pestana_avance`, `render`, nuevo `_bloque_envio`/`_dialogo_envio`), `views/paginas.py` (`pagina_admin`)
- Test: `tests/test_admin_view.py`, `tests/test_paginas.py`

**Interfaces:**
- Consumes: `ConfigCorreo`, `config_desde`, `pendientes_de_envio`, `enviar_pendientes` (Task 3).
- Produces: `admin.render(repo, tests, esperada, cliente_ip, url_publica, correo: ConfigCorreo | None = None)`.

- [ ] **Step 1: Escribir las pruebas que fallan:**
  - `test_la_fila_muestra_el_estado_del_reporte`: textos «Reporte enviado», «Reporte con error: <motivo>», «Sin correo» (terminado sin correo) en la nota de la fila; un alumno en curso no muestra nada de reporte.
  - `test_boton_enviar_pendientes_envia_y_resume`: con 2 pendientes y 1 enviado, confirma el diálogo y aparece «Enviados: 2 · Con error: 0 · Omitidos: 0»; los estados quedan `enviado`; el panel se recarga.
  - `test_boton_desactivado_sin_configuracion`: `correo=None` → botón `disabled` y texto «Falta configurar la sección [correo] en los secretos de la app.».
  - `test_boton_desactivado_si_no_hay_pendientes` (texto «No hay reportes pendientes.»).
  - `test_un_fallo_se_cuenta_y_no_detiene_a_los_demas`.

- [ ] **Step 2: Ejecutar y comprobar que fallan**

Run: `.venv/bin/python -m pytest tests/test_admin_view.py -q`
Expected: FAIL.

- [ ] **Step 3: Implementar.** La `nota` de cada fila (hoy «Fuera de la lista» / «Irregular») se concatena con ` · ` y el estado del envío para alumnos con `estado == "terminado"`: `enviado` → «Reporte enviado»; `error` → «Reporte con error: {reporte_error}»; `enviando` → «Enviando reporte…»; `pendiente` → «Reporte pendiente»; sin correo → «Sin correo». El bloque de envío va al inicio de `_pestana_avance`, tras `frase_avance`: `st.button("Enviar reportes pendientes", icon=":material/mail:")` que abre un `st.dialog` (mismo patrón que `_dialogo_reinicio`) con «Se enviarán N reportes. ¿Continuar?»; al confirmar llama `enviar_pendientes(repo, panel.tests, panel.filas, correo, fecha)`, guarda el resumen en `st.session_state["admin_aviso"]`, hace `st.session_state.pop("panel", None)` y `st.rerun()`. `pagina_admin` pasa `config_desde(secreto)`.

- [ ] **Step 4: Ejecutar y comprobar que pasan**

Run: `.venv/bin/python -m pytest -q`
Expected: suite en verde.

- [ ] **Step 5: Commit**

```bash
git add views tests
git commit -m "Muestra el estado del envío y permite reenviar reportes desde /admin"
```

---

### Task 6: Configuración, documentación y verificación visual

**Files:**
- Modify: `.streamlit/secrets.toml.example`, `README.md`, `PLAN.md`
- Create (fuera del repo, en el scratchpad): demo con `FakeRepo` y un servidor SMTP de depuración local

- [ ] **Step 1: Documentar.** `.streamlit/secrets.toml.example`: sección `[correo]` con `servidor = "smtp.gmail.com"`, `puerto = 465`, `usuario`, `contrasena` (contraseña de aplicación, con comentario de cómo se genera: verificación en dos pasos → «Contraseñas de aplicaciones»), `remitente`; comentario de que sin la sección el envío queda desactivado. `README.md` y `PLAN.md`: reemplazar «No se pide correo» por la descripción nueva (correo para el reporte, estados del envío, botón del panel, migración `06` antes de desplegar).

- [ ] **Step 2: Comprobar la suite completa**

Run: `.venv/bin/python -m pytest -q`
Expected: todo en verde (≥ 566 pruebas más las nuevas).

- [ ] **Step 3: Demo visual local.** En el scratchpad, un script Streamlit que arma `FakeRepo` con un alumno que ya contestó todos los tests, llama a `alumno.render` y `admin.render` con una `ConfigCorreo` que apunta a `localhost:1025`, y un servidor `python -m smtpd -n -c DebuggingServer localhost:1025` (Python 3.11) que imprime el correo. Abrir el registro, la pantalla final y `/admin`, y revisar: campos de correo, aviso de envío, estado en la fila, botón y diálogo; confirmar que el correo impreso trae el PDF adjunto. No usar la base real ni los secretos reales.

- [ ] **Step 4: Commit**

```bash
git add .streamlit/secrets.toml.example README.md PLAN.md
git commit -m "Documenta la configuración del correo y el envío de reportes"
```

---

## Autorrevisión

- **Cobertura del diseño:** datos y migración (T1), registro y aviso (T1-T2), módulo de envío con reserva, vencimiento y reinicio (T3), pantalla final con `MOSTRAR_RESULTADO_AL_ALUMNO` (T4), panel con estado y botón (T5), secretos y documentación (T6). Sin huecos.
- **Consistencia de tipos:** `Alumno.correo/reporte_estado/reporte_error`, `ConfigCorreo`, `entregar_reporte(...) -> str`, `RepositorioEnvio` y la firma `render(..., correo=None)` se usan igual en todas las tareas.
- **Fuera de alcance, a propósito:** borrar los 20 registros piloto y ejecutar la migración `06` en Supabase son pasos manuales de despliegue, anotados en el README.
