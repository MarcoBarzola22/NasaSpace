# Especificación 001 — Backend MVP de AgroDSS: comparación de rotaciones de secano

| Campo | Valor |
|---|---|
| Identificador | 001-agrodss-backend |
| Estado | Revisión 2: lista para planificación (ver §9 para las dudas que quedan abiertas) |
| Fecha | 2026-11-15 |
| Base | Constitución del proyecto; reglas de AGENTS; documento de investigación (leído por orden humana explícita para la revisión 1); documento de producto «Agro DSS — Sistema de apoyo para comparar rotaciones agrícolas» («Nasa agronomia»), según los puntos que indicó el equipo en la revisión 2; decisiones de clarificación y de revisión (§1.3) |
| Alcance | Qué debe hacer el backend y por qué. La arquitectura, los módulos y los nombres de archivos se definen en el plan. |
| Historial | **Rev. 1:** versión inicial con seis decisiones de clarificación. **Rev. 2:** consulta en vivo a NASA POWER sin almacenamiento local; perfil de profundidad fija con raíces que crecen dentro de él; barbecho con Kc base y reducción por rastrojo; excedente de lluvia perdido; viento fuerte con WS2M > 8 m/s; alineación con el documento de producto. **Rev. 3:** viento fuerte con el máximo diario WS2M_MAX > 8 m/s; principio 5 de la constitución enmendado (consulta en vivo, sin base de datos ni caché); CA-6.10 (Tmáx < Tmín bloquea el escenario); CA-1.12 (latitud entre −60° y 60°). |

---

## 1. Contexto y objetivo

### 1.1 Contexto

Los ingenieros agrónomos de San Luis (Argentina) deben elegir entre rotaciones de cultivos de secano en un ambiente semiárido, donde el agua del suelo y la secuencia de lluvias deciden el resultado. Por ejemplo, el informe técnico de INTA San Luis 2024–2025 advierte que la soja de segunda después de trigo puede ser de alto riesgo cuando queda poca humedad tras la cosecha. Además, el centeno de cobertura consume agua y genera costos sin producir grano.

Hoy no disponen de una herramienta trazable que muestre cómo se habrían comportado distintas rotaciones con el clima real de años pasados en su lote, con los datos, parámetros y supuestos a la vista.

AgroDSS es una **herramienta de apoyo a la decisión para agrónomos, no un recomendador automático** (documento de producto). El sistema muestra comparaciones y el agrónomo decide.

### 1.2 Objetivo

Construir la primera funcionalidad del backend de AgroDSS. A partir de los datos de una parcela, de hasta tres rotaciones de dos años armadas por el usuario (A, B y C) y de un conjunto de años históricos, el backend debe:

1. **consultar en vivo la API diaria de NASA POWER en cada solicitud** y procesar la serie al vuelo, sin guardarla;
2. calcular la ET₀ diaria con **FAO-56 Penman–Monteith**;
3. ejecutar un **balance hídrico diario continuo** (FAO-56) sobre un perfil de suelo de profundidad fija durante cada ventana de dos años, con raíces que crecen dentro del perfil, transferencia del agua entre cultivos y barbechos, y evaporación de barbecho reducible por rastrojo;
4. estimar el **rendimiento bajo déficit** de cada cultivo de grano con **FAO-33**;
5. calcular el **ingreso** y el **margen bruto** con los precios y costos que ingresa el usuario;
6. contar los **días sin cultivo vivo con viento fuerte** (proxy de exposición del suelo);
7. resumir **rangos descriptivos** entre los años elegidos;
8. devolver todo con su **procedencia** y la **lista de supuestos**, listo para que el frontend lo muestre sin calcular nada.

**Por qué:** el agrónomo necesita comparar rotaciones con evidencia reproducible y honesta. Los resultados son **escenarios históricos descriptivos**: no son pronósticos, no son probabilidades y no parten de parámetros calibrados.

### 1.3 Decisiones tomadas

| # | Tema | Decisión | Origen |
|---|---|---|---|
| 1 | Significado de A, B y C | Son **tres rotaciones libres**: el usuario arma cada una eligiendo cultivos de un catálogo y su orden. | Clarificación |
| 2 | Obtención de NASA POWER | **Consulta en vivo en cada solicitud.** La serie se procesa al vuelo y solo se devuelven los resultados. No se guardan archivos locales, copias de respaldo ni caché de las series climáticas. Reemplaza el modo híbrido de la revisión 1. | Revisión 2 |
| 3 | Datos faltantes | **Procedimientos FAO-56 para datos faltantes como supuesto visible** cuando faltan radiación, humedad o viento. Si faltan lluvia o temperatura, el escenario se bloquea. | Clarificación |
| 4 | Escenarios históricos | **Años de inicio elegidos por el usuario** (de 1 a 10). Cada rotación se calcula sobre la ventana de dos años de cada año. | Clarificación |
| 5 | Parámetros | El usuario carga siempre **suelo, fechas e Ym**. Kc, Ky, duración de etapas, profundidad radicular y fracción p se **sugieren desde FAO-56/FAO-33**; si no se modifican, se marcan como supuesto visible («valor tabulado FAO, no calibrado»). | Clarificación |
| 6 | Contenido de la respuesta | Resumen por rotación × escenario × cultivo, procedencia y supuestos, **más** ingreso y margen bruto, proxy de exposición del suelo y rangos entre escenarios. **Sin serie diaria** en este MVP. | Clarificación |
| 7 | Perfil y raíces (ex D-2) | **Perfil de suelo de profundidad fija**, igual a la **profundidad efectiva** que carga el usuario. Las raíces de cada cultivo crecen dentro de ese perfil. El agua que queda en el perfil al terminar un cultivo es el estado inicial del cultivo o barbecho siguiente. | Revisión 2 |
| 8 | Evaporación en barbecho (ex D-3) | El barbecho **no tiene consumo cero**. Se usa un **Kc base de suelo desnudo de 0,20** por defecto (rango indicado por el equipo: 0,15–0,20), editable por el usuario. Se reduce si el usuario declara rastrojo, según la regla de FAO-56 para acolchados orgánicos: alrededor de un 5 % menos de evaporación por cada 10 % de superficie cubierta. | Revisión 2 |
| 9 | Excesos de lluvia (ex D-4) | Todo milímetro de lluvia que supere la capacidad disponible del perfil (capacidad de campo menos almacenamiento actual) se considera **excedente perdido** (escorrentía o percolación profunda, sin distinguirlas) y no se acumula. | Revisión 2 |
| 10 | Viento fuerte (ex D-5) | Variable **WS2M_MAX** de NASA POWER (velocidad máxima diaria del viento a 2 m). **Día de viento fuerte: WS2M_MAX > 8 m/s** (unos 29 km/h). Se cuenta **solo en los días sin cultivo vivo**. WS2M (media diaria) se sigue usando para la ET₀. | Revisiones 2 y 3 |
| 11 | Fuentes y alcance (ex D-17) | **Prevalece AGENTS.** NASA POWER diario es la fuente climática principal. GPM, MODIS, Landsat y SMAP no son integraciones obligatorias del MVP inicial y su uso requiere aprobación explícita. Toda la especificación se alinea con el documento de producto: herramienta de apoyo a decisiones, no recomendador automático. | Revisión 2 |

### 1.4 Principios que condicionan toda la especificación

- **Secano:** el riego es cero todos los días. No se simula un lote regado.
- **Nada de relleno:** no se interpola ni se inventa ningún valor. Toda sustitución es un procedimiento FAO-56 declarado y visible, o el resultado se bloquea.
- **Sin calibración asumida:** Kc, Ky, Ym y los parámetros de suelo son entradas o supuestos declarados. No se muestran precisión, porcentajes de acierto ni probabilidades.
- **Procedencia:** un dato de NASA POWER es modelo o reanálisis a escala de celda, no una medición del lote.
- **Lógica fuera de la interfaz:** todo cálculo agronómico o económico ocurre en el backend.
- **Solo modelos aprobados:** FAO-56, FAO-33 y la economía de margen bruto.
- **Apoyo, no recomendación:** el sistema compara y explica; no elige ni recomienda rotaciones.
- **Persistencia mínima (constitución, principio 5, enmendado):** consulta en vivo a NASA POWER, sin base de datos ni caché; la demo requiere conexión a internet.

### 1.5 Glosario

