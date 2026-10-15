Plan de desarrollo: Test vocacional de especialización
Objetivo
App web (Streamlit + Supabase) para que alumnos mayores de edad contesten, vía QR, un test que mide su afinidad con las especialidades de su carrera, y generar reportes individuales (PDF) y grupales (Excel).
Decisiones pendientes (resolver antes o durante la Fase 1)
Decisión	Opciones	Por defecto
Escala de respuesta	1 a 5 / "me gusta - no me gusta"	1 a 5
Número de especialidades	Por definir	3 (ejemplo)
Resultado visible al alumno	Sí / No	No (solo docente)
Preguntas con puntuación invertida	Sí / No	Soportadas
Texto del aviso de privacidad	Lo proporciona la escuela	Texto base editable
Estructura propuesta
```
test-vocacional/
├── app.py                  # Entrada y ruteo (alumno / admin)
├── modules/
│   ├── config_loader.py    # Lee test.xlsx y valida su formato
│   ├── db.py               # Acceso a Supabase
│   ├── scoring.py          # Calificación (lógica pura)
│   ├── reports.py          # PDF individual, ZIP y Excel
│   ├── qr_utils.py         # Generación del QR
│   └── security.py         # Límite de intentos, validaciones
├── views/
│   ├── alumno.py
│   └── admin.py
├── config/
│   ├── test.xlsx           # Preguntas, especialidades, escala
│   └── aviso_privacidad.md
├── sql/
│   ├── 01_esquema.sql
│   └── 02_rls.sql
├── tests/
│   ├── test_scoring.py
│   └── test_config_loader.py
├── .streamlit/secrets.toml.example
├── requirements.txt
└── README.md
```
Estructura de test.xlsx
Hoja `especialidades`: codigo, nombre, descripcion, perfil_profesional.
Hoja `preguntas`: id, bloque, texto, especialidad_codigo, invertida (SI/NO).
Hoja `escala`: valor, etiqueta (por ejemplo 1 = "Nada de acuerdo", 5 = "Totalmente de acuerdo").
El cargador debe fallar con un mensaje claro si falta una hoja, hay IDs repetidos, o una pregunta apunta a una especialidad que no existe.
Modelo de datos (Supabase / PostgreSQL)
`grupos` (id, codigo_acceso UNIQUE, nombre, activo, expira_en, creado_en)
`alumnos` (id, nombre, matricula UNIQUE, correo, grupo_id → grupos, acepto_privacidad, acepto_en, estado [en_curso | terminado], creado_en)
`respuestas` (alumno_id → alumnos, pregunta_id, valor, UNIQUE(alumno_id, pregunta_id))
`resultados` (alumno_id UNIQUE → alumnos, puntajes JSONB, afinidad JSONB, especialidad_principal, especialidad_secundaria, calculado_en)
RLS activo en todas las tablas, sin políticas públicas; acceso solo con service role desde el servidor.
Fases
Fase 1: Base del proyecto
Estructura de carpetas, entorno virtual, requirements.txt, secrets de ejemplo.
Esquema SQL y RLS en /sql; conexión a Supabase.
`config_loader` con test.xlsx de ejemplo (3 especialidades, 12 preguntas ficticias).
Aceptación: `pytest` pasa; la app abre en local; el cargador valida y rechaza archivos mal formados.
Fase 2: Flujo de acceso y captura
Bienvenida, aviso de privacidad y casilla de aceptación.
Formulario de datos y validación de código de grupo.
Bloqueo de una respuesta por matrícula; límite de intentos.
Aceptación: un alumno nuevo entra, queda registrado y no puede repetir; un código inválido o expirado se rechaza.
Fase 3: Test
Preguntas por bloques de 10, barra de avance, guardado por bloque y reanudación.
Pantalla final de confirmación.
Diseño pensado para celular (botones grandes, una columna).
Aceptación: probar en un celular real; recargar la página a mitad del test conserva el avance.
Fase 4: Calificación y reportes
`scoring.py` con puntajes, afinidad %, ranking, empates y preguntas invertidas.
PDF individual con radar y descripciones; Excel concentrado; ZIP por grupo.
Aceptación: pruebas unitarias con casos conocidos (incluye empate e invertidas); los archivos abren correctamente en Word/Excel/lector PDF.
Fase 5: Panel de administración
Login con contraseña y límite de intentos.
Avance por grupo, descargas, gestión de códigos de grupo.
Generador de QR (PNG de alta resolución).
Aceptación: un docente puede, sin tocar código, crear un grupo, descargar el QR y obtener los reportes.
Fase 6: Despliegue y cierre
Publicar en Streamlit Community Cloud con secrets configurados.
README completo y checklist de privacidad.
Prueba piloto con 3 a 5 personas y ajuste de textos.
Cargar el test.xlsx real con las preguntas definitivas.
Aceptación: URL pública funcionando, QR probado en varios celulares (iPhone y Android).
Riesgos y cuidados
Señal en el salón: confirmar Wi-Fi o datos suficientes; considerar que 30 a 40 alumnos se conectan a la vez.
Límites del plan gratuito de Streamlit y Supabase: hacer una prueba de carga antes de la aplicación real.
Privacidad: aviso de privacidad visible, datos mínimos, acceso solo del docente, política de conservación y borrado.
Calidad del test: si es un instrumento propio, conviene que un orientador o psicólogo lo revise; los resultados son una guía, no un diagnóstico.
Copias de seguridad: exportar la base de datos a Excel al cerrar cada aplicación.
Cuando lleguen las preguntas
Llenar las tres hojas de `config/test.xlsx`.
Correr `pytest` y la validación del cargador.
Hacer una prueba completa con 2 o 3 alumnos de prueba.
Revisar el PDF resultante y ajustar las descripciones de cada especialidad.
## Actualización: 3 tests por alumno
- Hay 3 tests, uno por archivo en `config/tests/` (`test_1_*.xlsx`, `test_2_*.xlsx`, `test_3_*.xlsx`); el orden alfabético es el orden en que el alumno los contesta. Cada archivo conserva las hojas `especialidades`, `preguntas`, `escala` y admite una hoja opcional `info` (`titulo`).
- Un solo QR y una sola URL; el código de grupo solo autoriza la entrada (`grupos.tests_habilitados` permite limitar qué tests hace un grupo).
- Cada test se califica por separado (ranking, principal y secundaria). El PDF individual trae una sección por test y una gráfica final que relaciona los resultados de los tests (diseño a definir en la Fase 4). En el Excel de grupo, una hoja de resultados por test.
- BD: `progreso_tests` (avance y versión por test), y `respuestas`/`resultados` llevan `test_id`.

