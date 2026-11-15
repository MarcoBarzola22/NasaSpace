# Investigación previa 001 — Verificaciones del backend MVP de AgroDSS

Este documento reúne las verificaciones previas del plan (§12). No contiene series climáticas: solo claves, unidades y metadatos.

| Sección | Tarea | Estado |
|---|---|---|
| V-1 NASA POWER | T001 | Completa y aprobada el 2026-11-15 |
| V-2 Catálogo FAO | T002 | Completa y aprobada el 2026-11-15 |
| V-3 Ejemplos FAO-56 | T003 | Sin empezar |
| Prueba en vivo | T050 | Sin empezar |

---

## V-1 NASA POWER

**Fecha de la verificación:** 2026-11-15 · **Versión de la API observada:** `v2.10.3` · **Comunidad:** `AG`

**Método.** Lectura de la documentación oficial de POWER y cuatro consultas manuales de prueba al endpoint diario de punto, con un punto genérico de San Luis y rangos de 5 a 14 días, más una consulta larga (1981-01-01 a 2026-11-10) para comprobar que no hay límite de rango. No se guardó ninguna serie.

**Limitación del método.** Las páginas y respuestas se leyeron con una herramienta de lectura que resume el contenido; los valores de la tabla provienen de esas lecturas. Las cadenas de unidades y las rutas JSON son lo que más importa para el parser (T040). Antes de cerrar T040, un humano debe contrastarlas una vez con una consulta propia (ver «Verificación humana sugerida» al final).

### Tabla de verificación