| Término | Significado |
|---|---|
| ET₀ | Evapotranspiración de referencia diaria (mm/día), FAO-56 Penman–Monteith. |
| Kc | Coeficiente de cultivo (single Kc de FAO-56), variable por etapa. |
| ETc | Demanda del cultivo sin limitación hídrica: `Kc × ET₀` (mm/día). |
| Ks | Coeficiente de estrés hídrico de FAO-56 (0 a 1). |
| ETa | Evapotranspiración real del cultivo, limitada por el agua disponible: `Ks × Kc × ET₀` (mm/día). |
| ETm | Evapotranspiración máxima del ciclo para FAO-33; aquí se toma como la suma de ETc entre la siembra y el fin del ciclo. |
| Ky | Factor de respuesta del rendimiento al déficit hídrico (FAO-33), para el ciclo completo. |
| Ym | Rendimiento de referencia sin limitación hídrica (t/ha), ingresado por el usuario. |
| Ya | Rendimiento estimado bajo déficit (t/ha). |
| θCC, θPMP | Contenido volumétrico de agua a capacidad de campo y a punto de marchitez permanente (m³/m³). |
| Profundidad efectiva | Profundidad fija del perfil de suelo simulado (m), ingresada por el usuario. |
| Capacidad del perfil | Agua útil máxima del perfil: `(θCC − θPMP) × profundidad efectiva`, en mm. |
| Zr | Profundidad radicular del cultivo en un día dado (m). Crece desde Zr inicial hasta Zr máxima y nunca supera la profundidad efectiva. |
| ADT | Agua disponible total en la zona explorada por las raíces: `(θCC − θPMP) × Zr`, en mm (TAW en FAO-56). |
| AFA | Agua fácilmente aprovechable: `p × ADT` (mm) (RAW en FAO-56). |
| p | Fracción de agotamiento sin estrés (FAO-56). |
| Kc base de barbecho | Coeficiente de evaporación de suelo desnudo durante el barbecho (0,20 por defecto). |
| Cobertura de rastrojo | Porcentaje de la superficie cubierta por residuos durante un barbecho (0–100 %). |
| Excedente perdido | Lluvia que supera la capacidad disponible del perfil y sale del sistema (escorrentía o percolación profunda, sin distinguirlas). |
| Ventana | Período continuo de dos años (730 o 731 días) sobre el que se simula cada rotación. |
| Escenario | Una ventana concreta definida por un año de inicio histórico. |
| Barbecho | Todo día de la ventana sin cultivo activo en la rotación. |
| Celda | Unidad espacial de NASA POWER que representa el punto consultado; no es el lote. |

---

## 2. Usuarios

| Usuario | Rol frente al backend | Necesidad principal |
|---|---|---|
| **Ingeniero agrónomo asesor de San Luis** (usuario primario) | Carga los datos a través del frontend, lee los resultados y toma la decisión. | Comparar rotaciones con datos trazables y supuestos explícitos que pueda defender ante el productor. |
| **Frontend de AgroDSS** (consumidor técnico) | Envía las solicitudes y muestra las respuestas. | Un contrato estable con todos los valores ya calculados y con sus unidades, para no replicar fórmulas. |
| **Equipo AgroDSS y jurado de NASA Space Apps** | Ejecutan la demostración y auditan los cálculos. | Ver la integración real con NASA POWER y poder verificar los controles científicos (masa, límites y unidades). |
| **Productor agropecuario** (indirecto) | Recibe las conclusiones a través del agrónomo. | Entender diferencias de agua, rendimiento y margen sin promesas de pronóstico. |

---

## 3. Historias de usuario

- **HU-1.** Como agrónomo, quiero cargar los datos de mi lote y hasta tres rotaciones armadas por mí, para comparar cómo se habrían comportado con el clima real de años pasados.
- **HU-2.** Como agrónomo, quiero partir de valores de referencia FAO con su cita, para no cargar todo desde cero, sabiendo que no están calibrados para mi lote.
- **HU-3.** Como agrónomo, quiero elegir los años históricos (por ejemplo, un año seco y uno húmedo que recuerdo), para contrastar las rotaciones en situaciones que conozco.
- **HU-4.** Como agrónomo, quiero ver la demanda y el consumo real de agua, los días con estrés y el rendimiento estimado de cada cultivo, para entender en qué tramo de la rotación falta agua.
- **HU-5.** Como agrónomo, quiero que el agua que deja un cultivo o un barbecho pase al siguiente, para ver el efecto real de la secuencia (por ejemplo, cuánta agua consume el centeno antes de la soja).
- **HU-6.** Como agrónomo, quiero indicar cuánto rastrojo queda en cada barbecho, para que la evaporación refleje mi manejo.
- **HU-7.** Como agrónomo, quiero ver el ingreso y el margen bruto con mis precios y costos, para comparar el resultado económico y no solo las toneladas.
- **HU-8.** Como agrónomo, quiero saber cuántos días de viento fuerte cayeron con el lote sin cultivo vivo, para considerar la protección del suelo sin cifras de erosión inventadas.
- **HU-9.** Como agrónomo, quiero ver de dónde salió cada dato y qué supuestos se aplicaron, para explicar y defender mi decisión.
- **HU-10.** Como agrónomo, quiero saber por qué un escenario no se calculó o por qué falló la consulta a NASA, para elegir otro año, corregir mis datos o reintentar.
- **HU-11.** Como equipo de la demo, queremos que cada cálculo consulte NASA POWER en el momento, para mostrar la integración real con datos NASA.
- **HU-12.** Como desarrollador del frontend, quiero una respuesta con todos los resultados ya calculados y con unidades explícitas, para mostrarlos sin realizar cálculos.

---

## 4. Requisitos funcionales

Los criterios de aceptación (CA) usan la notación **EARS** en español:

| Patrón | Plantilla |
|---|---|
| Ubicuo | «El sistema deberá …» |
| Por evento | «Cuando ‹disparador›, el sistema deberá …» |
| Por estado | «Mientras ‹estado›, el sistema deberá …» |
| No deseado | «Si ‹condición no deseada›, entonces el sistema deberá …» |
| Opcional | «Donde ‹característica presente›, el sistema deberá …» |

Las referencias **[NECESITA ACLARACIÓN: D-x]** remiten a las dudas abiertas de la §9.

### RF-1 — Datos de la parcela

**Por qué:** el balance hídrico necesita la capacidad de almacenamiento del perfil y su estado inicial. Son datos del lote que solo conoce el agrónomo y no se obtienen de NASA.

**Entradas:** latitud y longitud (grados decimales); θCC y θPMP (m³/m³) [NECESITA ACLARACIÓN: D-16]; profundidad efectiva del perfil (m); humedad inicial como porcentaje del agua útil del perfil (0–100 %), válida en la fecha de inicio de la ventana; Kc base de barbecho (opcional; 0,20 por defecto).

- **CA-1.1** Cuando se reciba una solicitud de cálculo, el sistema deberá exigir latitud, longitud, θCC, θPMP, profundidad efectiva y humedad inicial.
- **CA-1.2** Si la latitud está fuera de [−90, 90] o la longitud fuera de [−180, 180], entonces el sistema deberá rechazar la solicitud indicando el campo inválido.
- **CA-1.3** Si no se cumple `0 ≤ θPMP < θCC ≤ 1`, entonces el sistema deberá rechazar la solicitud indicando la incoherencia.
- **CA-1.4** Si la profundidad efectiva es menor o igual a 0 o supera el máximo plausible que fije el plan, entonces el sistema deberá rechazar la solicitud.
- **CA-1.5** Si la humedad inicial está fuera de [0, 100] %, entonces el sistema deberá rechazar la solicitud.
- **CA-1.6** El sistema deberá calcular la capacidad del perfil en mm a partir de θCC, θPMP y la profundidad efectiva, e informarla en la respuesta.
- **CA-1.7** El sistema deberá tratar la parcela como de secano, con riego igual a 0 todos los días, y registrar el supuesto «secano: riego = 0».
- **CA-1.8** Si la solicitud incluye cualquier dato de riego, entonces el sistema deberá rechazarla indicando que el MVP solo evalúa secano.
- **CA-1.9** Cuando se omita el Kc base de barbecho, el sistema deberá usar 0,20 y registrar el supuesto «Kc base de barbecho definido por el equipo AgroDSS (rango 0,15–0,20); no es un valor tabulado único de FAO-56».
- **CA-1.10** Si el Kc base de barbecho ingresado es menor o igual a 0 o supera el máximo plausible que fije el plan, entonces el sistema deberá rechazar la solicitud.
- **CA-1.11** Donde las coordenadas queden fuera de la provincia de San Luis, el sistema deberá comportarse según lo que resuelva la D-9 [NECESITA ACLARACIÓN: D-9].
- **CA-1.12** Si la latitud está fuera de [−60°, 60°], entonces el sistema deberá rechazar la solicitud indicando que el MVP está pensado para San Luis. (Aprobado por el equipo el 2026-11-15; evita las latitudes polares, donde la radiación de cielo despejado puede ser 0 y la ET₀ no se define.)

