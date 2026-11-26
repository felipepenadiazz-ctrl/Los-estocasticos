# Guía del scraper

`src/scraper_portalinmobiliario.py` extrae departamentos en venta de Portal Inmobiliario y los guarda en `data/raw/`.

## Instalación (una vez)

Requiere Python 3.10 o superior. Desde la raíz del repositorio:

```bash
pip install -r requirements.txt
python -m playwright install chromium
```

En Jupyter o VS Code también se puede instalar desde una celda:

```python
%pip install -r ../requirements.txt
import sys
!{sys.executable} -m playwright install chromium
```

Si después aparece `No module named ...`, reinicia el kernel.

## Uso

Lo más simple es el notebook `notebooks/01_scraping_biobio.ipynb`. Desde código:

```python
import sys
sys.path.insert(0, "../src")
import scraper_portalinmobiliario as sc

sc.main("--max-paginas 1 --max-avisos 10 --salida ../data/raw/departamentos_biobio.csv")
```

O desde una terminal en la raíz del repositorio:

```bash
python src/scraper_portalinmobiliario.py --comunas "concepcion,san pedro de la paz" --salida data/raw/departamentos_biobio.csv
```

| Opción | Para qué sirve |
|---|---|
| `--region` | Región tal como aparece en la URL del sitio (por defecto `biobio`; ej. `metropolitana`). |
| `--comunas` | Lista de comunas separadas por coma. Recomendado: el sitio muestra máximo 42 páginas por búsqueda. |
| `--url` | URL de búsqueda copiada del navegador. |
| `--condicion` | `usadas` (por defecto), `nuevas` o `todas`. |
| `--max-paginas` / `--max-avisos` | Limitar el tamaño de la corrida. |
| `--solo-fichas` | Saltarse los listados y seguir solo con las fichas pendientes. |
| `--incluir-proyectos` | Incluir proyectos nuevos (por defecto se omiten). |
| `--uf` | Valor de la UF a mano, si no se puede descargar de mindicador.cl. |
| `--headless` | Correr sin ventana (más propenso a bloqueos). |
| `--desatendido` | Para dejarlo corriendo solo: ante una verificación no espera a que una persona la resuelva; hace pausas largas (3, 6 y 9 minutos) y reintenta. |
| `--salida` | Ruta del CSV (por defecto `departamentos_biobio.csv`). |

## Cómo funciona

1. **Listados:** recorre las páginas de resultados de cada búsqueda y guarda el link y los datos básicos de cada aviso en `<salida>_urls.csv`. Las URLs de las páginas siguientes se leen desde el JSON que trae la página, porque los botones de paginación del sitio vienen sin link.
2. **Fichas:** visita cada aviso pendiente y guarda una fila en `<salida>.csv`, con todas las características de la ficha (ver `data/README.md`). Los avisos finalizados quedan en `<salida>_descartados.txt`.

Un aviso finalizado no siempre muestra "Publicación finalizada": a veces el sitio redirige a un listado de Mercado Libre, a menudo detrás de su página de verificación, con `#redirectedFromVip=` en la URL. El scraper reconoce esa redirección (función `redirigio_fuera`) y descarta el aviso en vez de tratarlo como bloqueo. Las fichas normales cargan el script de reCAPTCHA, así que la palabra "captcha" sola no se usa como señal de bloqueo.

Para completar las fichas de un índice de URLs ya existente, y sumar los avisos publicados desde entonces:

```bash
python src/scraper_portalinmobiliario.py --comunas "concepcion,san pedro de la paz,chiguayante,los angeles,talcahuano,hualpen,tome,penco,coronel" --solo-urls --salida data/raw/departamentos_biobio.csv
python src/scraper_portalinmobiliario.py --solo-fichas --desatendido --salida data/raw/departamentos_biobio.csv
```

El valor de la UF se toma de mindicador.cl y, si no responde, de boostr.cl.

## Auditoría de los datos

`src/auditar_dataset.py` revisa el CSV (estructura, cobertura respecto del índice, completitud, tipos, rangos, coherencia entre columnas y duplicados probables) y escribe `docs/auditoria_datos.md`:

```bash
python src/auditar_dataset.py --datos data/raw/departamentos_biobio.csv --reporte docs/auditoria_datos.md
```

Todo se guarda a medida que avanza. Si se corta o se detiene (botón Stop en Jupyter o Ctrl+C), al volver a correr lo mismo sigue donde quedó. Si el CSV tiene columnas de una versión anterior del script, se renombra a `..._anterior_<fecha>.csv` y esos avisos se vuelven a visitar.

## Tiempos

Con pausas de 3 a 7 segundos entre páginas, se procesan unos 6 a 7 avisos por minuto: el Biobío completo (~2.200 avisos) toma entre 5 y 6 horas. No suspendas el PC mientras corre.

## Si algo falla

- **Verificación "no soy un robot":** resuélvela en la ventana del navegador; el scraper sigue solo apenas carga la página (espera hasta 5 minutos por intento). Si nadie la resuelve, se detiene con el avance guardado. Corre el script desde una red doméstica, sin VPN.
- **`PermissionError`:** el CSV está abierto en Excel. Ciérralo y vuelve a correr.
- **Una columna sale vacía en todas las filas:** el sitio cambió su HTML. Revisar `parsear_listado`, `extraer_caracteristicas`, `extraer_precio` y `extraer_coordenadas`.
- **No funciona en Google Colab:** no hay ventana de navegador y el sitio bloquea las IPs de Google.

## Uso responsable

El script revisa `robots.txt` y se salta lo no permitido, deja pausas entre páginas, no descarga imágenes y no guarda datos personales (nombre o teléfono del corredor, descripciones).
