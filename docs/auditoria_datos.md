# Auditoria de `departamentos_biobio.csv`

Generado el 2026-11-26 con `src/auditar_dataset.py`. Las revisiones no modifican los datos: marcan lo que hay que limpiar antes de modelar.

## Estructura

- Filas: **2386**, columnas: **64** (esperadas 64).
- Columnas faltantes: ninguna; columnas sobrantes: ninguna.
- `id_aviso` duplicados: **0**; filas sin id o url: **0**.

## Cobertura respecto del indice de URLs

- Avisos en el indice de URLs (`*_urls.csv`): **2795**.
- Con ficha en el dataset: **2386** (85.4%).
- Descartados (aviso finalizado o sin datos): **409** (14.6%).
- Pendientes (ni ficha ni descartado): **0**.
- Filas del dataset que no estan en el indice: **0**.
- Fichas por fecha de extraccion: 2026-11-10: 156, 2026-11-11: 250, 2026-11-26: 1980.

## Tipos de datos

- Todas las columnas numericas son numericas, las 1/0 solo tienen 1, 0 o vacio, y `otras_caracteristicas` es JSON valido en todas las filas.
- Monedas: {'UF': 1774, 'CLP': 612}.

## Completitud por columna

| Columna | Con dato | % |
|---|---:|---:|
| `id_aviso` | 2386 | 100.0% |
| `url` | 2386 | 100.0% |
| `titulo` | 2386 | 100.0% |
| `precio` | 2386 | 100.0% |
| `moneda` | 2386 | 100.0% |
| `precio_uf` | 2386 | 100.0% |
| `superficie_total_m2` | 2332 | 97.7% |
| `superficie_util_m2` | 2339 | 98.0% |
| `superficie_terraza_m2` | 1348 | 56.5% |
| `ambientes` | 1133 | 47.5% |
| `dormitorios` | 2386 | 100.0% |
| `banos` | 2386 | 100.0% |
| `estacionamientos` | 2385 | 100.0% |
| `bodegas` | 2244 | 94.0% |
| `piso` | 1809 | 75.8% |
| `pisos_edificio` | 1713 | 71.8% |
| `deptos_por_piso` | 1415 | 59.3% |
| `tipo_departamento` | 2115 | 88.6% |
| `orientacion_raw` | 1922 | 80.6% |
| `orientacion` | 1922 | 80.6% |
| `orient_norte` | 1922 | 80.6% |
| `orient_sur` | 1922 | 80.6% |
| `orient_oriente` | 1922 | 80.6% |
| `orient_poniente` | 1922 | 80.6% |
| `antiguedad_anios` | 1996 | 83.7% |
| `gastos_comunes_clp` | 1717 | 72.0% |
| `agua_corriente` | 1446 | 60.6% |
| `gas_natural` | 1873 | 78.5% |
| `aire_acondicionado` | 1762 | 73.8% |
| `calefaccion` | 1955 | 81.9% |
| `conexion_lavarropas` | 1835 | 76.9% |
| `ascensor` | 2129 | 89.2% |
| `lavanderia` | 1850 | 77.5% |
| `piscina` | 2030 | 85.1% |
| `gimnasio` | 947 | 39.7% |
| `quincho` | 0 | 0.0% |
| `parrilla` | 718 | 30.1% |
| `jardin` | 633 | 26.5% |
| `salon_usos_multiples` | 1137 | 47.7% |
| `estacionamiento_visitas` | 879 | 36.8% |
| `juegos_infantiles` | 672 | 28.2% |
| `tipo_seguridad` | 1275 | 53.4% |
| `conserjeria` | 2241 | 93.9% |
| `closets` | 1526 | 64.0% |
| `terraza` | 2117 | 88.7% |
| `comedor` | 2140 | 89.7% |
| `living` | 2182 | 91.5% |
| `dormitorio_suite` | 2056 | 86.2% |
| `balcon` | 2156 | 90.4% |
| `cocina` | 2237 | 93.8% |
| `logia` | 1001 | 42.0% |
| `bano_visitas` | 643 | 26.9% |
| `amoblado` | 173 | 7.3% |
| `admite_mascotas` | 1942 | 81.4% |
| `otras_caracteristicas` | 2188 | 91.7% |
| `direccion` | 2386 | 100.0% |
| `barrio` | 2323 | 97.4% |
| `comuna` | 2386 | 100.0% |
| `comuna_busqueda` | 2338 | 98.0% |
| `region` | 2386 | 100.0% |
| `latitud` | 2386 | 100.0% |
| `longitud` | 2386 | 100.0% |
| `uf_usada` | 2386 | 100.0% |
| `fecha_scraping` | 2386 | 100.0% |

Columnas vacias en todas las filas: `quincho`. Si la etiqueta tampoco aparece en `otras_caracteristicas`, el sitio no la publica (no es un error del scraper).

## Caracteristicas extra mas frecuentes (`otras_caracteristicas`)