### RF-2 — Catálogo de cultivos y valores de referencia

**Por qué:** el usuario arma rotaciones libres. Necesita saber qué cultivos existen y partir de valores de referencia con fuente citada, sin confundirlos con valores calibrados.

- **CA-2.1** El sistema deberá ofrecer una consulta del catálogo de cultivos disponibles para componer rotaciones. Para cada cultivo informará: nombre en español, tipo (grano o cobertura) y valores de referencia (Kc inicial, medio y final; duración de las cuatro etapas de FAO-56; profundidad radicular inicial y máxima; fracción p; Ky del ciclo completo de FAO-33). Cada valor irá con su unidad y la cita de su fuente (documento y tabla o capítulo).
- **CA-2.2** El catálogo no deberá incluir valores de Ym, precios ni costos.
- **CA-2.3** Donde un cultivo carezca de un valor de referencia publicado en FAO-56 o FAO-33, el sistema deberá marcar ese parámetro como «sin referencia» y exigir que el usuario lo ingrese [NECESITA ACLARACIÓN: D-14].
- **CA-2.4** El catálogo inicial deberá incluir, como mínimo, maíz, soja, trigo y centeno de cobertura [NECESITA ACLARACIÓN: D-1].
- **CA-2.5** El sistema deberá identificar cada valor de referencia con la leyenda «valor tabulado FAO, no calibrado para el lote».
- **CA-2.6** El sistema deberá informar en el catálogo el Kc base de barbecho por defecto (0,20) y la regla de reducción por rastrojo (RF-8), cada uno con su fuente.

### RF-3 — Composición de las rotaciones A, B y C

**Por qué:** la comparación central de AgroDSS se da entre secuencias de cultivos. El orden, las fechas, los barbechos y el rastrojo determinan cuánta agua llega a cada cultivo.

**Entradas por rotación:** identificador (A, B o C); nombre opcional; lista ordenada de cultivos; cobertura de rastrojo al inicio de la ventana (%, opcional), que se aplica al barbecho previo al primer cultivo.

**Entradas por cultivo:**
- cultivo del catálogo;
- fecha de siembra, expresada como día y mes más el año de la ventana (1 o 2). El año 1 son los primeros doce meses desde la fecha de inicio de la ventana.
- Kc inicial, medio y final; duración de las cuatro etapas (días); profundidad radicular inicial y máxima (m); fracción p;
- solo para cultivos de grano: Ky e Ym (t/ha);
- cobertura de rastrojo que deja tras su cosecha o terminación (%, opcional), que se aplica al barbecho siguiente;
- datos económicos opcionales (ver RF-10).

- **CA-3.1** Cuando se reciba una solicitud, el sistema deberá aceptar de una a tres rotaciones, identificadas como A, B y C, cada una con al menos un cultivo [NECESITA ACLARACIÓN: D-8].
- **CA-3.2** El sistema deberá exigir, para cada cultivo, el cultivo del catálogo y la fecha de siembra. Para cada cultivo de grano exigirá además Ym > 0 (t/ha).
- **CA-3.3** Cuando se omita un parámetro con referencia en el catálogo (Kc, duración de etapas, Zr inicial, Zr máxima, p o Ky), el sistema deberá usar el valor de referencia. También deberá registrar un supuesto «valor tabulado FAO, no calibrado» con la rotación, el cultivo, el parámetro, el valor y la cita.
- **CA-3.4** Cuando el usuario ingrese un parámetro, el sistema deberá registrar su origen como «ingresado por el usuario». Lo rotulará igualmente como no calibrado.
- **CA-3.5** El sistema deberá derivar la fecha de fin de ciclo (cosecha o terminación) de cada cultivo como la fecha de siembra más la suma de las duraciones de sus cuatro etapas, e informarla en la respuesta [NECESITA ACLARACIÓN: D-7].
- **CA-3.6** Si en algún escenario elegido dos cultivos de una misma rotación quedan activos el mismo día, entonces el sistema deberá rechazar la solicitud indicando la rotación, los cultivos y el escenario.
- **CA-3.7** Si en algún escenario elegido el ciclo de un cultivo empieza antes del primer día de la ventana o termina después del último, entonces el sistema deberá rechazar la solicitud indicando el cultivo y el escenario.
- **CA-3.8** Si una fecha de siembra es el 29 de febrero, entonces el sistema deberá rechazar la solicitud, porque esa fecha no existe en todos los escenarios.
- **CA-3.9** Si algún parámetro está fuera de su rango físico, entonces el sistema deberá rechazar la solicitud indicando el parámetro y el rango válido. Los rangos físicos son: Kc ≥ 0; Ky ≥ 0; 0 < p < 1; 0 < Zr inicial ≤ Zr máxima; duraciones de etapa enteras y ≥ 1 día; cobertura de rastrojo entre 0 y 100 %. Los rangos plausibles adicionales los fija el plan.
- **CA-3.10** Si la Zr inicial o la Zr máxima de un cultivo superan la profundidad efectiva, entonces el sistema deberá limitarlas a la profundidad efectiva y registrar el supuesto correspondiente.
- **CA-3.11** El sistema deberá tratar como barbecho todo día de la ventana sin cultivo activo.
- **CA-3.12** Cuando se omita la cobertura de rastrojo de un barbecho, el sistema deberá usar 0 % (suelo desnudo, sin reducción) y registrar el supuesto «sin rastrojo declarado».
- **CA-3.13** Mientras un cultivo sea de cobertura, el sistema no deberá exigir Ym, Ky ni precio. Sí deberá aceptar sus costos directos.
- **CA-3.14** El sistema deberá permitir repetir un cultivo dentro de una rotación (por ejemplo, maíz → maíz) y aceptar rotaciones idénticas entre sí.

### RF-4 — Escenarios históricos

**Por qué:** la secuencia diaria real de lluvias y demanda atmosférica de años pasados permite mostrar cómo habría respondido cada rotación, sin pronosticar.

**Entradas:** fecha de inicio de la ventana, como día y mes común a todas las rotaciones y escenarios [NECESITA ACLARACIÓN: D-6]; lista de años de inicio.

- **CA-4.1** El sistema deberá aceptar entre 1 y 10 años de inicio distintos.
- **CA-4.2** El sistema deberá definir, para cada año de inicio Y, una ventana desde la fecha de inicio del año Y hasta el día anterior a esa misma fecha del año Y+2, con 730 o 731 días. Esa ventana se aplica por igual a todas las rotaciones.
- **CA-4.3** Si un año de inicio se repite, se piden más de 10 años o la fecha de inicio es el 29 de febrero, entonces el sistema deberá rechazar la solicitud.
- **CA-4.4** Si una ventana termina después de la fecha actual, entonces el sistema deberá rechazar la solicitud indicando el año.
- **CA-4.5** Si una ventana no queda completa dentro del período que la fuente cubre para todas las variables requeridas, entonces el sistema deberá bloquear ese escenario con su motivo y seguir con los demás.
- **CA-4.6** El sistema deberá aplicar la humedad inicial ingresada solo al primer día de cada escenario, sin arrastrar el estado final de otro escenario, y registrar ese supuesto.
- **CA-4.7** El sistema deberá permitir años de inicio con ventanas superpuestas (por ejemplo, 2010 y 2011). Tratará cada una como un escenario independiente.

### RF-5 — Consulta en vivo a NASA POWER

**Por qué:** el desafío exige datos NASA, y el equipo decidió que cada cálculo use la serie que entrega la API en el momento, sin mantener copias locales. Así se evita gestionar archivos y versiones de series en el MVP.

**Variables requeridas** (los códigos son los de referencia en POWER y se confirman en el plan):

| Magnitud | Variable de referencia | Unidad | Uso |
|---|---|---|---|
| Precipitación diaria corregida | PRECTOTCORR | mm/día | Balance hídrico |
| Temperatura máxima a 2 m | T2M_MAX | °C | ET₀ |
| Temperatura mínima a 2 m | T2M_MIN | °C | ET₀ |
| Humedad del aire | RH2M o T2MDEW [NECESITA ACLARACIÓN: D-11] | % o °C | ET₀ |
| Velocidad media diaria del viento a 2 m | WS2M | m/s | ET₀ |
| Velocidad máxima diaria del viento a 2 m | WS2M_MAX | m/s | Proxy de viento fuerte |
| Radiación solar global en superficie | ALLSKY_SFC_SW_DWN | MJ/m²/día | ET₀ |
| Elevación de la celda | Metadato de la respuesta | m | Presión atmosférica (ET₀) |