| # | Elemento | Resultado verificado | Fuente |
|---|---|---|---|
| 1 | URL del endpoint diario de punto | `https://power.larc.nasa.gov/api/temporal/daily/point`. Parámetros de consulta: `parameters` (lista separada por comas), `community` (`AG`), `latitude`, `longitude`, `start` y `end` (`YYYYMMDD`), `format` (`JSON`) y `time-standard` (`UTC` o `LST`). Los demás parámetros opcionales (`site-elevation`, `wind-elevation`, `wind-surface`) no se usan. La documentación no declara valores por defecto para `community` ni `format`, por lo que se envían siempre de forma explícita. | [Daily API](https://power.larc.nasa.gov/docs/services/api/temporal/daily/) |
| 2a | `PRECTOTCORR` | Disponible en comunidad AG, diario: **sí**. Nombre largo: «Precipitation Corrected». Unidad exacta devuelta: `mm/day`. | [Catálogo de parámetros AG diario](https://power.larc.nasa.gov/api/system/manager/parameters?community=ag&temporal=daily&user=anonymous) |
| 2b | `T2M_MAX` | Disponible: **sí**. «Temperature at 2 Meters Maximum». Unidad: `C`. | ídem |
| 2c | `T2M_MIN` | Disponible: **sí**. «Temperature at 2 Meters Minimum». Unidad: `C`. | ídem |
| 2d | `T2MDEW` | Disponible: **sí**. «Dew/Frost Point at 2 Meters». Unidad: `C`. | ídem |
| 2e | `WS2M` | Disponible: **sí**. «Wind Speed at 2 Meters» (media). Unidad: `m/s`. | ídem |
| 2f | `WS2M_MAX` | Disponible: **sí**. «Wind Speed at 2 Meters Maximum». Unidad: `m/s`. Según el catálogo es el máximo de los valores **horarios** del día, no una ráfaga instantánea (ver observación O-3). | ídem |
| 2g | `ALLSKY_SFC_SW_DWN` | Disponible: **sí**. «All Sky Surface Shortwave Downward Irradiance». Unidad: `MJ/m^2/day`. | ídem |
| 3 | Dato de relleno | Ruta JSON `header.fill_value`, valor `-999.0` (número decimal). Confirmado en las 3 consultas con datos. El valor aparece dentro de `properties.parameter.<VARIABLE>.<YYYYMMDD>`. | [Daily API](https://power.larc.nasa.gov/docs/services/api/temporal/daily/) y consultas de prueba |
| 4 | Versión de la API | Ruta JSON `header.api.version`; valor observado `"v2.10.3"`. El nombre está en `header.api.name` (`"POWER Daily API"`). | Consultas de prueba |
| 5 | Elevación | Ruta JSON `geometry.coordinates[2]`, en metros. El orden del arreglo es `[longitud, latitud, elevación]` (observado: `[-65.47, -33.68, 699.34]`). No hay una clave con nombre; la posición es la única referencia. La documentación leída no aclara a qué superficie corresponde esa elevación (ver O-5). | Consultas de prueba |
| 6 | Inicio de cobertura diaria | **Meteorología** (`PRECTOTCORR`, `T2M_MAX`, `T2M_MIN`, `T2MDEW`, `WS2M`, `WS2M_MAX`): **1981-01-01**. **Radiación** (`ALLSKY_SFC_SW_DWN`): **1984-01-01**; el servicio informa «radiation parameters are not available until 1984-1-1». Fin de cobertura: casi tiempo real; ver O-2 por el retraso observado. | [Daily API](https://power.larc.nasa.gov/docs/services/api/temporal/daily/) (inicio 1981-01-01) y consultas de prueba (1984) |
| 7 | `time-standard` | Soportado para datos diarios, con valores `UTC` y `LST`. Valor por defecto: **`LST`** («Daily API defaults to providing LST»). Se observó `header.time_standard: "LST"`. El plan propone enviar `time-standard=LST` de forma explícita, para que el resultado no dependa del valor por defecto. | [Daily API](https://power.larc.nasa.gov/docs/services/api/temporal/daily/) |
| 8 | Límites por consulta | **Parámetros:** máximo **20** por consulta de punto (se usan 7). **Rango de fechas:** la documentación no declara un máximo; una consulta de 1981-01-01 a 2026-11-10 (unos 16 800 días) devolvió datos sin error (respuesta de más de 1,9 millones de caracteres). **Frecuencia:** la documentación solo lista el código 429 («Too Many Requests») sin umbrales. **Tiempo:** la documentación indica que las APIs de aplicación «típicamente completan en menos de un minuto». **Errores:** 200 correcto, 422 «Validation Error», 429; el formato del cuerpo de error no está descrito. | [Daily API](https://power.larc.nasa.gov/docs/services/api/temporal/daily/) y [visión general de la API](https://power.larc.nasa.gov/docs/services/api/) |
| 9 | Esqueleto de la respuesta (solo claves) | Ver el esqueleto debajo de la tabla. | Consultas de prueba |

### Esqueleto de la respuesta JSON (sin valores de la serie)

```
{
  "type": "Feature",
  "geometry": {
    "type": "Point",
    "coordinates": [ <longitud>, <latitud>, <elevación_m> ]
  },
  "properties": {
    "parameter": {
      "<VARIABLE>": { "<YYYYMMDD>": <número; -999.0 si falta>, ... },
      ...
    }
  },
  "header": {
    "title": "NASA/POWER Source Native Resolution Daily Data",
    "api": { "version": "<vX.Y.Z>", "name": "POWER Daily API" },
    "sources": [ "MERRA2", "POWER" ],
    "fill_value": -999.0,
    "start": "<YYYYMMDD>",
    "end": "<YYYYMMDD>",
    "time_standard": "<LST|UTC>"
  },
  "messages": [ <texto>, ... ],
  "parameters": {
    "<VARIABLE>": { "units": "<cadena exacta>", "longname": "<nombre>" }, ...
  },
  "times": { "data": <segundos>, "process": <segundos> }
}
```

La primera consulta de prueba devolvió el esquema completo. La consulta larga se leyó solo parcialmente y no mostró el bloque `header`: no se pudo confirmar ahí su presencia ni un posible error de recorte, por lo que no se deduce nada de ella salvo que devolvió datos.

### Cadenas de unidades exactas (para el parser, plan §6.3 paso 2)

| Variable | Cadena en `parameters.<VARIABLE>.units` | Unidad del modelo |
|---|---|---|
| `PRECTOTCORR` | `mm/day` | mm/día |
| `T2M_MAX`, `T2M_MIN`, `T2MDEW` | `C` | °C |
| `WS2M`, `WS2M_MAX` | `m/s` | m/s |
| `ALLSKY_SFC_SW_DWN` | `MJ/m^2/day` | MJ/m²/día |

El plan escribía las unidades con su forma legible (°C, mm/día, MJ/m²/día). El parser debe comparar contra **estas cadenas literales** y mantener un mapa hacia las unidades legibles de la respuesta.

### Observaciones que afectan al plan y a las tareas

Estas observaciones se desprenden de las consultas de prueba. **Ninguna cambia un requisito del spec; las tres primeras sí requieren precisar el plan o una tarea.**

- **O-1. La radiación desaparece si todo el rango es anterior a 1984.** Una consulta del 1981-01-01 al 1981-01-05 devolvió **seis** variables (sin `ALLSKY_SFC_SW_DWN`) y un mensaje en `messages`. Una consulta del 1983-12-29 al 1984-01-03 devolvió las **siete**, con `-999.0` hasta el 1983-12-31 y datos desde el 1984-01-01.
  - *Consecuencia:* el plan trata una variable ausente como `power_bad_response` (CA-5.5). Una solicitud cuyas ventanas empiecen todas antes de 1984 recibiría un 502 engañoso, en lugar de escenarios bloqueados por cobertura (CA-4.5).
  - *Propuesta:* la validación semántica (T036) o el servicio (T043) deben bloquear por cobertura antes de consultar, con el inicio de la radiación en `Settings` (T005): 1984-01-01. Las ventanas que empiecen antes de esa fecha quedan bloqueadas. Además, la consulta a POWER no debe pedir fechas anteriores al inicio de cobertura de la radiación.
- **O-2. Retraso de publicación y huecos recientes.** Consultando el 2026-11-15, todas las variables meteorológicas estaban completas hasta el 2026-11-12 y con `-999.0` los días 13 y 14. La radiación tenía además huecos aislados (2026-11-05) y faltaba desde el 2026-11-11.
  - *Consecuencia:* confirma la regla del plan (T-13): una racha final de `-999.0` es «aún no publicado» y bloquea el escenario. El hueco aislado del 2026-11-05 se sustituye con Hargreaves (RF-6). Una ventana que termina en los últimos días puede quedar bloqueada.
- **O-3. Alcance de `WS2M_MAX`.** El catálogo de POWER lo describe como el valor máximo de las velocidades **horarias** del día, y la documentación de metodología consultada no lo define. El rótulo de CA-11.5 debería decir «máximo de los valores horarios del día», no «ráfaga». Los valores de las consultas de prueba (entre 2,96 y 6,92 m/s en los días mirados) quedaron lejos de 8 m/s. Esto respalda el riesgo R-5 del plan: el umbral de 8 m/s puede dar cero días casi siempre. Se mide en T050 y no se cambia el umbral sin decisión humana.
- **O-4. Resolución espacial nativa.** La metodología de POWER describe, para su versión de referencia, una grilla de ½° de latitud por ⅝° de longitud para la meteorología y de 1° × 1° para la radiación. La documentación no la restablece para la versión actual. El texto `spatial_note` de la procedencia debe decir «celda de varios kilómetros» sin cifras exactas, como ya prevé el plan, salvo que el equipo las confirme.
- **O-5. Elevación.** Se informa un valor por punto (por ejemplo, 699,34 m para el punto de prueba). La documentación leída no dice si es la elevación de la celda del reanálisis o la del terreno. Se usa tal cual para la presión atmosférica (ET₀) y se registra en la procedencia como «elevación informada por NASA POWER». Se puede enviar `site-elevation` en una versión futura.
- **O-6. Fuente de cada variable.** Según el catálogo, `PRECTOTCORR` es la precipitación de MERRA-2 corregida con sesgo; `T2MDEW` y la radiación provienen de la fuente (MERRA-2/CERES) y las temperaturas y el viento los calcula POWER a partir de valores horarios. Todo es modelo o reanálisis, coherente con la etiqueta de CA-13.2.

### Decisiones de la tarea

| Dato | Valor para `Settings` (T005) y el cliente (T039) |
|---|---|
| Variables solicitadas | `PRECTOTCORR,T2M_MAX,T2M_MIN,T2MDEW,WS2M,WS2M_MAX,ALLSKY_SFC_SW_DWN` |
| Comunidad, formato, estándar de tiempo | `AG`, `JSON`, `LST` (enviado explícitamente) |
| Inicio de cobertura | Meteorología 1981-01-01; radiación 1984-01-01 |
| Valor de relleno | Leer `header.fill_value`; si falta, usar `-999.0` |
| Versión de la fuente | `header.api.version` |
| Elevación | `geometry.coordinates[2]` |
| Timeouts | Conexión 10 s y lectura 60 s (sin cambios: la documentación indica «menos de un minuto» típico) |
| Límite de rango | Sin límite documentado; el riesgo R-1 sigue vigente |

### Verificación humana sugerida (2 minutos)

Ejecutar una vez, desde cualquier terminal, y comparar con la tabla (solo `header`, `geometry` y `parameters`):

```
curl "https://power.larc.nasa.gov/api/temporal/daily/point?parameters=PRECTOTCORR,T2M_MAX,T2M_MIN,T2MDEW,WS2M,WS2M_MAX,ALLSKY_SFC_SW_DWN&community=AG&latitude=-33.68&longitude=-65.47&start=19831229&end=19840103&format=JSON&time-standard=LST"
```

Debe mostrar las 7 variables, `header.fill_value = -999.0`, `header.api.version`, la elevación en `geometry.coordinates[2]`, las unidades `C`, `mm/day`, `m/s`, `MJ/m^2/day` y radiación en `-999.0` hasta el 19831231.

---

## V-2 Catálogo FAO

**Fecha:** 2026-11-15 · **Archivo generado:** `backend/app/data/crop_catalog.json` (la tarea T031 agrega el cargador y sus pruebas).

**Origen de los valores.** Los valores de Kc, duraciones de maíz y rangos de Zr los aportó el agrónomo del equipo desde FAO-56; se contrastaron con las tablas oficiales. Los valores de **p** y **Ky**, las duraciones de trigo y soja y los Kc del centeno los completó Claude desde las mismas tablas, y están marcados con ⚑ para confirmación.

**Códigos de cita** (cada celda de la tabla remite a uno de estos):

| Código | Cita |
|---|---|
| **T11** | FAO-56, Cap. 6, Tabla 11 (longitud de etapas). <https://www.fao.org/4/x0490e/x0490e0b.htm> |
| **T12** | FAO-56, Cap. 6, Tabla 12 (Kc y altura). <https://www.fao.org/4/x0490e/x0490e0b.htm> |
| **T22** | FAO-56, Cap. 8, Tabla 22 (Zr máxima y fracción p). <https://www.fao.org/4/x0490e/x0490e0e.htm> |
| **T24** | FAO-56, Cap. 8, Tabla 24, que reproduce los Ky estacionales de FAO-33. <https://www.fao.org/4/x0490e/x0490e0e.htm> |
| **EQ** | Decisión técnica del equipo AgroDSS; no es un valor de FAO |

### Tabla de 5 cultivos × 8 parámetros

| Parámetro | `maize` | `soybean_first` | `soybean_second` | `wheat` | `rye_cover` |
|---|---|---|---|---|---|
| **Kc inicial** | 0,30 (T12, grupo Cereales) | 0,40 (T12, grupo Leguminosas) ⚑ | 0,40 (T12, grupo Leguminosas) ⚑ | 0,70 (T12, Winter Wheat, suelos no congelados) | 0,30 (T12, grupo Cereales; asimilado a cereales menores) |
| **Kc medio** | 1,20 (T12, Maize field) | 1,15 (T12, Soybeans) | 1,15 (T12, Soybeans) | 1,15 (T12, Winter Wheat) | 1,15 (T12, Barley/Oats; asimilado a cereales menores) |
| **Kc final** | 0,35 (T12, nota 11: cosecha seca) | 0,50 (T12, Soybeans) | 0,50 (T12, Soybeans) | 0,25 (T12, nota 10: cosecha mecánica) | 0,25 (T12, Barley/Oats; asimilado a cereales menores) ⚑ |
| **Etapas (días) ini/des/med/fin** | 25/40/45/30 (T11, Maize grain, clima árido, dic./ene.) | 20/35/60/25 (T11, Soybeans, centro de EE. UU., mayo; la tabla imprime desarrollo 30/35) ⚑ | sin referencia (T11 no distingue la soja de segunda) | 20/60/70/30 (T11, Winter Wheat, dic., California) ⚑ | sin referencia (T11 solo trae ciclos completos) |
| **Zr inicial (m)** | 0,25 (EQ; rango 0,2–0,3) ⚑ | 0,25 (EQ) ⚑ | 0,25 (EQ) ⚑ | 0,25 (EQ) ⚑ | 0,25 (EQ) ⚑ |
| **Zr máxima (m)** | 1,2 (EQ; rango T22: 1,0–1,7) | 0,6 (T22: 0,6–1,3; extremo inferior) ⚑ | 0,6 (T22: 0,6–1,3; extremo inferior) ⚑ | 1,5 (T22, Wheat Winter: 1,5–1,8; extremo inferior) ⚑ | 1,0 (T22, Barley/Oats: 1,0–1,5; extremo inferior) ⚑ |
| **Fracción p** | 0,55 (T22) ⚑ | 0,50 (T22) ⚑ | 0,50 (T22) ⚑ | 0,55 (T22) ⚑ | 0,55 (T22, Barley/Oats) ⚑ |
| **Ky** | 1,25 (T24) ⚑ | 0,85 (T24) ⚑ | 0,85 (T24) ⚑ | 1,05 (T24) ⚑ | no aplica (cultivo de cobertura) |

**Fuente del centeno:** «asimilado a cereales menores (avena/cebada)», según lo indicado por el agrónomo; el centeno no figura en las tablas de FAO-56. La soja de segunda comparte con la soja de primera todos los valores por ser la misma especie.

### Contraste con las tablas oficiales

| Valor aportado por el agrónomo | Resultado |
|---|---|
| Trigo: Kc ini 0,7 (suelos no congelados), mid 1,15, end 0,25 (cosecha mecánica); Zr 1,5–1,8 | Coincide con T12 (0,7 es el valor «with non-frozen soils») y T22 |
| Soja: Kc mid 1,15, end 0,50; Zr 0,6–1,3 | Coincide con T12 y T22 |
| Soja: duraciones 15–20 / 15–35 / 40–75 / 15–30 | Coincide con el rango de las filas de T11 (Trópicos, centro de EE. UU. y Japón) |
| Maíz: Kc mid 1,20, end 0,35 (cosecha seca); Zr 1,0–1,7; etapas 25/40/45/30 para clima árido | Coincide con T12 (nota 11), T22 y la fila «Arid Climate» de T11 |
| Maíz y centeno: Kc ini del grupo Cereales (0,3) | Coincide con T12 |
| Soja: Kc ini del grupo Leguminosas (0,4) | **No verificado en la lectura automática**; confirmar en la tabla impresa |
| Zr inicial 0,2–0,3 m como decisión del equipo | Correcto no citar T22: esa página no contiene ninguna guía de Zr inicial |

### Elecciones marcadas con ⚑ (aprobadas por Mauro el 2026-11-15)

Son decisiones tomadas para que el catálogo no quede vacío. Cada una es corregible en una línea del JSON.

1. **Duraciones del trigo** (20/60/70/30, California, diciembre) y **de la soja de primera** (20/35/60/25, centro de EE. UU.): elegí filas de T11 por clima sin congelamiento. Tú aportaste solo rangos para la soja y nada para el trigo.
2. **Zr máxima de trigo, soja y centeno:** usé el extremo inferior de cada rango de T22. La nota 1 de T22 indica que los valores mayores corresponden a modelar estrés hídrico en secano.
3. **Zr inicial:** 0,25 m (punto medio de tu rango de 0,2–0,3 m), igual para los cinco cultivos.
4. **Ky del trigo de invierno:** T24 da 1,05, mientras que otra publicación de la FAO sobre riego deficitario lista 1,00. Usé T24 por ser la tabla citada.
5. **Valores de p y Ky:** los tomé de T22 y T24 porque no los incluiste; son los de cada cultivo en la tabla.
6. **Kc final del centeno** (0,25, de cebada/avena): un centeno terminado antes de la madurez quizás no llegue a ese valor.

### Cierre de la tarea

- Celdas: 40 (5 cultivos × 8 parámetros). Ninguna vacía: 37 con valor y cita, 2 «sin referencia» (duraciones de `soybean_second` y de `rye_cover`) y 1 «no aplica» (Ky de `rye_cover`).
- Revisado por: **Mauro**, 2026-11-15. Aprobó las elecciones ⚑ y el ajuste de la Zr inicial a 0,25 m el mismo día.
- Catálogo cargado y cotejado: la carga y las pruebas llegan con T031.

## V-3 Ejemplos FAO-56

Sin empezar (tarea T003).

## Prueba en vivo

Sin empezar (tarea T050).