## Actualización: registro sin código de grupo
- El registro pide apellido paterno, apellido materno, nombre(s), matrícula, edad (>= 18), nombre del tutor/orientador y la aceptación del aviso de privacidad; la fecha de aplicación se llena sola. Ya no se pide correo.
- **No hay código de grupo ni lista de matrículas autorizadas:** entra cualquier matrícula con formato válido. Se quitan la tabla `grupos`, `tests_habilitados` y la expiración; todos los alumnos contestan todos los tests. Riesgo aceptado: quien tenga el QR puede registrarse con datos inventados.
- Una matrícula se registra una sola vez. Si sigue "en_curso", se reanuda con la misma matrícula y el mismo nombre; entrar con una matrícula ajena cuenta como intento fallido (5 por matrícula y 100 por IP, cada 15 min).
- Los reportes "por grupo" de las Fases 4 y 5 quedan por definir (por ejemplo, por tutor o por fecha de aplicación).

## Actualización: Fase 3 (test)
- Preguntas en el orden original del Excel, en bloques de 10, con barra de avance; una columna y opciones de 44 px para el celular.
- **Todas las preguntas son obligatorias:** un bloque se guarda completo o no se guarda. Un test termina cuando todas sus preguntas tienen respuesta; el alumno termina al acabar todos los tests.
- Opción "SE" (sin experiencia) del test 2: cuenta como respuesta y se guarda como `valor` NULL (0 y NULL son distintos). Su tratamiento en el puntaje es de la Fase 4.
- El avance vive en la BD. Si recarga la página, vuelve a entrar con matrícula y nombre y continúa en el primer bloque sin contestar. Si el .xlsx de un test cambia a mitad de la aplicación, el alumno en curso ve un aviso (se compara el hash `version_test`).
- Al terminar, el alumno no ve su resultado (solo el docente).