- **CA-5.1** Cuando se reciba una solicitud de cálculo válida, el sistema deberá consultar en vivo la API diaria de NASA POWER con una única consulta por solicitud, que cubra la ubicación, el período de todas las ventanas y todas las variables requeridas.
- **CA-5.2** El sistema deberá procesar la serie recibida durante la propia solicitud. No deberá guardarla en archivos, bases de datos ni caché, ni conservarla entre solicitudes.
- **CA-5.3** Si la solicitud es inválida (RF-16), entonces el sistema deberá rechazarla sin consultar NASA POWER.
- **CA-5.4** Si la consulta falla (sin conexión, error de la fuente o tiempo agotado), entonces el sistema deberá responder con un error en español que indique el motivo y que se puede reintentar. No deberá calcular ningún escenario.
- **CA-5.5** Si la respuesta de NASA POWER tiene un formato inesperado u omite por completo alguna variable requerida, entonces el sistema deberá responder con un error en español sin calcular ningún escenario. Los valores faltantes dentro de una variable presente se tratan según RF-6.
- **CA-5.6** El sistema deberá esperar la respuesta de NASA POWER solo hasta un tiempo máximo declarado, que fija el plan.
- **CA-5.7** El sistema deberá enviar a NASA POWER solo coordenadas, fechas y variables, sin ningún otro dato del usuario.

### RF-6 — Tratamiento de datos faltantes

**Por qué:** las reglas del proyecto prohíben rellenar datos. FAO-56 define procedimientos explícitos para estimar ET₀ cuando faltan algunas variables. Usarlos como supuesto declarado permite calcular sin ocultar la sustitución. La lluvia y la temperatura no tienen sustituto aceptable.

- **CA-6.1** El sistema deberá considerar faltante todo valor de relleno de la fuente (−999 o el que la fuente declare) y todo día ausente dentro de una ventana.
- **CA-6.2** El sistema no deberá interpolar, promediar con días vecinos ni copiar valores de otros días, celdas o fuentes.
- **CA-6.3** Si falta la precipitación, la temperatura máxima o la temperatura mínima en cualquier día de una ventana, entonces el sistema deberá bloquear ese escenario para todas las rotaciones. Indicará las variables y fechas faltantes y seguirá con los demás escenarios.
- **CA-6.4** Si falta la radiación solar de un día, entonces el sistema deberá estimarla con la fórmula de radiación de Hargreaves de FAO-56, a partir de Tmáx − Tmín y la radiación extraterrestre, con el coeficiente kRs declarado. Registrará el supuesto con la fecha.
- **CA-6.5** Si falta la humedad de un día, entonces el sistema deberá estimar la presión de vapor real con el procedimiento de FAO-56 para datos faltantes (punto de rocío aproximado a partir de Tmín, con la corrección para clima semiárido que fije el plan). Registrará el supuesto con la fecha.
- **CA-6.6** Si falta el viento a 2 m de un día, entonces el sistema deberá usar 2 m/s para la ET₀, el valor provisional que recomienda FAO-56, y registrar el supuesto con la fecha.
- **CA-6.7** El sistema deberá informar, por escenario, la cantidad de días sustituidos por variable y sus fechas.
- **CA-6.8** El sistema deberá usar los valores sustituidos solo para calcular la ET₀. No los presentará como datos de NASA POWER ni los usará en el proxy de viento fuerte.
- **CA-6.9** Donde se acuerde un límite máximo de días sustituidos por escenario, el sistema deberá bloquear el escenario que lo supere [NECESITA ACLARACIÓN: D-12].
- **CA-6.10** Si en cualquier día de una ventana la temperatura máxima es menor que la mínima, entonces el sistema deberá bloquear ese escenario para todas las rotaciones como «dato inconsistente de la fuente», indicando la fecha, y seguir con los demás escenarios. (Aprobado por el equipo el 2026-11-15.)

### RF-7 — Evapotranspiración de referencia (ET₀)

**Por qué:** la ET₀ es la demanda atmosférica que fija la demanda de cada cultivo y la evaporación del barbecho. FAO-56 Penman–Monteith es el método aprobado.

- **CA-7.1** El sistema deberá calcular la ET₀ diaria (mm/día) con FAO-56 Penman–Monteith para cada día de cada ventana. Usará las variables del RF-5, la latitud y la elevación de la celda, con flujo de calor del suelo diario igual a 0 y albedo de referencia 0,23.
- **CA-7.2** Si la ET₀ diaria calculada resulta negativa, entonces el sistema deberá usar 0 ese día y registrar el supuesto con la fecha.
- **CA-7.3** El sistema deberá reproducir el ejemplo trabajado de ET₀ diaria de FAO-56 (ejemplo 18) con una diferencia de 0,1 mm/día o menos.

### RF-8 — Balance hídrico diario sobre un perfil de profundidad fija (FAO-56)

**Por qué:** en secano, la diferencia entre rotaciones depende del agua que cada cultivo o barbecho deja para el siguiente. Un perfil fijo con raíces que crecen dentro de él permite representar esa transferencia y el agua que todavía no alcanzan raíces jóvenes, conservando la masa en toda la ventana.

**Perfil y raíces**

- **CA-8.1** El sistema deberá simular, para cada rotación y escenario calculado, un único perfil de suelo cuya profundidad es la profundidad efectiva y cuya capacidad es la capacidad del perfil (CA-1.6). El perfil se mantiene igual durante toda la ventana.
- **CA-8.2** El sistema deberá ejecutar el balance día a día, de forma continua, desde el primer hasta el último día de la ventana, sin días omitidos ni duplicados.
- **CA-8.3** El sistema deberá aplicar la humedad inicial (RF-1) al perfil completo el primer día de la ventana, distribuida de manera uniforme, y registrar ese supuesto.
- **CA-8.4** Mientras haya un cultivo activo, el sistema deberá hacer crecer su profundidad radicular desde la Zr inicial, el día de la siembra, hasta la Zr máxima, según el criterio de FAO-56 que precise el plan. Después la mantendrá hasta el fin del ciclo, siempre sin superar la profundidad efectiva.
- **CA-8.5** Mientras haya un cultivo activo, el sistema deberá permitir que extraiga agua solo de la porción del perfil explorada por sus raíces. El agua por debajo de las raíces permanecerá en el perfil y quedará disponible a medida que las raíces profundicen, y para los cultivos o barbechos siguientes.
- **CA-8.6** Cuando termine un cultivo o un barbecho, el sistema deberá usar el estado de agua del perfil de ese día como estado inicial del barbecho o cultivo siguiente, sin reiniciarlo.
- **CA-8.7** El sistema deberá repartir el agua entre la zona explorada por las raíces y el resto del perfil con el criterio que defina el plan, respetando CA-8.5, CA-8.6 y la conservación de masa (CA-8.14).

**Demanda y consumo**

- **CA-8.8** Mientras haya un cultivo activo, el sistema deberá calcular `ETc = Kc × ET₀` con la curva de Kc por etapas de FAO-56: Kc inicial constante en la etapa inicial; variación lineal hasta Kc medio en la etapa de desarrollo; Kc medio constante en la etapa media; variación lineal hasta Kc final en la etapa final [NECESITA ACLARACIÓN: D-13].
- **CA-8.9** Mientras haya un cultivo activo, el sistema deberá calcular la ETa aplicando el coeficiente de estrés Ks de FAO-56 sobre la zona explorada por las raíces: Ks = 1 mientras el agotamiento de esa zona no supere el AFA (`p × ADT`), y decrece linealmente hasta 0 cuando el agotamiento alcanza el ADT.
- **CA-8.10** Mientras no haya cultivo activo (barbecho), el sistema deberá calcular la evaporación demandada como `Kc base de barbecho × factor de rastrojo × ET₀`. El factor de rastrojo es `1 − 0,05 × (cobertura de rastrojo % / 10)`, según la regla de FAO-56 para acolchados orgánicos: alrededor de un 5 % menos de evaporación por cada 10 % de superficie cubierta. Con 0 % de rastrojo el factor es 1; con 100 % es 0,5.
- **CA-8.11** El sistema deberá mantener constante la cobertura de rastrojo durante todo el barbecho al que se aplica, y registrar el supuesto «rastrojo sin descomposición durante el barbecho».

**Entradas, excedentes y límites**

