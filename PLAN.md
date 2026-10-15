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