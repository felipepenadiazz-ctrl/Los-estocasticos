# Los Estocásticos — Precio justo de departamentos

Proyecto del curso **Machine Learning y Business Intelligence**.

## Problema

Quien busca comprar un departamento usado no tiene una forma simple de saber si el precio publicado es razonable para lo que ofrece, ni cuánto le costaría reparar los problemas que encuentra en la visita.

## Pregunta

¿Se puede estimar el precio de mercado de un departamento a partir de sus características (superficie, dormitorios, baños, piso, orientación, ubicación y equipamiento) y usar esa estimación para decir si un aviso está bajo, dentro o sobre un precio justo?

## Solución propuesta

Una aplicación donde la persona ingresa las características de un departamento y obtiene:

1. **Precio estimado** con un modelo de machine learning entrenado con avisos reales, comparado con el precio pedido.
2. **Descuento por reparaciones:** un modelo de detección de objetos identifica fallas en fotos del departamento (grietas, humedad, moho, pintura dañada, etc.), estima el costo de repararlas y lo descuenta del precio estimado.

## Etapas

| Etapa | Estado |
|---|---|
| 1. Extracción de datos (scraping) — Región del Biobío | En curso |
| 2. Limpieza y análisis exploratorio | Pendiente |
| 3. Modelo de predicción de precios | Pendiente |
| 4. Modelo de detección de fallas | Pendiente |
| 5. Prototipo de la aplicación (MVP) | Pendiente |
| 6. Ampliar los datos al resto de Chile | Pendiente |

## Datos

- **Fuente:** avisos de departamentos usados en venta publicados en [Portal Inmobiliario](https://www.portalinmobiliario.com).
- **Alcance actual:** Región del Biobío, 9 comunas (Concepción, San Pedro de la Paz, Chiguayante, Los Ángeles, Talcahuano, Hualpén, Tomé, Penco y Coronel).
- **Tamaño:** 2.185 avisos encontrados el 10-11-2026; la extracción de sus fichas sigue en curso.
- **Variables:** precio (en UF), superficies, dormitorios, baños, piso, orientación, antigüedad, gastos comunes, servicios, equipamiento, seguridad, ambientes, dirección, comuna y coordenadas. El detalle está en [`data/README.md`](data/README.md).

## Extracción y transformación (ETL)

**Extracción** (`src/scraper_portalinmobiliario.py`, detalle en [`docs/scraper.md`](docs/scraper.md)):

1. Recorre los resultados de búsqueda de cada comuna y guarda el link de cada aviso. Se busca por comuna porque el sitio muestra como máximo 42 páginas (~2.016 avisos) por búsqueda.
2. Entra a la ficha de cada aviso y lee todas sus tablas de características, el recuadro de destacados y las coordenadas del mapa.
3. Respeta `robots.txt`, deja de 3 a 7 segundos entre páginas y no descarga imágenes.

**Transformación:**

- Precios en pesos convertidos a UF con el valor del día de extracción (fuente: mindicador.cl).
- Características Sí/No convertidas a 1/0, y vacías cuando el aviso no las informa.
- Orientación: el código del sitio (N, S, O = Oriente, P = Poniente y combinaciones como `NOSP`) se traduce y se separa en cuatro variables 0/1 (norte, sur, oriente, poniente).
- Comuna y barrio obtenidos desde el texto de ubicación del aviso.
- Características poco frecuentes guardadas en una columna JSON (`otras_caracteristicas`).

**Carga:** CSV en `data/raw/`, escrito de forma incremental (se puede detener y retomar).

**Supuestos y limitaciones:**

- Son precios **publicados** (lo que pide el vendedor), no precios de venta efectivos.
- Los avisos los escriben corredores y particulares: hay errores de tipeo que se deben limpiar (por ejemplo, gastos comunes iguales al precio o superficies imposibles).
- Un mismo departamento puede estar publicado por varios corredores.
- Se excluyen los proyectos nuevos, porque publican rangos de precio y no un departamento específico.
- Los datos corresponden a la fecha de extracción (`fecha_scraping`).
- Los avisos destacados pueden ser de otra comuna; `comuna` dice la del aviso y `comuna_busqueda` la buscada.

## Estructura del repositorio

```
├── data/
│   ├── raw/              # datos extraídos, sin modificar
│   └── README.md         # diccionario de datos
├── docs/
│   └── scraper.md        # guía del scraper
├── notebooks/
│   └── 01_scraping_biobio.ipynb
├── src/
│   └── scraper_portalinmobiliario.py
├── requirements.txt
└── README.md
```

## Cómo ejecutar

```bash
pip install -r requirements.txt
python -m playwright install chromium
```

Luego abre `notebooks/01_scraping_biobio.ipynb` en VS Code o Jupyter y ejecuta las celdas en orden.

## Uso de los datos

Portal Inmobiliario prohíbe reproducir su contenido. Los datos se usan solo con fines académicos en este curso y el repositorio debe mantenerse **privado** si incluye `data/raw/`.

## Forma de trabajo

- `main` es la versión estable. Los cambios se hacen en ramas (`feat/...`, `fix/...`, `docs/...`) y se integran a `main` con un Pull Request.
- Mensajes de commit con el formato `tipo(alcance): qué se hizo`, por ejemplo `feat(scraping): ...`, `fix: ...`, `docs: ...`, `data: ...`.
- Las tareas se registran como issues en GitHub y se cierran indicando el commit o la rama que las resolvió.