- **CA-8.12** El sistema deberá tomar como única entrada de agua la precipitación diaria, con riego y ascenso capilar iguales a 0. Toda la lluvia infiltra hasta completar la capacidad del perfil; la escorrentía por intensidad de lluvia no se representa (supuesto visible).
- **CA-8.13** Cuando la lluvia de un día supere la capacidad disponible del perfil (capacidad del perfil menos almacenamiento actual), el sistema deberá contabilizar ese exceso como «excedente perdido» (escorrentía o percolación profunda, sin distinguirlas) en ese mismo día. Ese exceso no deberá acumularse en el perfil ni en días posteriores.
- **CA-8.14** El sistema deberá mantener `0 ≤ almacenamiento ≤ capacidad del perfil` todos los días.
- **CA-8.15** El sistema deberá garantizar cada día que `ETa ≤ ETc` (o, en barbecho, evaporación real ≤ evaporación demandada) y que el consumo no supere el agua disponible ese día en la porción del perfil de la que se extrae.
- **CA-8.16** El sistema deberá verificar en cada corrida (rotación × escenario) la conservación de masa: `almacenamiento final − almacenamiento inicial = Σ precipitación − Σ ETa de cultivos − Σ evaporación de barbecho − Σ excedente perdido`, con un error de cierre de 0,01 mm o menos.
- **CA-8.17** Si una corrida no cumple CA-8.14, CA-8.15 o CA-8.16, entonces el sistema no deberá entregar resultados de esa corrida e informará un error interno de cálculo, en lugar de un resultado.

### RF-9 — Rendimiento bajo déficit (FAO-33)

**Por qué:** convierte el déficit hídrico del ciclo en una estimación de rendimiento relativa a un Ym declarado. Es la relación aprobada y más simple.

- **CA-9.1** Para cada cultivo de grano de cada rotación y escenario, el sistema deberá calcular ETm (Σ ETc) y ETa (Σ ETa) en mm entre la siembra y el fin del ciclo.
- **CA-9.2** El sistema deberá calcular `Ya = Ym × [1 − Ky × (1 − ETa/ETm)]` con el Ky del ciclo completo.
- **CA-9.3** Si la fórmula da un Ya negativo (Ky > 1 con déficit severo), entonces el sistema deberá informar Ya = 0 y registrar el supuesto.
- **CA-9.4** El sistema deberá garantizar `0 ≤ Ya ≤ Ym` en todo resultado.
- **CA-9.5** Si ETm de un cultivo es 0, entonces el sistema no deberá calcular Ya para ese cultivo e informará el motivo.
- **CA-9.6** El sistema deberá informar, por cultivo: fechas de siembra y fin, almacenamiento del perfil al sembrar y al terminar, ETm, ETa, ETa/ETm, días con estrés hídrico (Ks < 1), Ya (t/ha) e Ya/Ym.
- **CA-9.7** Mientras un cultivo sea de cobertura, el sistema deberá informar ETm, ETa, ETa/ETm, días con estrés y almacenamiento al sembrar y al terminar, y en el rendimiento la leyenda «no aplica (cultivo de cobertura)».

### RF-10 — Ingreso y margen bruto

**Por qué:** producir más no siempre equivale a ganar más. El agrónomo necesita comparar el resultado económico con sus propios precios y costos, sin que el sistema los pronostique.

**Entradas por cultivo (opcionales):** precio (moneda/t) solo para cultivos de grano y costos directos totales (moneda/ha). **Entrada por solicitud:** moneda única [NECESITA ACLARACIÓN: D-15].

- **CA-10.1** Donde un cultivo de grano tenga precio y costos directos, el sistema deberá calcular `ingreso = Ya × precio` (moneda/ha) y `margen bruto = ingreso − costos directos` (moneda/ha).
- **CA-10.2** Donde un cultivo de cobertura tenga costos directos, el sistema deberá informar un ingreso de 0 y un margen bruto igual a menos los costos directos.
- **CA-10.3** El sistema deberá calcular, por rotación y escenario, el ingreso, los costos y el margen bruto totales de la ventana como suma de sus cultivos.
- **CA-10.4** Si a algún cultivo de una rotación le faltan datos económicos, entonces el sistema deberá informar «margen de la rotación no calculado» y listar los cultivos sin datos, sin suponer valores en cero.
- **CA-10.5** Si un precio o un costo es negativo, entonces el sistema deberá rechazar la solicitud.
- **CA-10.6** El sistema deberá usar una única moneda por solicitud, declarada por el usuario, sin conversiones.
- **CA-10.7** El sistema no deberá llamar «pérdida» ni «pérdida neta» a un margen bruto negativo. Lo rotulará como «margen bruto negativo».
- **CA-10.8** El sistema deberá registrar como supuestos visibles que los precios y costos ingresados se aplican sin cambios a todos los escenarios históricos, que no son precios históricos ni pronosticados, y que no se descuentan entre el año 1 y el año 2.
- **CA-10.9** Si el rendimiento de un cultivo de grano no se pudo calcular (ETm = 0, CA-9.5), entonces el sistema deberá informar el ingreso y el margen de ese cultivo como «no calculado», con la nota «No se pudo calcular el margen porque hubo un fallo en la estimación de rendimiento (ETm = 0)», y el margen de la rotación como «no calculado». No deberá tomar el ingreso como 0. (Aprobado por el equipo el 2026-11-15.)

### RF-11 — Proxy de exposición del suelo (viento fuerte sin cultivo vivo)

**Por qué:** la protección del suelo es un criterio de decisión, sobre todo con centeno de cobertura. El método aprobado se limita a contar los días de viento fuerte que caen en períodos sin cultivo vivo, sin estimar erosión.

- **CA-11.1** El sistema deberá considerar día de viento fuerte aquel en que la velocidad máxima diaria del viento a 2 m (WS2M_MAX) de NASA POWER sea estrictamente mayor que 8 m/s (unos 29 km/h).
- **CA-11.2** El sistema deberá evaluar el viento fuerte solo en los días sin cultivo vivo. Un día está sin cultivo vivo cuando no está entre la siembra y el fin de ciclo de ningún cultivo de la rotación, incluidos los de cobertura.
- **CA-11.3** El sistema deberá informar, por rotación y escenario: días de la ventana, días con cultivo vivo, días sin cultivo vivo, días sin cultivo vivo con viento fuerte y días sin cultivo vivo sin dato de viento.
- **CA-11.4** Si falta el dato de WS2M_MAX en un día sin cultivo vivo, entonces el sistema deberá contarlo como «sin dato de viento», y no como día de viento fuerte ni calmo. Los 2 m/s sustituidos en WS2M para la ET₀ no se usan aquí.
- **CA-11.5** El sistema deberá informar en la respuesta la variable (WS2M_MAX, máxima diaria a 2 m), el umbral (> 8 m/s), la unidad y la fuente del umbral («decisión del equipo AgroDSS, revisión 3; no calibrado para erosión local»).
- **CA-11.6** El sistema deberá usar la expresión «días sin cultivo vivo» y no «suelo desnudo», aunque se haya declarado rastrojo. No deberá convertir el proxy en toneladas de suelo, pérdidas de nitrógeno ni de carbono.

### RF-12 — Rangos descriptivos entre escenarios

**Por qué:** el agrónomo necesita ver la variación de cada rotación entre los años elegidos sin que eso se interprete como probabilidad.

- **CA-12.1** El sistema deberá informar, por rotación, el mínimo, la mediana y el máximo entre escenarios calculados de: Ya y ETa/ETm de cada cultivo (identificado por su posición en la rotación); margen bruto total de la rotación, cuando esté calculado en todos los escenarios; y días sin cultivo vivo con viento fuerte. Junto a cada rango indicará la cantidad de escenarios (n).
- **CA-12.2** El sistema deberá calcular la mediana como el valor central y, si n es par, como el promedio de los dos valores centrales.
- **CA-12.3** Si solo hay un escenario calculado, entonces el sistema deberá informar ese valor único e indicar que no hay rango.
- **CA-12.4** El sistema deberá excluir de los rangos los escenarios bloqueados y listarlos.
- **CA-12.5** El sistema deberá rotular cada rango como «rango descriptivo de los años elegidos; no es una probabilidad ni un pronóstico».

### RF-13 — Procedencia de los datos

**Por qué:** la trazabilidad es la propuesta de valor de AgroDSS y la exigen las reglas del proyecto. Sin copias locales, la procedencia de cada respuesta es el único registro de qué datos se usaron.

- **CA-13.1** El sistema deberá incluir en la respuesta, para la serie climática usada: fuente (NASA POWER, API diaria, consulta en vivo); variables con su unidad; coordenadas solicitadas; celda o coordenadas que representa el dato según la fuente; elevación; rango de fechas consultado; versión de la fuente, si la informa; fecha y hora de la consulta; y faltantes por variable.
- **CA-13.2** El sistema deberá rotular la serie como «dato de modelo/reanálisis de NASA POWER a escala de celda; no es una medición del lote».
- **CA-13.3** El sistema deberá identificar en cada respuesta la versión del modelo de cálculo de AgroDSS que produjo los resultados.

