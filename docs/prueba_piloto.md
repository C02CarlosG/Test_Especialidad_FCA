# Prueba piloto: lista de verificación

Objetivo: comprobar con **3 a 5 personas en celulares reales** que el flujo completo funciona antes de aplicarlo a un grupo.
Dura unos 30 minutos más lo que tarde cada persona en contestar (cada test tiene 25 preguntas en 3 bloques: 10, 10 y 5).

Imprime esta hoja o ábrela en una pantalla aparte. Marca cada casilla al terminar y anota en la tabla final lo que falle.

## 1. Antes de empezar (docente)

- [ ] La app abre en la dirección pública (`https://testespecialidadfca.streamlit.app`). Si estaba dormida, espera a que despierte.
- [ ] El proyecto de Supabase **no** está pausado (en su panel no dice *Paused*).
- [ ] En *Settings → Secrets* de Streamlit Cloud están `[supabase]`, `[admin]` y `[app] public_url` con la dirección real, sin `/admin` al final.
- [ ] En `/admin` entra la contraseña del docente (**un solo intento**; 5 fallidos bloquean 15 minutos).
- [ ] Pestaña **Código QR**: se genera el QR con la dirección pública y se imprime o se muestra en pantalla.
- [ ] Cada participante tiene su propio celular y se anotó modelo, navegador y tipo de red (Wi-Fi o datos).
- [ ] Hay al menos **un iPhone con Safari** y **un Android con Chrome**.

Datos de prueba que usarán los participantes (no usar matrículas reales):

| Participante | Matrícula | Nombre | Edad |
|---|---|---|---|
| 1 | 900001 | Prueba Uno | 20 |
| 2 | 900002 | Prueba Dos | 22 |
| 3 | 900003 | Prueba Tres | 19 |
| 4 | 900004 | Prueba Cuatro | 25 |
| 5 | 900005 | Prueba Cinco | 30 |

## 2. Entrada y registro (cada participante)

- [ ] Al escanear el QR se abre la pantalla de registro sin pedir instalar nada ni iniciar sesión.
- [ ] Se ven **los dos logos** (FCA a la izquierda, UABJO a la derecha), completos y sin que el botón «Fork» de la plataforma se encime.
- [ ] El título y los encabezados se ven en la tipografía con remates (serif); el texto de los formularios, en la sans.
- [ ] Todo el formulario se lee sin hacer zoom ni desplazar la pantalla hacia los lados.
- [ ] El teclado de **Matrícula** y **Edad** es numérico o permite escribir números sin problema.
- [ ] El aviso de privacidad se lee completo y se entiende.

Validaciones (probar una por una antes del registro bueno; cada una debe mostrar un mensaje claro y **no** avanzar):

- [ ] Matrícula con 5 dígitos.
- [ ] Matrícula con letras (por ejemplo `12A456`).
- [ ] Edad 17.
- [ ] Un campo obligatorio vacío.
- [ ] Sin marcar la casilla del aviso de privacidad.

Registro correcto:

- [ ] Con los datos de la tabla y la casilla marcada, **Iniciar evaluación** abre el Test 1.
- [ ] El camino de pasos de arriba muestra *Registro* como hecho y *Test 1* como actual.

## 3. Contestar los tests

- [ ] Cada pregunta se ve con su número y las opciones caben en pantalla; tocar una opción la marca a la primera.
- [ ] La barra de avance y el texto «Bloque 1 de 3 · 0 de 25 preguntas contestadas» son correctos.
- [ ] Dejar **una pregunta sin contestar** y pulsar *Guardar y continuar*: avisa cuántas preguntas faltan en el bloque y no avanza.
- [ ] Al guardar un bloque, la página **sube al inicio** y el avance sube (10 de 25, 20 de 25).
- [ ] En el último bloque el botón dice *Terminar este test*.
- [ ] Al pasar al **Test 2**, el camino de pasos lo marca como actual.
- [ ] En el Test 2 existe la opción de «sin experiencia» (SE) al final de cada pregunta y se puede elegir.
- [ ] Tiempo de espera al guardar un bloque: menos de 3 segundos (anotar el máximo observado).