## Actualización: Fase 4 (calificación y reportes del alumno)
- **El alumno ve y exporta sus resultados al terminar** (PDF y Excel), para decidir qué especialidad le conviene. Sustituye la decisión anterior "resultado visible al alumno: No". Se puede apagar con `[app] MOSTRAR_RESULTADO_AL_ALUMNO = false` en los secrets. Los archivos se generan en memoria y no se guardan; al cerrar la página el alumno ya no puede volver a consultarlos (su matrícula queda "terminada").
- `modules/scoring.py` replica las calculadoras de Excel (docs/referencia) y se verifica contra ellas con 253 casos recalculados en LibreOffice (`scripts/generar_golden_scoring.py` → `tests/golden/`). Reglas:
  - Porcentaje = obtenido / (respuestas contestadas x valor máximo de la escala). Preguntas invertidas: `min + max - respuesta`.
  - "SE": no suma al puntaje ni al máximo; 2 o más "SE" en una especialidad = "requiere explorar"; si todas son "SE" no hay dato y queda fuera del ranking (la calculadora la mostraba como 0 %).
  - Ranking: mayor porcentaje, luego mayor puntaje bruto, luego orden del Excel. Principal y secundaria solo si hay al menos 2 con dato. Empate técnico: 5 puntos porcentuales o menos entre las dos primeras.
  - Test 1 (Big Five): se califica por dimensión y se calcula la afinidad con cada especialidad (p. ej. Mercadotecnia = Apertura + Extraversión) con las mismas fórmulas; la 1ª y 2ª opción salen de esa afinidad.
- Los niveles (Alto/Medio/...) y las afinidades derivadas viven en el Excel de cada test (hojas opcionales `niveles` y `afinidad`). La versión del test (`version_test`) ahora solo depende de preguntas y escala: corregir descripciones o umbrales no invalida avances en curso.
- **Vista conjunta (provisional):** las especialidades de la carrera comparten código entre tests (MKT, CH, AF, NI, EMP). El reporte las compara lado a lado, promedia los tests con dato y dibuja un radar con un color por test. El diseño definitivo de la gráfica sigue pendiente.
- Pendiente de la Fase 4: Excel concentrado y ZIP para el docente (dependen de cómo se agrupen los reportes sin grupos) y guardar resultados en la tabla `resultados`.
- Revisión independiente de la Fase 4 (18 agentes; 11 hallazgos confirmados, 4 refutados): porcentajes redondeados igual en pantalla, PDF y Excel (.05 hacia arriba); caracteres de control eliminados de nombres; la pantalla final no deja caché a medias, ofrece "Reintentar" y no consulta la BD en cada rerun; el radar omite "sin datos" y conserva su proporción; el PDF usa una fuente Unicode (DejaVu Sans). Si algo falla al generar los resultados y el alumno no los recupera, el docente los entrega desde el panel (Fase 5).

## Actualización: Fase 5 (panel del docente)
- Ruta oculta `/admin` de la misma URL (no hay enlace desde la vista del alumno). Login con una contraseña compartida (`[admin] password`, mínimo 12 caracteres); 5 intentos fallidos por equipo y 30 en total bloquean 15 minutos; la sesión caduca a los 60 minutos sin uso. Sin contraseña configurada el panel queda deshabilitado.
- **Todos los alumnos juntos** (decisión del usuario): pestaña *Avance* (registrados, terminados, en curso, tabla con estado por test y 1ª opción), pestaña *Descargas* (Excel concentrado con una hoja por test y hoja «Respuestas» de respaldo, ZIP con el PDF de quienes terminaron, PDF y Excel de un alumno, y botón para guardar los resultados en la tabla `resultados`) y pestaña *Código QR* (PNG de alta resolución, solo https).
- Los reportes del docente se calculan siempre desde las respuestas guardadas; la tabla `resultados` es una copia que se refresca desde el panel. Un alumno que contestó con una versión anterior del test aparece en los avisos y no se califica con la actual.
- Verificado contra Supabase real con 41 alumnos temporales (2050 respuestas, más que el tope de 1000 filas por consulta): paginación correcta, resultados iguales al cálculo local y limpieza completa.
- Pendiente (Fase 6): despliegue, README, lista de privacidad (plazo de conservación y borrado de datos), piloto con 3 a 5 personas y prueba de carga.
- Revisión independiente de la Fase 5 (15 agentes; 9 hallazgos confirmados, 3 refutados), corregida: la caducidad de la sesión del docente también cubre las descargas de una pestaña que quedó abierta (reloj compartido y vigilante cada minuto); `/admin` no muestra detalles de configuración antes del login; el intento de acceso se reserva antes de comparar la contraseña (sin carreras) y los intentos bloqueados no alargan el bloqueo; la hoja «Respuestas» respalda TODO lo guardado, incluso tests y preguntas que ya no están en la configuración; los textos del alumno se limpian de caracteres sin asignar o no-caracteres (U+FFFE/U+FFFF); el panel indica desde cuándo son sus datos y los archivos llevan esa hora; el QR rechaza hosts, puertos y la dirección `/admin` mal formados.