### RF-14 — Registro de supuestos

**Por qué:** el agrónomo debe ver qué parte del resultado depende de valores no medidos o no calibrados, para interpretarlo con prudencia.

- **CA-14.1** El sistema deberá devolver una lista estructurada de supuestos. Cada supuesto llevará: identificador estable, descripción en español, alcance (solicitud, rotación, cultivo, barbecho, escenario o fecha), valor usado con su unidad y origen (usuario, referencia FAO con cita, equipo AgroDSS o sistema).
- **CA-14.2** El sistema deberá incluir siempre estos supuestos:
  - secano con riego = 0;
  - toda la lluvia infiltra hasta completar la capacidad del perfil, sin escorrentía por intensidad;
  - el excedente sobre la capacidad se pierde, sin distinguir escorrentía de percolación;
  - ascenso capilar = 0;
  - humedad inicial uniforme en el perfil e igual en cada escenario;
  - perfil de profundidad fija;
  - precios y costos constantes;
  - parámetros no calibrados;
  - dato climático de celda.
- **CA-14.3** Cuando ocurran, el sistema deberá incluir estos supuestos:
  - valores FAO no modificados;
  - Kc base de barbecho por defecto;
  - rastrojo omitido (0 %) o rastrojo sin descomposición;
  - sustituciones de datos faltantes (RF-6);
  - ET₀ negativa llevada a 0;
  - Ya llevado a 0;
  - Zr limitada por la profundidad efectiva.
- **CA-14.4** El sistema deberá agrupar los supuestos diarios repetidos en una sola entrada con el conteo y las fechas, para no inflar la respuesta.

### RF-15 — Contenido de la respuesta para el frontend

**Por qué:** la constitución prohíbe calcular en el frontend. La respuesta debe traer todo lo que se muestra, ya calculado y sin ambigüedad de unidades.

- **CA-15.1** Cuando un cálculo termine, el sistema deberá devolver una respuesta estructurada con:
  - (a) la entrada resuelta, con el valor efectivo y el origen de cada parámetro;
  - (b) la procedencia (RF-13);
  - (c) el estado de cada escenario (calculado o bloqueado, con su motivo);
  - (d) por rotación y escenario: el balance agregado, los resultados por cultivo (RF-9), la economía (RF-10) y el proxy de suelo (RF-11);
  - (e) los rangos por rotación (RF-12);
  - (f) los supuestos (RF-14);
  - (g) las advertencias de interpretación (RF-17).
- **CA-15.2** El sistema deberá incluir en el balance agregado de cada rotación y escenario, todo en mm: almacenamiento inicial y final del perfil, precipitación total, ET₀ total, ETa total de cultivos, evaporación total de barbechos, excedente perdido total y error de cierre de masa.
- **CA-15.3** El sistema deberá acompañar todo valor numérico de su unidad explícita.
- **CA-15.4** El sistema deberá entregar ya calculados todos los totales, cocientes, márgenes y rangos, de modo que el frontend no tenga que hacer ningún cálculo agronómico ni económico [NECESITA ACLARACIÓN: D-15 sobre diferencias entre rotaciones].
- **CA-15.5** El sistema no deberá incluir la serie diaria del balance ni la serie climática diaria en este MVP.
- **CA-15.6** El sistema deberá documentar el contrato de la respuesta y mantenerlo estable. Todo cambio incompatible requerirá una nueva versión del contrato.

### RF-16 — Validación y manejo de errores

**Por qué:** el agrónomo debe poder corregir sus datos en un solo intento y distinguir un error de entrada, una falla de NASA POWER y un escenario sin datos suficientes.

- **CA-16.1** Si la solicitud contiene datos inválidos, entonces el sistema deberá rechazarla completa, sin consultar NASA POWER ni calcular nada, e informar todos los errores encontrados (campo y motivo en español), no solo el primero.
- **CA-16.2** Si un escenario queda bloqueado por datos (RF-4 o RF-6), entonces el sistema deberá calcular los demás e informar qué escenario se bloqueó y por qué.
- **CA-16.3** Si todos los escenarios quedan bloqueados, entonces el sistema deberá responder sin resultados de rotaciones, con el motivo de cada bloqueo.
- **CA-16.4** El sistema deberá distinguir en sus respuestas de error tres casos: error de datos de entrada, falla o indisponibilidad de NASA POWER, y error interno de cálculo.
- **CA-16.5** Si ocurre un error interno de cálculo, entonces el sistema deberá responder con un mensaje en español sin detalles técnicos internos y no deberá entregar resultados parciales de la corrida afectada.
- **CA-16.6** El sistema deberá redactar en español todo mensaje visible para el usuario. Los identificadores técnicos del contrato irán en inglés.

### RF-17 — Lenguaje y límites de interpretación

**Por qué:** el documento de producto define AgroDSS como apoyo a la decisión, no como recomendador. Una simulación con parámetros no calibrados no debe leerse como pronóstico ni como recomendación validada.

- **CA-17.1** El sistema no deberá emitir probabilidades futuras, porcentajes de acierto, medidas de precisión ni intervalos de confianza.
- **CA-17.2** El sistema deberá incluir en cada respuesta la advertencia: «Escenarios históricos descriptivos: muestran cómo se habría comportado cada rotación con el clima de los años elegidos; no son pronósticos».
- **CA-17.3** El sistema deberá incluir la advertencia de que Kc, Ky, Ym y los parámetros de suelo son entradas o referencias no calibradas para el lote.
- **CA-17.4** El sistema no deberá atribuir al modelo efectos que no representa: nitrógeno, malezas, enfermedades, efectos residuales del centeno más allá del agua, erosión ni carbono.
- **CA-17.5** El sistema no deberá rotular ninguna rotación como «recomendada», «óptima» o «mejor», ni producir un orden de conveniencia entre rotaciones. Presenta las comparaciones para que el agrónomo decida.

---

## 5. Requisitos no funcionales

| ID | Requisito |
|---|---|
| **RNF-1 Reproducibilidad** | Con la misma solicitud, la misma respuesta de NASA POWER y la misma versión del modelo, los resultados deberán ser idénticos. Como la serie se consulta en vivo, una revisión de datos de la fuente puede cambiar resultados entre fechas. La procedencia (versión de la fuente y fecha y hora de consulta) debe permitir explicar esa diferencia. |
| **RNF-2 Dependencia de conexión** | Todo cálculo requiere acceso a NASA POWER en el momento. Sin conexión, el sistema responde con un error claro y no produce resultados, conforme al principio 5 enmendado de la constitución. |
| **RNF-3 Tiempo de respuesta** | Una vez recibida la respuesta de NASA POWER, el procesamiento de 3 rotaciones × 10 escenarios deberá completarse en 5 s o menos en una notebook del equipo. La espera de la consulta tiene un máximo declarado (CA-5.6). |
| **RNF-4 Tamaño de respuesta** | La respuesta se limita a resúmenes, sin series diarias, y los supuestos diarios se agrupan (CA-14.4). |
| **RNF-5 Unidades** | Unidades únicas y explícitas: mm, mm/día, °C, %, m/s, MJ/m²/día, m, m³/m³, t/ha, moneda/t y moneda/ha. |
| **RNF-6 Idioma** | Código, identificadores y commits en inglés. Mensajes, etiquetas y advertencias visibles en español. |
| **RNF-7 Separación lógica/interfaz** | Ninguna fórmula agronómica ni económica fuera del backend. La respuesta basta para mostrar resultados. |
| **RNF-8 Alcance tecnológico y persistencia** | Sin dependencias, servicios ni bases de datos nuevas sin aprobación humana registrada. El backend no almacena series climáticas, solicitudes ni resultados. |
| **RNF-9 Pruebas** | Toda fórmula (ET₀, balance, FAO-33, margen) con pruebas automáticas de conservación de masa, unidades y límites (`0 ≤ almacenamiento ≤ capacidad`, `ETa ≤ ETc`, `0 ≤ Ya ≤ Ym`) y de cronología diaria continua. Las pruebas automáticas no dependen de la red: usan respuestas simuladas (sintéticas) de NASA POWER. Sin pruebas verdes no hay merge. |
| **RNF-10 Calidad de código** | El linter y el chequeo de formato del proyecto, sin errores. El servidor arranca sin errores de importación. |
| **RNF-11 Privacidad** | Hacia NASA POWER solo salen coordenadas, fechas y nombres de variables. |
| **RNF-12 Uso responsable de la fuente** | Una única consulta a NASA POWER por solicitud válida y ninguna consulta para solicitudes inválidas. |
| **RNF-13 Contrato autodescriptivo** | El contrato de entrada y salida debe estar documentado de forma navegable para que el frontend lo consuma sin leer el código del backend. |