- En condominio cerrado: 1376 avisos (57.7%)
- Recepción: 1373 avisos (57.5%)
- Acceso a internet: 1202 avisos (50.4%)
- Con área verde: 1003 avisos (42.0%)
- Salón de fiestas: 953 avisos (39.9%)
- Rampa para silla de ruedas: 818 avisos (34.3%)
- Número de torre: 762 avisos (31.9%)
- Línea telefónica: 713 avisos (29.9%)
- Walk-in clóset: 623 avisos (26.1%)
- Comedor de diario: 506 avisos (21.2%)
- Caldera: 480 avisos (20.1%)
- Piso: 432 avisos (18.1%)
- Generador eléctrico: 352 avisos (14.8%)
- Cowork: 281 avisos (11.8%)
- Refrigerador: 266 avisos (11.1%)
- Homeoffice: 262 avisos (11.0%)
- Patio: 253 avisos (10.6%)
- Azotea: 217 avisos (9.1%)
- Dormitorio y baño de servicio: 160 avisos (6.7%)
- Canchas de usos múltiples: 118 avisos (4.9%)
- Playroom: 114 avisos (4.8%)
- Sauna: 81 avisos (3.4%)
- Jacuzzi: 73 avisos (3.1%)
- Uso comercial: 71 avisos (3.0%)
- Cisterna: 70 avisos (2.9%)

## Rangos y coherencia

| Revision | Filas | % |
|---|---:|---:|
| Sin `precio_uf` (variable objetivo) | 0 | 0.0% |
| `precio_uf` fuera de 300 a 60.000 UF | 0 | 0.0% |
| Moneda UF pero `precio_uf` distinto de `precio` | 0 | 0.0% |
| Moneda CLP pero `precio_uf` distinto de `precio / uf_usada` | 0 | 0.0% |
| Sin superficie util ni total | 15 | 0.6% |
| Superficie fuera de 15 a 600 m2 | 19 | 0.8% |
| Superficie util o total menor o igual a 0 | 2 | 0.1% |
| Bodegas fuera de 0 a 10 | 10 | 0.4% |
| Estacionamientos fuera de 0 a 10 | 2 | 0.1% |
| Superficie total mayor que 3 veces la util | 7 | 0.3% |
| Superficie util mayor que la total | 36 | 1.5% |
| Dormitorios fuera de 0 a 8 | 4 | 0.2% |
| Banos fuera de 1 a 8 | 8 | 0.3% |
| `piso` mayor que `pisos_edificio` | 104 | 4.4% |
| `piso` fuera de -3 a 40 | 15 | 0.6% |
| Antiguedad fuera de 0 a 100 anios | 50 | 2.1% |
| Gastos comunes iguales al precio (error de tipeo) | 3 | 0.1% |
| Gastos comunes fuera de 0 a $1.000.000 | 4 | 0.2% |
| Sin coordenadas | 0 | 0.0% |
| Coordenadas fuera de la Region del Biobio | 0 | 0.0% |
| `comuna` distinta de `comuna_busqueda` (aviso destacado de otra comuna) | 0 | 0.0% |
| Banderas `orient_*` no calzan con `orientacion_raw` | 0 | 0.0% |

## Duplicados probables

- 243 filas (10.2%) en 114 grupos comparten coordenadas, superficie util, piso, dormitorios y banos: probablemente el mismo departamento publicado por varios corredores. No se borran; decidir al limpiar.

## Estadisticos descriptivos

| Variable | n | media | p5 | mediana | p95 | min | max |
|---|---:|---:|---:|---:|---:|---:|---:|
| `precio_uf` | 2386 | 4,252.4 | 1,750.0 | 3,300.0 | 10,000.0 | 724.4 | 58,919.6 |
| `superficie_util_m2` | 2339 | 86.7 | 32.0 | 60.0 | 140.0 | 1.0 | 6,450.0 |
| `superficie_total_m2` | 2332 | 93.3 | 33.0 | 63.0 | 156.4 | -3.0 | 6,470.0 |
| `dormitorios` | 2386 | 2.4 | 1.0 | 2.0 | 4.0 | 0.0 | 51.0 |
| `banos` | 2386 | 1.8 | 1.0 | 2.0 | 3.0 | 0.0 | 55.0 |
| `estacionamientos` | 2385 | 0.9 | 0.0 | 1.0 | 2.0 | 0.0 | 44.0 |
| `bodegas` | 2244 | 647.8 | 0.0 | 0.0 | 1.0 | -54.0 | 242,085.0 |
| `piso` | 1809 | 9.0 | 1.0 | 4.0 | 17.0 | 0.0 | 2,385.0 |
| `pisos_edificio` | 1713 | 9.6 | 1.0 | 8.0 | 21.0 | 1.0 | 39.0 |
| `antiguedad_anios` | 1996 | 60.7 | 0.0 | 10.0 | 49.0 | 0.0 | 2,027.0 |
| `gastos_comunes_clp` | 1717 | 266,379.0 | 0.0 | 70,000.0 | 216,000.0 | 0.0 | 90,000,000.0 |

UF/m2 util: mediana 58.6, p5 31.7, p95 87.5.

| Comuna | Avisos | Mediana UF/m2 |
|---|---:|---:|
| Concepción | 1267 | 60.6 |
| San Pedro De La Paz | 566 | 59.6 |
| Chiguayante | 191 | 60.0 |
| Los Ángeles | 183 | 44.0 |
| Talcahuano | 70 | 44.7 |
| Hualpén | 46 | 35.4 |
| Tomé | 44 | 52.5 |
| Penco | 15 | 35.9 |
| Coronel | 4 | 19.7 |
