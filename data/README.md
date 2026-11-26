# Diccionario de datos

## Archivos en `data/raw/`

| Archivo | Contenido |
|---|---|
| `departamentos_biobio.csv` | Dataset principal: una fila por departamento, con todas las características de su ficha. 2.386 departamentos: 406 extraídos el 10 y 11 de noviembre de 2026 y 1.980 el 26 de noviembre de 2026. |
| `departamentos_biobio_urls.csv` | Índice de avisos encontrados en los listados (etapa 1), 2.795 avisos. Solo trae datos básicos: precio, dormitorios, baños, superficie útil y ubicación. Los 409 que no tienen ficha estaban finalizados al visitarlos. |
| `departamentos_biobio_descartados.txt` | Avisos finalizados o sin datos, que no se vuelven a visitar (no se versiona). |

Para cargar el dataset con pandas, con `otras_caracteristicas` separada en columnas `extra_*`:

```python
import sys
sys.path.insert(0, "../src")
import scraper_portalinmobiliario as sc
df = sc.cargar_dataset("../data/raw/departamentos_biobio.csv")
```

## Columnas de `departamentos_biobio.csv`

Las columnas Sí/No vienen como **1/0**, y vacías cuando el aviso no informa el dato.

### Identificación

| Columna | Descripción |
|---|---|
| `id_aviso` | Código del aviso en Portal Inmobiliario (ej. `MLC4084848924`). |
| `url` | Link a la ficha. |
| `titulo` | Título del aviso. |
| `fecha_scraping` | Fecha de extracción (AAAA-MM-DD). |

### Precio

| Columna | Descripción |
|---|---|
| `precio` | Precio publicado, en la moneda original. |
| `moneda` | `UF`, `CLP` o `USD`. |
| `precio_uf` | Precio en UF. Los avisos en pesos se convierten con `uf_usada`. **Variable objetivo del modelo.** |
| `uf_usada` | Valor de la UF el día de extracción (mindicador.cl). |

### Características principales

| Columna | Descripción |
|---|---|
| `superficie_total_m2` | Superficie total (m²). |
| `superficie_util_m2` | Superficie útil (m²). |
| `superficie_terraza_m2` | Superficie de terraza (m²). |
| `ambientes` | Ambientes según el aviso (habitaciones). |
| `dormitorios` | Número de dormitorios. |
| `banos` | Número de baños. |
| `estacionamientos` | Número de estacionamientos. |
| `bodegas` | Número de bodegas. |
| `piso` | Piso en que está el departamento. |
| `pisos_edificio` | Pisos del edificio. |
| `deptos_por_piso` | Departamentos por piso. |
| `tipo_departamento` | Texto (ej. "Departamento", "Dúplex"). |
| `antiguedad_anios` | Años de antigüedad (0 = a estrenar). |
| `gastos_comunes_clp` | Gastos comunes mensuales en pesos. |

### Orientación

| Columna | Descripción |
|---|---|
| `orientacion_raw` | Código del sitio: N, S, O (Oriente), P (Poniente), NO, NP, SO, SP o combinaciones (`NOSP`). |
| `orientacion` | Texto traducido (ej. "Nororiente-Surponiente"). |
| `orient_norte`, `orient_sur`, `orient_oriente`, `orient_poniente` | 1 si el departamento tiene vista hacia ese punto cardinal. |

### Servicios, equipamiento, seguridad y ambientes (1/0)

| Grupo | Columnas |
|---|---|
| Servicios | `agua_corriente`, `gas_natural`, `aire_acondicionado`, `calefaccion`, `conexion_lavarropas` |
| Comodidades | `ascensor`, `lavanderia`, `piscina`, `gimnasio`, `quincho`, `parrilla`, `jardin`, `salon_usos_multiples`, `estacionamiento_visitas`, `juegos_infantiles` |
| Seguridad | `conserjeria` (1/0) y `tipo_seguridad` (texto, ej. "24 horas") |
| Ambientes | `closets`, `terraza`, `comedor`, `living`, `dormitorio_suite`, `balcon`, `cocina`, `logia`, `bano_visitas` |
| Condiciones | `amoblado`, `admite_mascotas` |
| Otras | `otras_caracteristicas`: JSON con cualquier otra característica del aviso (ej. `{"En condominio cerrado": "Sí", "Caldera": "Sí"}`) |

### Ubicación

| Columna | Descripción |
|---|---|
| `direccion` | Dirección publicada. |
| `barrio` | Barrio o sector, según el aviso. |
| `comuna` | Comuna según el aviso. |
| `comuna_busqueda` | Comuna usada en la búsqueda. Si es distinta de `comuna`, el sitio mostró un aviso destacado de otra comuna. |
| `region` | Región buscada (`biobio`). |
| `latitud`, `longitud` | Coordenadas del mapa del aviso. |

## Problemas conocidos (limpiar antes de modelar)

La auditoría completa está en `docs/auditoria_datos.md` y el detalle por aviso en `docs/auditoria_problemas.csv` (se regeneran con `src/auditar_dataset.py`).

- Errores de tipeo: gastos comunes iguales al precio, superficie total muchas veces mayor que la útil, pisos imposibles (mayores que `pisos_edificio`), antigüedad escrita como año (ej. 2015), bodegas o estacionamientos imposibles (ej. 242085 bodegas), 0 baños.
- `quincho` viene vacía en todas las filas: el sitio no publica esa etiqueta (usar `parrilla`).
- Las fichas de distintas fechas usan la UF de su día (`uf_usada`) para convertir los precios en pesos.
- Duplicados: un departamento publicado por varios corredores (comparar coordenadas, superficie, piso y precio).
- Valores faltantes: no todos los avisos informan todas las características.