## 4. Reanudar

- [ ] Participante 1: a la mitad del Test 1, **cerrar la pestaña del navegador** y volver a abrir el QR.
- [ ] Registrarse con la **misma matrícula y el mismo nombre**: muestra «Te damos la bienvenida de nuevo» y continúa en el bloque donde se quedó, con las respuestas anteriores guardadas.
- [ ] Participante 2: intentar entrar con la matrícula del participante 1 pero **otro nombre**: lo rechaza con el mensaje «Esta matrícula ya está registrada…» y no deja ver nada del otro.

## 5. Resultados

- [ ] Al terminar el Test 2 aparece «¡Terminaste!» y las tarjetas con **Tu mejor opción** y la 1ª y 2ª opción de cada test.
- [ ] La tabla «Los tests, juntos» y la gráfica de radar se ven completas en el celular.
- [ ] Los porcentajes y los niveles (alto, medio, bajo) tienen sentido con lo que la persona contestó.
- [ ] **Descargar PDF**: se descarga y abre en el celular; se ven los logos, las tablas y la gráfica sin texto cortado.
- [ ] **Descargar Excel**: se descarga y abre en el celular o en una computadora; se ven los logos y las hojas de cada test.
- [ ] Volver a registrar una matrícula que ya terminó: la rechaza.

## 6. Panel del docente (en `/admin`)

- [ ] En **Avance** aparecen los participantes con el estado correcto (en curso o terminado) y el resumen de arriba suma bien.
- [ ] En **Descargas** el Excel concentrado abre y trae a cada alumno con sus resultados y el respaldo de sus respuestas.
- [ ] En **Descargas** el ZIP de PDFs trae un PDF por cada alumno que terminó los dos tests, un LEEME con quienes aún no terminaron, y los nombres de archivo son legibles.
- [ ] El botón para descargar el QR entrega un PNG que se escanea bien impreso o desde otra pantalla.
- [ ] Los datos de los alumnos (nombre, matrícula, tutor) aparecen completos y sin caracteres raros.
- [ ] Pasados 60 minutos sin actividad, el panel pide la contraseña de nuevo.

## 7. Todos al mismo tiempo

- [ ] Con los 3 a 5 participantes contestando **a la vez**, nadie ve errores ni pantallas lentas.
- [ ] Probar con **datos móviles** en al menos un celular, no solo con Wi-Fi.
- [ ] Anotar si algún celular perdió la conexión y si al volver la persona pudo continuar.

## 8. Textos y mejoras

- [ ] Hay erratas o frases confusas en las instrucciones, preguntas, avisos o mensajes de error (anotar cuáles y dónde).
- [ ] El aviso de privacidad está completo: responsable, plazo de conservación y cómo ejercer los derechos.
- [ ] Alguna persona dudó en qué botón tocar o cómo seguir (anotar en qué pantalla).

## 9. Al terminar: borrar los datos de prueba

Los participantes dejaron registros reales en la base de datos. Bórralos para que no se mezclen con los alumnos.
En Supabase, *SQL Editor*, ejecuta (la matrícula es texto numérico; ajusta el rango si usaste otras):

```sql
delete from public.alumnos where matricula between '900001' and '900005';
```

Las respuestas, el avance y los resultados de esos alumnos se borran solos (borrado en cascada).
Comprueba en `/admin → Avance` que ya no aparecen.

## Registro de problemas

| # | Participante | Celular y navegador | Pantalla | Qué pasó | ¿Grave? |
|---|---|---|---|---|---|
| 1 | | | | | |
| 2 | | | | | |
| 3 | | | | | |
| 4 | | | | | |
| 5 | | | | | |

**Criterio para dar el visto bueno:** todas las casillas de las secciones 2 a 6 marcadas, ningún problema grave abierto y los
tiempos de guardado por debajo de 3 segundos con todos conectados a la vez.
