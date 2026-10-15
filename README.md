# Evaluación Diagnóstica FCA

Aplicación web para que estudiantes mayores de edad de la Facultad de Contaduría y Administración (UABJO)
contesten, desde su celular, dos tests —**Test 1: The Big Five** y **Test 2: Administration Specialties**— y
reciban una guía de **qué especialidad podría convenirles**. El docente ve el avance de todos, descarga los
reportes y genera el código QR de acceso.

> Los resultados son una **guía de orientación**, no un diagnóstico psicológico ni una decisión obligatoria.
> Si el instrumento es propio, conviene que un orientador o psicólogo lo revise.

Hecha con [Streamlit](https://streamlit.io) y [Supabase](https://supabase.com) (PostgreSQL).

## Qué hace

**Alumno** (en la raíz de la URL, pensado para el celular)

1. Se registra: apellidos, nombre(s), matrícula (6 dígitos), edad (mínimo 18), tutor, y acepta el aviso de privacidad.
2. Contesta los tests **en orden**, en bloques de 10 preguntas, con barra de avance. **Todas las preguntas son
   obligatorias**; cada bloque se guarda al continuar.
3. Si recarga la página, vuelve a escribir su matrícula y nombre y **continúa donde se quedó**.
4. Al terminar ve su 1ª y 2ª opción de cada test, una vista conjunta y puede **descargar su PDF y su Excel**.
   Esa pantalla es la única vez que los ve: al cerrarla, el docente se los entrega desde el panel.

**Docente** (ruta oculta `/admin`, con contraseña)

- **Avance:** registrados, terminados y en curso, con el estado de cada alumno por test.
- **Descargas:** Excel concentrado (con una hoja por test y la hoja «Respuestas» como respaldo de la base de
  datos), ZIP con el PDF de quienes terminaron, y PDF/Excel de un alumno.
- **Código QR:** PNG de alta resolución con la URL pública.
- Acceso: contraseña compartida; 5 intentos fallidos desde un mismo equipo (o 30 en total) bloquean 15 minutos, y la
  sesión caduca tras 60 minutos sin uso.
- Todos los alumnos van juntos: no hay grupos ni códigos de grupo.

## Reglas importantes

- **No hay lista de matrículas autorizadas:** entra cualquier matrícula de 6 dígitos, y quien tenga el QR puede
  registrarse. Si en el piloto aparecen matrículas desconocidas, el siguiente paso es agregar esa lista.
- Una matrícula se registra **una sola vez**. Si sigue «en curso», se reanuda con la misma matrícula y el mismo
  nombre; con otro nombre se rechaza y cuenta como intento fallido (5 por matrícula y 100 por equipo cada 15 min).
- «Sin experiencia» (SE, solo en el Test 2) es un dato faltante: no suma ni cuenta como 0.

## Puesta en marcha en tu computadora

Requisitos: Python 3.11 o superior y un proyecto de [Supabase](https://supabase.com).

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

**1. Base de datos.** En Supabase abre **SQL Editor → New query** y ejecuta, en este orden, el contenido de
[`sql/01_esquema.sql`](sql/01_esquema.sql) y luego el de [`sql/02_rls.sql`](sql/02_rls.sql). El segundo activa la
seguridad por filas sin políticas públicas: nadie puede leer ni escribir con la clave pública; la app usa la
`service_role key` desde el servidor.

**2. Secretos.** Copia la plantilla y llena los valores (el archivo real está en `.gitignore`):

```bash
cp .streamlit/secrets.toml.example .streamlit/secrets.toml
```

| Sección | Clave | Para qué sirve |
|---|---|---|
| `[supabase]` | `url` | Dirección del proyecto, `https://…supabase.co` |
| `[supabase]` | `service_role_key` | Clave de servidor (Settings → API). **Nunca** en el navegador ni en el repositorio |
| `[admin]` | `password` | Contraseña del panel `/admin`: mínimo 12 caracteres, larga y única |
| `[app]` | `public_url` | URL pública de la app (la que lleva el QR) |
| `[app]` | `MOSTRAR_RESULTADO_AL_ALUMNO` | `true` (por defecto): el alumno ve y descarga sus resultados; `false`: solo el docente |

**3. Correr la app y las pruebas.**

```bash
streamlit run app.py        # alumno en http://localhost:8501  ·  docente en http://localhost:8501/admin
python3 -m pytest -q        # unas 500 pruebas; no necesitan Supabase
```

Algunas pruebas usan herramientas opcionales (`pdftotext`, `pdfimages`, `zbarimg`) y se omiten si no están.

## Los tests (archivos Excel)

Cada test es un `.xlsx` en [`config/tests/`](config/tests). El alumno los contesta en el **orden alfabético** del
nombre de archivo, que además es el id del test (minúsculas, números, `_` o `-`, hasta 40 caracteres).

| Hoja | Columnas | |
|---|---|---|
| `especialidades` | `codigo`, `nombre`, `descripcion`, `perfil_profesional` | Obligatoria |
| `preguntas` | `id`, `bloque`, `texto`, `especialidad_codigo`, `invertida` (SI/NO) | Obligatoria |
| `escala` | `valor`, `etiqueta` (valores enteros consecutivos; una fila `SE` opcional = sin experiencia) | Obligatoria |
| `info` | `clave`, `valor` (`titulo`, `instrucciones`) | Opcional |
| `niveles` | `ambito` (`categoria`/`afinidad`), `minimo` (0 a 1), `etiqueta` | Opcional |
| `afinidad` | `codigo`, `nombre`, `componentes` (p. ej. `APERTURA+EXTRAVERSION`), `descripcion` | Opcional |

- Si falta una hoja, hay IDs repetidos o una pregunta apunta a una especialidad inexistente, la app **lo dice con
  todos los errores juntos** (el docente los ve en los registros; el alumno ve un aviso genérico).
- **Cambiar preguntas o escala mientras hay alumnos contestando** los bloquea con un aviso, porque sus respuestas
  ya no corresponden al test. Corregir descripciones, títulos o niveles **no** los afecta. Haz los cambios cuando
  nadie esté contestando.
- Las calculadoras originales están en [`docs/referencia/`](docs/referencia). [`scripts/convertir_tests_reales.py`](scripts/convertir_tests_reales.py)
  las convierte a este formato.

## Cómo se califica

[`modules/scoring.py`](modules/scoring.py) replica las calculadoras de Excel y se verifica contra ellas con 253
casos recalculados en LibreOffice (`scripts/generar_golden_scoring.py`, `tests/golden/`).

- Porcentaje de una especialidad = puntos obtenidos ÷ (respuestas contestadas × valor máximo). Una pregunta
  invertida vale `mínimo + máximo − respuesta`.
- **Ranking:** mayor porcentaje; el empate se rompe por mayor puntaje bruto y luego por el orden del Excel.
  La 1ª y 2ª opción solo existen si al menos 2 especialidades tienen datos.
- **Empate técnico:** las dos primeras difieren 5 puntos porcentuales o menos.
- **Sin experiencia:** no entra al puntaje ni al máximo; con 2 o más en una especialidad se pide explorarla; si
  todas sus respuestas son SE, la especialidad queda «sin datos» y fuera del ranking.
- **Test 1 (Big Five):** se califica por dimensión y se calcula la afinidad con cada especialidad de la carrera
  (p. ej. Mercadotecnia = Apertura + Extraversión).
- La **vista conjunta** compara las especialidades comunes de los tests y promedia los que tienen dato; es una
  lectura orientativa, no un puntaje oficial.

## Publicar en Streamlit Community Cloud

1. Une el PR a `main` en GitHub (o despliega desde la rama que quieras probar).
2. En [share.streamlit.io](https://share.streamlit.io) entra con GitHub → **Create app**. Si el repositorio es
   privado, autoriza el acceso.
3. Repositorio `C02CarlosG/Test_Especialidad_FCA`, rama `main`, archivo principal `app.py`, y una URL corta
   (será la del QR).
4. En **Advanced settings** elige Python 3.12 o 3.13 y pega en **Secrets** el contenido de tu `secrets.toml`.
5. **Deploy.** Revisa que `/` muestre el registro con los logos, que `/admin` pida la contraseña y que un
   registro de prueba aparezca en el panel. Los errores están en **Manage app → Logs**.
6. Pon la URL real en `[app] public_url`, genera el QR en `/admin → Código QR` y **pruébalo con un iPhone y un
   Android** antes de imprimirlo.

## Antes, durante y después de una aplicación

| Cuándo | Qué hacer |
|---|---|
| **Una semana antes** | Entra a Supabase: el plan gratuito **pausa el proyecto tras 7 días sin uso**. Haz una prueba completa con 2 o 3 alumnos de prueba y bórralos después. |
| **10 minutos antes** | Abre la URL: Streamlit duerme la app tras unas 12 horas sin visitas y tarda en despertar. Confirma que el salón tenga Wi‑Fi o datos para 30 a 40 conexiones a la vez. |
| **Durante** | En `/admin → Avance` ves quién va en qué test. «Actualizar datos» recarga la tabla. |
| **Después** | Descarga el **Excel concentrado**: su hoja «Respuestas» respalda toda la base. Entrega a cada alumno su PDF (o el ZIP) y, si quieres, pulsa «Guardar los resultados» para copiarlos a la tabla `resultados`. |

## Privacidad y datos personales

- **Qué se guarda:** apellidos, nombre(s), matrícula, edad, tutor, fecha y hora de aceptación del aviso, y las
  respuestas a los tests. **No se pide correo.** Para limitar intentos fallidos se guarda un *hash* de la IP del
  equipo (no la IP), que es seudonimización, no anonimato.
- **Quién accede:** solo el docente con la contraseña del panel. Las tablas tienen seguridad por filas activa y
  sin políticas públicas; la clave de servidor vive únicamente en los secretos de Streamlit.
- **El aviso de privacidad** está en [`config/aviso_privacidad.md`](config/aviso_privacidad.md). No indica
  responsable, plazo de conservación ni cómo ejercer los derechos de acceso, rectificación, cancelación y
  oposición; la escuela debe valorar si los agrega.
- **Plazo y borrado:** define cuánto tiempo se conservan los datos (por ejemplo, hasta el cierre del ciclo, tras
  descargar el respaldo). Para borrar, en el SQL Editor de Supabase:

```sql
-- un alumno (se borran también sus respuestas, avance y resultados)
delete from public.alumnos where matricula = '123456';

-- todo, al cerrar el ciclo (descarga antes el Excel concentrado)
truncate public.resultados, public.respuestas, public.progreso_tests,
         public.intentos_fallidos, public.alumnos cascade;
```

- **Repositorio:** si es público, las preguntas y las calculadoras de los tests también lo son. Hazlo privado si
  el instrumento no debe difundirse. Los secretos nunca se suben (`.streamlit/secrets.toml` está en `.gitignore`).

## Solución de problemas

| Síntoma | Qué revisar |
|---|---|
| El alumno ve «El test no está disponible» | Faltan o están mal los secretos de Supabase, o hay un error en un Excel de `config/tests`. Mira los registros en Manage app → Logs. |
| `/admin` dice «no está configurado» | Falta `[admin] password` o tiene menos de 12 caracteres. |
| «Demasiados intentos fallidos» | Espera 15 minutos. Si fue por una prueba, borra los intentos: `delete from public.intentos_fallidos;` |
| Un alumno quedó bloqueado por un cambio en el test | El test cambió mientras contestaba (ver «Los tests»). Si es necesario, bórralo con el SQL de arriba para que repita. |
| Un alumno no pudo descargar sus resultados | Descárgalos tú desde `/admin → Descargas → Un alumno`. |
| La app tarda en responder | Probablemente estaba dormida; espera unos segundos y recarga. |
| No cargan los logos | Revisa que `.streamlit/config.toml` tenga `enableStaticServing = true` y que exista la carpeta `static/`. |

## Estructura del proyecto

```
app.py                  entrada: "/" alumno, "/admin" docente (st.navigation oculta)
views/                  pantallas: alumno.py, test.py, admin.py, paginas.py, tema.py y tema.css (diseño)
modules/                lógica: acceso, avance, scoring, panel, reports, reports_admin, admin_auth,
                        security, qr_utils, config_loader, db (única capa que habla con Supabase)
config/                 aviso_privacidad.md y tests/*.xlsx
sql/                    01_esquema.sql y 02_rls.sql
static/                 logos y tipografías, servidos con enableStaticServing
scripts/                conversión de las calculadoras y generación de los casos de verificación
tests/                  pruebas automáticas (golden/ = casos calculados con las hojas de Excel)
docs/referencia/        calculadoras originales
PLAN.md                 plan por fases y decisiones tomadas
```

## Licencias y créditos

Los logos de la FCA y de la UABJO pertenecen a sus instituciones. Las tipografías **Fraunces** y **Plus Jakarta
Sans** van autoalojadas y se distribuyen bajo la [SIL Open Font License 1.1](https://openfontlicense.org).