---

## 6. Casos límite

| # | Caso | Comportamiento esperado | Ref. |
|---|---|---|---|
| CL-1 | Coordenadas válidas pero fuera de San Luis o sobre el océano | Según lo que resuelva la D-9. Nunca se presenta como dato del lote. | RF-1 |
| CL-2 | Dos solicitudes con coordenadas distintas dentro de la misma celda de POWER | Cada una consulta la API y recibe la misma serie. La procedencia muestra la celda representada. | RF-5, RF-13 |
| CL-3 | Ventana que incluye un 29 de febrero (731 días) | El balance cubre los 731 días sin huecos ni duplicados. | RF-4, RF-8 |
| CL-4 | La fecha de fin de un ciclo varía un día según el escenario incluya o no un 29 de febrero (con 29 de febrero termina un día antes) y, en algunos escenarios, el cultivo se superpone con el siguiente | Se rechaza la solicitud indicando la rotación y los escenarios afectados. | CA-3.6 |
| CL-5 | Un cultivo que termina el último día de la ventana en un año bisiesto pero la excede en otro | Se rechaza la solicitud indicando el escenario. | CA-3.7 |
| CL-6 | Un año de inicio cuya ventana termina en un período que POWER todavía no publicó por completo | Escenario bloqueado con motivo; si la ventana termina en el futuro, rechazo. | CA-4.4, CA-4.5 |
| CL-7 | Un año de inicio anterior a la cobertura de alguna variable | Escenario bloqueado con motivo. | CA-4.5 |
| CL-8 | Falta la lluvia de un solo día | Escenario bloqueado para todas las rotaciones; se informan la fecha y la variable. | CA-6.3 |
| CL-9 | Falta la radiación en varios días de una ventana | Estimación de Hargreaves (FAO-56) en esos días, con supuesto agrupado y fechas. | CA-6.4, CA-14.4 |
| CL-10 | Faltan WS2M y WS2M_MAX un día sin cultivo vivo | ET₀ con 2 m/s como supuesto. En el proxy, ese día cuenta como «sin dato de viento». | CA-6.6, CA-11.4 |
| CL-11 | Faltan radiación, humedad y viento el mismo día | Las tres sustituciones aplicadas y registradas por separado. | RF-6 |
| CL-12 | ET₀ calculada negativa en un día invernal | Se usa 0 con supuesto. | CA-7.2 |
| CL-13 | Lluvia diaria mayor que la capacidad disponible del perfil | El perfil queda en su capacidad y el resto se informa como excedente perdido ese día. El cierre de masa se mantiene. | CA-8.13, CA-8.16 |
| CL-14 | Humedad inicial 0 % (perfil en punto de marchitez) | Ks = 0 y evaporación de barbecho = 0 hasta que llueva; sin valores negativos. | CA-8.9, CA-8.14 |
| CL-15 | Humedad inicial 100 % (perfil a capacidad de campo) | Válido; toda lluvia antes del primer consumo es excedente perdido. | CA-8.13 |
| CL-16 | Cultivo recién sembrado con raíces someras, superficie seca y agua almacenada en profundidad | El cultivo puede sufrir estrés aunque el perfil tenga agua debajo de sus raíces; esa agua queda disponible al profundizar. Es el comportamiento esperado, no un error. | CA-8.5 |
| CL-17 | Soja de segunda sembrada el día siguiente a la cosecha del trigo (barbecho de 0 días) | Válido; el agua del perfil pasa directamente del trigo a la soja. | CA-3.6, CA-8.6 |
| CL-18 | Centeno de cobertura que termina con el perfil casi seco antes de la soja | La soja empieza con ese almacenamiento; se informa el almacenamiento al sembrar. | CA-8.6, CA-9.6 |
| CL-19 | Barbecho con 100 % de rastrojo declarado | Factor de rastrojo 0,5: la evaporación demandada se reduce a la mitad. | CA-8.10 |
| CL-20 | Barbecho largo sin rastrojo declarado | Kc base 0,20 sin reducción; supuestos «sin rastrojo declarado» y, si corresponde, «Kc base por defecto». | CA-1.9, CA-3.12 |
| CL-21 | Día sin cultivo vivo con WS2M_MAX exactamente 8,0 m/s | No cuenta como viento fuerte (el umbral es estrictamente mayor). | CA-11.1 |
| CL-22 | Día con WS2M_MAX > 8 m/s mientras hay cultivo vivo | No se cuenta en el proxy. | CA-11.2 |
| CL-23 | Rotación con un solo cultivo y un barbecho largo | Válido; el barbecho consume agua según el Kc base y el rastrojo. | CA-8.10 |
| CL-24 | Rotación solo con cultivo de cobertura | Sin Ya; margen igual a menos los costos, rotulado «margen bruto negativo», no «pérdida». | CA-9.7, CA-10.7 |
| CL-25 | Ky > 1 con déficit severo que da Ya teórico negativo | Ya = 0 con supuesto. | CA-9.3 |
| CL-26 | Zr máxima mayor que la profundidad efectiva (por ejemplo, tosca a poca profundidad) | Zr limitada a la profundidad efectiva, con supuesto. | CA-3.10 |
| CL-27 | Zr inicial mayor que la Zr máxima, θPMP ≥ θCC, humedad > 100 %, Ym = 0 en un cultivo de grano, rastrojo > 100 % o precio negativo | Rechazo con la lista completa de errores, sin consultar NASA POWER. | RF-16, CA-5.3 |
| CL-28 | Años de inicio repetidos, más de 10 años o fecha de siembra 29 de febrero | Rechazo. | CA-4.3, CA-3.8 |
| CL-29 | Datos económicos incompletos en un cultivo de la rotación | Margen de la rotación «no calculado», con lista de cultivos sin datos. Los márgenes de los cultivos completos sí se informan. | CA-10.4 |
| CL-30 | Sin conexión a internet, o NASA POWER caído durante la demo | Error claro en español («no se pudo consultar NASA POWER; reintente»), sin resultados. | CA-5.4, RNF-2 |
| CL-31 | NASA POWER responde con tiempo agotado, formato inesperado o sin una variable requerida | Error claro, sin cálculo parcial. | CA-5.4, CA-5.5 |
| CL-32 | Todos los escenarios bloqueados | Respuesta sin resultados de rotaciones y con los motivos. | CA-16.3 |
| CL-33 | Tres rotaciones idénticas | Válido; resultados idénticos y ningún rótulo de «mejor». | CA-3.14, CA-17.5 |
| CL-34 | Ventanas superpuestas (por ejemplo, años 2010 y 2011) | Válido; escenarios tratados por separado. Los rangos siguen siendo descriptivos (comparten un año de clima). | CA-4.7, RF-12 |
| CL-35 | Dos escenarios calculados (n = 2) | La mediana es el promedio de ambos valores y se informa n = 2. | CA-12.2 |
| CL-36 | Un día con Tmáx < Tmín en la serie de NASA POWER | Escenario bloqueado para todas las rotaciones como «dato inconsistente de la fuente», con la fecha. | CA-6.10 |

---

## 7. Fuera de alcance

- Almacenamiento, caché o copias de respaldo de series climáticas, y funcionamiento sin conexión.
- Serie diaria del balance o de clima en la respuesta (posible ampliación futura).
- Riego en cualquier forma, y simular como secano un lote regado.
- Modelos no aprobados: AquaCrop, APSIM, DSSAT, RUSLE/RUSLE2, RWEQ, Monte Carlo y aprendizaje automático.
- Fuentes distintas de NASA POWER: GPM/IMERG, MODIS, Landsat, SMAP, GLDAS, ERA5, Sentinel-2, SoilGrids, INTA, MapBiomas y GAEZ. Su incorporación requiere aprobación explícita. También quedan fuera las fuentes solo de EE. UU. (NLDAS, PRISM, SSURGO, CDL, OpenET, etc.).
- Kc dual (evaporación del suelo separada de la transpiración) y Ky por etapa.
- Efectos del rastrojo distintos de la reducción de la evaporación en barbecho: descomposición, cambios en la infiltración o en la erosión.
- Separación entre escorrentía y percolación profunda, infiltración limitada por intensidad de lluvia, ascenso capilar y napa freática.
- Nitrógeno, carbono, materia orgánica, malezas, enfermedades, granizo, heladas y efectos residuales del centeno más allá del agua.
- Erosión en toneladas o cualquier cuantificación de pérdida de suelo.
- Pronósticos, probabilidades, intervalos de confianza, métricas de precisión y etiquetas ENSO.
- Recomendación automática de rotaciones o un orden de conveniencia entre ellas.
- Resultado neto (estructura, administración, arrendamiento), precios históricos o proyectados, conversión de monedas y descuento financiero.
- Calibración o validación contra rendimientos observados.
- Autenticación, cuentas de usuario, historial de consultas, base de datos y generación de informes (PDF u otros).
- Polígonos de lote o mapas (solo un punto por parcela).
- Cualquier trabajo del frontend.

---

## 8. Criterios de finalización

La funcionalidad se considera terminada cuando se cumple todo lo siguiente:

- [ ] **Gobierno:** la enmienda del principio 5 de la constitución está commiteada y aprobada en el PR.
- [ ] Cada criterio de aceptación de RF-1 a RF-17 tiene al menos una prueba automática que lo verifica, o una justificación escrita de por qué no se puede probar automáticamente.
- [ ] **Conservación de masa:** error de cierre de 0,01 mm o menos en todas las corridas de prueba (rotación × escenario), incluidas las de lluvias extremas, suelo seco, barbechos largos y transiciones sin barbecho.
- [ ] **Límites:** pruebas que verifican cada día `0 ≤ almacenamiento ≤ capacidad del perfil`, `ETa ≤ ETc`, evaporación de barbecho ≤ demandada, consumo ≤ agua disponible y `0 ≤ Ya ≤ Ym`.
- [ ] **Transferencia:** una prueba verifica que el almacenamiento al terminar un cultivo o barbecho es exactamente el inicial del siguiente.
- [ ] **Raíces:** una prueba verifica que un cultivo no extrae agua por debajo de su Zr del día y que esa agua queda disponible al profundizar.
- [ ] **Barbecho y rastrojo:** pruebas del Kc base por defecto y del factor de rastrojo (0 % → 1; 50 % → 0,75; 100 % → 0,5).
- [ ] **Excedente:** una prueba verifica que la lluvia por encima de la capacidad disponible se informa como excedente perdido y no se acumula.
- [ ] **Proxy de viento:** pruebas con WS2M_MAX = 8,0 (no cuenta), 8,1 sin cultivo vivo (cuenta) y 8,1 con cultivo vivo (no cuenta).
- [ ] **Cronología:** 730 o 731 días por ventana, sin huecos ni duplicados.
- [ ] **ET₀:** se reproduce el ejemplo 18 de FAO-56 con 0,1 mm/día de diferencia o menos.
- [ ] **Faltantes:** pruebas con series sintéticas que cubren el bloqueo por lluvia o temperatura, las tres sustituciones FAO-56 y su registro como supuestos.
- [ ] **NASA POWER:** las pruebas automáticas usan respuestas simuladas y no requieren red; cubren error, tiempo agotado, formato inesperado y variable ausente. Además, una prueba manual documentada contra la API real para un punto de San Luis completa una solicitud de 3 rotaciones × al menos 3 escenarios.
- [ ] **Sin persistencia:** se verifica que el backend no escribe series climáticas en disco.
- [ ] **Lenguaje:** una prueba verifica que los mensajes y rótulos no contienen «pérdida neta», «probabilidad», «precisión», «recomendada», «óptima» ni «mejor» aplicados a resultados o rotaciones.
- [ ] El contrato de entrada y salida está documentado y el frontend puede consultarlo.
- [ ] Linter, formato y pruebas del backend en verde. El servidor arranca sin errores de importación.
- [ ] Cada [NECESITA ACLARACIÓN] de esta especificación está resuelto o diferido explícitamente por un humano.
- [ ] Informe al equipo: qué cambió, qué pruebas corrieron y qué supuestos nuevos se introdujeron.

---

## 9. Dudas

### 9.1 Dudas abiertas

Ninguna bloquea el comienzo del plan. Si el equipo no indica otra cosa, el plan adoptará la propuesta por defecto y la registrará como decisión.

| ID | Duda | Propuesta por defecto (a confirmar) |
|---|---|---|
| **D-1** [NECESITA ACLARACIÓN] | ¿Qué cultivos forman el catálogo inicial? ¿La soja de segunda es un cultivo aparte (con duraciones de etapa propias) o es soja con otra fecha? ¿Se incluyen girasol o sorgo? | Maíz, soja de primera, soja de segunda, trigo y centeno de cobertura. |
| **D-6** [NECESITA ACLARACIÓN] | ¿La fecha de inicio de la ventana es fija (por ejemplo, 1 de julio, inicio de la campaña agrícola) o la elige el usuario? | Elegida por el usuario, con 1 de julio sugerido. |
| **D-7** [NECESITA ACLARACIÓN] | ¿Cómo se ingresa el ciclo: siembra + duraciones de etapa (propuesta actual), o siembra + fecha de cosecha o terminación con ajuste proporcional de las etapas? ¿Cómo se trunca la curva de Kc del centeno terminado antes de la madurez? | Siembra + duraciones; para el centeno, el usuario acorta la etapa final. |
| **D-8** [NECESITA ACLARACIÓN] | ¿Se exigen exactamente tres rotaciones o se aceptan de una a tres? | De una a tres. |
| **D-9** [NECESITA ACLARACIÓN] | ¿Se restringe o se advierte cuando las coordenadas están fuera de San Luis? | Aceptar con una advertencia visible «fuera del ámbito previsto del producto». |
| **D-11** [NECESITA ACLARACIÓN] | Hay que verificar la cobertura real (fecha de inicio por variable), la versión vigente y las unidades de NASA POWER. ¿Humedad como RH2M (humedad relativa media) o como T2MDEW (punto de rocío, el método preferido por FAO-56)? | Verificar en el plan; preferir punto de rocío si su cobertura es completa. |
| **D-12** [NECESITA ACLARACIÓN] | ¿Hay un máximo de días sustituidos por los métodos FAO-56 por escenario antes de bloquearlo? | Sin límite en el MVP, pero informado de forma prominente. |
| **D-13** [NECESITA ACLARACIÓN] | ¿Se ajustan Kc medio y Kc final por clima (FAO-56, ecuación 62: humedad mínima ≠ 45 % y viento ≠ 2 m/s)? En San Luis, con su clima semiárido, el ajuste suele aumentar Kc. | No ajustar en el MVP y declararlo como supuesto. |
| **D-14** [NECESITA ACLARACIÓN] | ¿Existen valores de referencia de FAO-56 o FAO-33 para el centeno de cobertura? Si no existen, ¿son obligatorios del usuario o el equipo cita otra fuente? | Obligatorios del usuario si no hay referencia FAO. |
| **D-15** [NECESITA ACLARACIÓN] | ¿Qué moneda se usa (ARS o USD)? ¿Se carga como costo directo la terminación del centeno? Como el frontend no puede calcular, ¿debe el backend calcular diferencias entre rotaciones (por ejemplo, margen de B − A), sin rotular ninguna como mejor? | Moneda declarada por el usuario; terminación como costo directo; diferencias entre rotaciones calculadas por el backend, sin orden de conveniencia. |
| **D-16** [NECESITA ACLARACIÓN] | Unidad de entrada del suelo: ¿θCC y θPMP (m³/m³), o agua útil (mm/m) cuando el agrónomo solo dispone de ese dato? | θ (m³/m³); evaluar aceptar agua útil como alternativa. |

### 9.2 Dudas resueltas en la revisión 2

| ID | Resolución | Dónde se aplica |
|---|---|---|
| D-2 | Perfil de profundidad fija (profundidad efectiva del usuario); raíces que crecen dentro del perfil; el agua del perfil pasa de un cultivo o barbecho al siguiente. | Decisión 7, RF-8 |
| D-3 | Kc base de barbecho 0,20 por defecto (rango 0,15–0,20), editable y reducido por rastrojo según la regla de FAO-56 para acolchados. | Decisión 8, CA-1.9, CA-8.10 |
| D-4 | La lluvia que supera la capacidad disponible del perfil es excedente perdido y no se acumula. | Decisión 9, CA-8.12, CA-8.13 |
| D-5 | WS2M_MAX > 8 m/s (máximo diario, revisión 3), contado solo en días sin cultivo vivo. | Decisión 10, RF-11 |
| D-10 | Sin efecto: al no haber datos precargados, no hay ubicaciones de demo que definir. | Decisión 2, RF-5 |
| D-17 | Prevalece AGENTS: solo NASA POWER; GPM, MODIS, Landsat y SMAP requieren aprobación. La especificación se alinea con el documento de producto: apoyo a decisiones, no recomendador. | Decisión 11, CA-17.5, §7 |
