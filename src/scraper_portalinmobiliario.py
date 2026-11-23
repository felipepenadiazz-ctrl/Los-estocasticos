#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Scraper de departamentos en venta - Portal Inmobiliario (Chile)
Proyecto: modelo de prediccion de precios (curso de Machine Learning y BI)

Funciona en dos etapas:
  1) Recorre las paginas de resultados y guarda el link de cada aviso.
  2) Entra a la ficha de cada aviso y extrae sus caracteristicas.

Todo se guarda en CSV de forma incremental: si se corta, vuelves a correr
el mismo comando y continua donde quedo (no repite avisos ya guardados).

No guarda datos personales: ni nombre/telefono del corredor ni descripciones.

Ejemplos (terminal):
  python scraper_portalinmobiliario.py --region biobio --max-paginas 1 --max-avisos 10
  python scraper_portalinmobiliario.py --region biobio --comunas "concepcion,talcahuano,san pedro de la paz"
  python scraper_portalinmobiliario.py --url "https://www.portalinmobiliario.com/venta/departamento/propiedades-usadas/biobio"

Ejemplo (Jupyter, con este archivo en la misma carpeta del notebook):
  import scraper_portalinmobiliario as sc
  sc.main("--max-paginas 1 --max-avisos 10")
"""
from __future__ import annotations

import argparse
import asyncio
import contextlib
import csv
import json
import os
import random
import re
import shlex
import sys
import threading
import time
import unicodedata
import urllib.request
import warnings
from datetime import datetime
from urllib.parse import urljoin, urlparse

try:
    from bs4 import BeautifulSoup
except ImportError:
    raise ImportError(
        "Falta la libreria beautifulsoup4. Instalala asi:\n"
        "  En una terminal:     pip install -r requirements.txt\n"
        "  En Jupyter (celda):  %pip install beautifulsoup4 lxml playwright\n"
        "Si estas en Jupyter y el error sigue despues de instalar, reinicia el kernel."
    ) from None

try:
    import lxml  # noqa: F401  (parser mas rapido, opcional)
    PARSER = "lxml"
except ImportError:
    PARSER = "html.parser"

BASE = "https://www.portalinmobiliario.com"
AVISOS_POR_PAGINA = 48

# Columnas del CSV final (una fila por departamento)
COLUMNAS = [
    "id_aviso", "url", "titulo",
    "precio", "moneda", "precio_uf",
    "superficie_total_m2", "superficie_util_m2", "superficie_terraza_m2",
    "ambientes", "dormitorios", "banos", "estacionamientos", "bodegas",
    "piso", "pisos_edificio", "deptos_por_piso", "tipo_departamento",
    "orientacion_raw", "orientacion",
    "orient_norte", "orient_sur", "orient_oriente", "orient_poniente",
    "antiguedad_anios", "gastos_comunes_clp",
    # Servicios
    "agua_corriente", "gas_natural", "aire_acondicionado", "calefaccion", "conexion_lavarropas",
    # Comodidades y equipamiento
    "ascensor", "lavanderia", "piscina", "gimnasio", "quincho", "parrilla", "jardin",
    "salon_usos_multiples", "estacionamiento_visitas", "juegos_infantiles",
    # Seguridad
    "tipo_seguridad", "conserjeria",
    # Ambientes
    "closets", "terraza", "comedor", "living", "dormitorio_suite", "balcon", "cocina", "logia",
    "bano_visitas",
    # Condiciones especiales
    "amoblado", "admite_mascotas",
    # Cualquier otra caracteristica de la ficha, como JSON {"Etiqueta": "valor"}
    "otras_caracteristicas",
    "direccion", "barrio", "comuna", "comuna_busqueda", "region",
    "latitud", "longitud",
    "uf_usada", "fecha_scraping",
]

# Columnas del CSV intermedio de links (etapa 1)
COLUMNAS_URLS = [
    "id_aviso", "url", "titulo", "precio", "moneda", "ubicacion",
    "dormitorios", "banos", "superficie_util_m2", "superficie_total_m2",
    "region", "comuna_busqueda",
]

# Etiqueta en la ficha (normalizada, sin tildes y sin "Con " inicial) -> columna del CSV
ETIQUETAS = {
    # Principales
    "superficie total": "superficie_total_m2",
    "superficie util": "superficie_util_m2",
    "superficie de terraza": "superficie_terraza_m2",
    "ambientes": "ambientes",
    "dormitorios": "dormitorios",
    "banos": "banos",
    "estacionamientos": "estacionamientos",
    "bodegas": "bodegas",
    "numero de piso de la unidad": "piso",
    "cantidad de pisos": "pisos_edificio",
    "departamentos por piso": "deptos_por_piso",
    "tipo de departamento": "tipo_departamento",
    "orientacion": "orientacion_raw",
    "antiguedad": "antiguedad_anios",
    "gastos comunes": "gastos_comunes_clp",
    # Servicios
    "agua corriente": "agua_corriente",
    "gas natural": "gas_natural",
    "aire acondicionado": "aire_acondicionado",
    "calefaccion": "calefaccion",
    "conexion para lavarropas": "conexion_lavarropas",
    # Comodidades y equipamiento
    "ascensor": "ascensor",
    "lavanderia": "lavanderia",
    "piscina": "piscina",
    "gimnasio": "gimnasio",
    "quincho": "quincho",
    "parrilla": "parrilla",
    "jardin": "jardin",
    "salon de usos multiples": "salon_usos_multiples",
    "estacionamiento de visitas": "estacionamiento_visitas",
    "estacionamiento para visitas": "estacionamiento_visitas",
    "area de juegos infantiles": "juegos_infantiles",
    # Seguridad
    "tipo de seguridad": "tipo_seguridad",
    "conserjeria": "conserjeria",
    # Ambientes
    "closets": "closets",
    "terraza": "terraza",
    "comedor": "comedor",
    "living": "living",
    "dormitorio en suite": "dormitorio_suite",
    "balcon": "balcon",
    "cocina": "cocina",
    "logia": "logia",
    "bano de visitas": "bano_visitas",
    # Condiciones especiales
    "amoblado": "amoblado",
    "admite mascotas": "admite_mascotas",
}
CAMPOS_TEXTO = {"orientacion_raw", "tipo_departamento", "tipo_seguridad"}
CAMPOS_NUMERICOS = {
    "superficie_total_m2", "superficie_util_m2", "superficie_terraza_m2", "ambientes",
    "dormitorios", "banos", "estacionamientos", "bodegas", "piso", "pisos_edificio",
    "deptos_por_piso", "antiguedad_anios", "gastos_comunes_clp",
}
CAMPOS_BOOLEANOS = set(ETIQUETAS.values()) - CAMPOS_TEXTO - CAMPOS_NUMERICOS  # Si/No -> 1/0

# En Chile la orientacion se abrevia con O = Oriente y P = Poniente.
# Un depto puede tener varias: "NOSP" = Nororiente + Surponiente.
PUNTOS_CARDINALES = {
    "N": "Norte", "S": "Sur", "O": "Oriente", "P": "Poniente",
    "NO": "Nororiente", "NP": "Norponiente", "SO": "Suroriente", "SP": "Surponiente",
}

# Nombres de regiones (normalizados) que a veces aparecen al final de la direccion
REGIONES = {
    "arica y parinacota", "tarapaca", "antofagasta", "atacama", "coquimbo", "valparaiso",
    "metropolitana", "metropolitana de santiago", "rm", "ohiggins",
    "libertador general bernardo ohiggins", "maule", "nuble", "biobio", "bio bio",
    "araucania", "la araucania", "los rios", "los lagos", "aysen",
    "aysen del general carlos ibanez del campo", "magallanes",
    "magallanes y la antartica chilena", "magallanes y antartica chilena", "chile",
}

# El sitio muestra como maximo 42 paginas (unos 2.016 avisos) por busqueda
MAX_PAGINAS_SITIO = 42

# Senales de pagina de verificacion/bloqueo (solo se usan si falta el contenido esperado)
SENALES_BLOQUEO = (
    "captcha", "account-verification", "verifica que eres", "no eres un robot",
    "acceso denegado", "access denied", "too many requests",
)


class Bloqueado(Exception):
    """El sitio sigue mostrando verificacion o bloqueo despues de varios intentos."""


# Se activa al interrumpir (boton Stop en Jupyter o Ctrl+C): el scraper termina la pagina
# actual, guarda y cierra el navegador.
DETENER = threading.Event()


# --------------------------------------------------------------------------
# Utilidades de texto y numeros
# --------------------------------------------------------------------------
def normalizar(texto: str) -> str:
    """minusculas, sin tildes, espacios simples y sin ':' al final."""
    t = unicodedata.normalize("NFKD", str(texto)).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"\s+", " ", t).strip().strip(":").strip().lower()


def slug(texto: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", normalizar(texto)).strip("-")


_RE_MILES = re.compile(r"-?\d{1,3}(?:\.\d{3})+(?:,\d+)?")
_RE_NUM = re.compile(r"-?\d{1,3}(?:\.\d{3})+(?:,\d+)?|-?\d+(?:[.,]\d+)?")


def a_numero(valor):
    """'2.170' -> 2170 | '50,5 m²' -> 50.5 | '110.000 CLP' -> 110000 | 'A estrenar' -> 0"""
    if valor is None:
        return None
    if isinstance(valor, (int, float)):
        return valor
    t = str(valor).replace("\xa0", " ").strip()
    if not t:
        return None
    if normalizar(t) in ("a estrenar", "nuevo", "en construccion"):
        return 0
    m = _RE_NUM.search(t)
    if not m:
        return None
    s = m.group(0)
    if _RE_MILES.fullmatch(s):
        s = s.replace(".", "").replace(",", ".")
    else:
        s = s.replace(",", ".")
    v = float(s)
    return int(v) if v.is_integer() else v


def a_booleano(valor):
    """'Si' -> 1 | 'No' -> 0 | vacio -> None | otro texto (ej. 'Central') -> 1 (lo tiene)."""
    n = normalizar(valor or "")
    if n in ("si", "s", "yes", "true", "1"):
        return 1
    if n in ("no", "n", "false", "0", "ninguno", "ninguna", "sin"):
        return 0
    if n in ("", "-", "--", "n/a", "na", "sin informacion"):
        return None
    return 1


def clave_etiqueta(etiqueta: str) -> str:
    """'Con conexión para lavarropas:' -> 'conexion para lavarropas'"""
    return re.sub(r"^(con|tiene)\s+", "", normalizar(etiqueta))


def descomponer_orientacion(valor):
    """'NOSP' -> ('Nororiente-Surponiente', {orient_norte: 1, orient_sur: 1, orient_oriente: 1, orient_poniente: 1})"""
    flags = {"orient_norte": "", "orient_sur": "", "orient_oriente": "", "orient_poniente": ""}
    if not valor or not str(valor).strip():
        return "", flags
    texto = normalizar(valor)
    compacto = re.sub(r"[^a-z]", "", texto)
    norte = sur = oriente = poniente = False
    if compacto and re.fullmatch(r"[nsop]+", compacto):  # codigos: N, S, O, P, NO, NP, SO, SP
        s, i, tokens = compacto.upper(), 0, []
        while i < len(s):
            if s[i:i + 2] in ("NO", "NP", "SO", "SP"):
                tokens.append(s[i:i + 2])
                i += 2
            else:
                tokens.append(s[i])
                i += 1
        tokens = list(dict.fromkeys(tokens))  # sin repetidos, en orden
        nombre = "-".join(PUNTOS_CARDINALES[t] for t in tokens)
        norte = any(t.startswith("N") for t in tokens)
        sur = any(t.startswith("S") for t in tokens)
        oriente = any("O" in t for t in tokens)
        poniente = any("P" in t for t in tokens)
    else:  # escrito con palabras: "Norte", "Nor Poniente", "Sur-Oriente"...
        nombre = str(valor).strip().title()
        norte, sur = "nor" in texto, "sur" in texto
        oriente = "orient" in texto or "este" in texto
        poniente = "ponient" in texto or "oeste" in texto
    if any((norte, sur, oriente, poniente)):
        flags = {"orient_norte": int(norte), "orient_sur": int(sur),
                 "orient_oriente": int(oriente), "orient_poniente": int(poniente)}
    return nombre, flags


def moneda_normalizada(m):
    m = (m or "").strip().upper().replace(" ", "")
    if m in ("UF", "CLF", "U.F.", "U.F"):
        return "UF"
    if m in ("$", "CLP", "PESOS"):
        return "CLP"
    if m in ("US$", "USD", "U$S"):
        return "USD"
    return m or ""


# --------------------------------------------------------------------------
# Parseo de la pagina de resultados (etapa 1)
# --------------------------------------------------------------------------
def precio_desde_monto(tag):
    """Lee un bloque 'andes-money-amount' de Mercado Libre -> (valor, moneda)."""
    if tag is None:
        return None, ""
    simbolo = tag.select_one(".andes-money-amount__currency-symbol")
    fraccion = tag.select_one(".andes-money-amount__fraction")
    centavos = tag.select_one(".andes-money-amount__cents")
    if fraccion is None:
        return a_numero(tag.get_text(" ", strip=True)), ""
    valor = a_numero(fraccion.get_text(strip=True))
    if valor is not None and centavos is not None:
        c = re.sub(r"\D", "", centavos.get_text())
        if c:
            valor = round(valor + int(c) / (10 ** len(c)), 2)
    moneda = moneda_normalizada(simbolo.get_text(strip=True) if simbolo else "")
    return valor, moneda


def _id_desde_url(url: str) -> str:
    m = re.search(r"MLC-?(\d+)", url)
    if m:
        return "MLC" + m.group(1)
    return "P-" + slug(urlparse(url).path)[-60:]


def _limpiar_url(href: str) -> str:
    url = urljoin(BASE, href.split("#")[0].split("?")[0])
    return re.sub(r"^https?://portalinmobiliario\.com", "https://www.portalinmobiliario.com", url)


def parsear_listado(html: str, incluir_proyectos: bool = False) -> list[dict]:
    """Devuelve una lista de tarjetas (dict) con el link y datos basicos de cada aviso."""
    soup = BeautifulSoup(html, PARSER)
    items = (soup.select("li.ui-search-layout__item")
             or soup.select("div.poly-card")
             or soup.select("div.ui-search-result__wrapper"))
    tarjetas, vistos = [], set()

    for it in items:
        # Proyectos inmobiliarios (etiqueta "PROYECTO", precio "Desde", rangos de m2): se omiten por defecto
        pill = it.select_one(".poly-component__pill, [class*='pill']")
        prefijo = it.select_one(".poly-price__prefix")
        es_proyecto = bool((pill and "proyecto" in normalizar(pill.get_text()))
                           or (prefijo and "desde" in normalizar(prefijo.get_text())))
        if es_proyecto and not incluir_proyectos:
            continue
        enlaces = [a["href"] for a in it.select("a[href]") if a["href"].strip() not in ("", "#")]
        href = next((h for h in enlaces if re.search(r"MLC-?\d+", h)), None)
        if href is None:
            if not incluir_proyectos or not enlaces:
                continue
            href = enlaces[0]
        url = _limpiar_url(href)
        id_aviso = _id_desde_url(url)
        if id_aviso in vistos:
            continue
        vistos.add(id_aviso)

        t = {c: "" for c in COLUMNAS_URLS}
        t["id_aviso"], t["url"] = id_aviso, url
        titulo = it.select_one(".poly-component__title, .ui-search-item__title, h2, h3")
        t["titulo"] = titulo.get_text(" ", strip=True) if titulo else ""
        valor, moneda = precio_desde_monto(it.select_one(".andes-money-amount"))
        t["precio"] = "" if valor is None else valor
        t["moneda"] = moneda
        ubic = it.select_one(".poly-component__location, .ui-search-result__content-location, "
                             "[class*='location']")
        t["ubicacion"] = ubic.get_text(" ", strip=True) if ubic else ""

        for li in it.select("li"):
            txt = normalizar(li.get_text(" ", strip=True))
            num = a_numero(txt)
            if num is None:
                continue
            if "dormitorio" in txt and not t["dormitorios"]:
                t["dormitorios"] = num
            elif "bano" in txt and not t["banos"]:
                t["banos"] = num
            elif "m2" in txt.replace("m 2", "m2") or "m²" in li.get_text():
                if "util" in txt and not t["superficie_util_m2"]:
                    t["superficie_util_m2"] = num
                elif "total" in txt and not t["superficie_total_m2"]:
                    t["superficie_total_m2"] = num
        tarjetas.append(t)

    if not tarjetas:  # respaldo: buscar links de avisos directamente en el HTML
        for m in re.finditer(r'https?://(?:www\.)?portalinmobiliario\.com/MLC-?\d+[^"\'#?\s<>]*', html):
            url = _limpiar_url(m.group(0))
            id_aviso = _id_desde_url(url)
            if id_aviso not in vistos:
                vistos.add(id_aviso)
                t = {c: "" for c in COLUMNAS_URLS}
                t["id_aviso"], t["url"] = id_aviso, url
                tarjetas.append(t)
    return tarjetas


def _json_embebido(html: str) -> str:
    return html.replace("\\u002F", "/").replace('\\"', '"')


def url_siguiente(html: str, pagina_actual: int | None = None) -> str | None:
    soup = BeautifulSoup(html, PARSER)
    for sel in ("li.andes-pagination__button--next a", 'a[title="Siguiente"]',
                'a[aria-label="Siguiente"]', "a.andes-pagination__link--next"):
        a = soup.select_one(sel)
        if a and a.get("href") and a["href"].strip() not in ("", "#"):
            return _limpiar_url(a["href"])
    # El sitio deja los links de paginacion vacios y guarda las URLs en un JSON dentro de la pagina
    if pagina_actual:
        m = re.search(r'"value"\s*:\s*"%d"\s*,\s*"url"\s*:\s*"([^"]+)"' % (pagina_actual + 1),
                      _json_embebido(html))
        if m:
            return _limpiar_url(m.group(1))
    return None


def resumen_busqueda(html: str):
    """-> (titulo, total de resultados, paginas disponibles)"""
    soup = BeautifulSoup(html, PARSER)
    h1 = soup.select_one("h1")
    titulo = h1.get_text(" ", strip=True) if h1 else ""
    m = re.search(r"([\d\.]+)\s+resultados?", soup.get_text(" ", strip=True))
    total = a_numero(m.group(1)) if m else None
    mp = re.search(r'"page_count"\s*:\s*(\d+)', _json_embebido(html))
    paginas = int(mp.group(1)) if mp else None
    return titulo, total, paginas


def construir_pagina(url_base: str, desde: int) -> str:
    """Arma la URL de la pagina que parte en el aviso 'desde' (formato _Desde_49)."""
    u = urlparse(url_base)
    path = re.sub(r"_Desde_\d+_?", "", u.path)
    if "/_" in path:
        path = path.replace("/_", f"/_Desde_{desde}_", 1)
    else:
        path = path.rstrip("/") + f"/_Desde_{desde}"
    return f"{u.scheme}://{u.netloc}{path}"


# --------------------------------------------------------------------------
# Parseo de la ficha de cada aviso (etapa 2)
# --------------------------------------------------------------------------
def _buscar_oferta(obj):
    if isinstance(obj, dict):
        if "price" in obj and "priceCurrency" in obj:
            return obj["price"], obj["priceCurrency"]
        for v in obj.values():
            r = _buscar_oferta(v)
            if r:
                return r
    elif isinstance(obj, list):
        for v in obj:
            r = _buscar_oferta(v)
            if r:
                return r
    return None


def extraer_precio(soup):
    # 1) Datos estructurados (JSON-LD)
    for s in soup.select('script[type="application/ld+json"]'):
        try:
            r = _buscar_oferta(json.loads(s.string or ""))
        except (ValueError, TypeError):
            continue
        if r and a_numero(r[0]) is not None:
            return a_numero(r[0]), moneda_normalizada(r[1])
    # 2) Metadatos
    meta_p = soup.select_one('meta[itemprop="price"]')
    meta_m = soup.select_one('meta[itemprop="priceCurrency"]')
    if meta_p and meta_p.get("content"):
        return a_numero(meta_p["content"]), moneda_normalizada(meta_m.get("content") if meta_m else "")
    # 3) Bloque de precio visible
    tag = soup.select_one(".ui-pdp-price__second-line .andes-money-amount, "
                          ".ui-pdp-price .andes-money-amount, .andes-money-amount")
    return precio_desde_monto(tag)


def extraer_caracteristicas(soup):
    """Lee todas las tablas de caracteristicas (Principales, Servicios, Comodidades, Seguridad,
    Ambientes, Condiciones especiales) y el recuadro de destacados.
    Devuelve (campos con columna propia, otras caracteristicas {etiqueta: valor})."""
    datos, extras = {}, {}

    def guardar(etiqueta, valor):
        etiqueta = (etiqueta or "").strip().rstrip(":").strip()
        valor = (valor or "").strip()
        if not etiqueta or not valor or len(etiqueta) > 60 or len(valor) > 120:
            return
        col = ETIQUETAS.get(clave_etiqueta(etiqueta))
        if col:
            datos.setdefault(col, valor)
        else:
            extras.setdefault(etiqueta, valor)

    for fila in soup.select("tr"):  # tablas: <th>etiqueta</th><td>valor</td>
        th, td = fila.find("th"), fila.find("td")
        if th and td:
            guardar(th.get_text(" ", strip=True), td.get_text(" ", strip=True))
    for dt in soup.select("dt"):  # listas de definicion
        dd = dt.find_next_sibling("dd")
        if dd:
            guardar(dt.get_text(" ", strip=True), dd.get_text(" ", strip=True))
    for el in soup.select("[class*='key-value'], [class*='highlighted-specs'] p"):  # "Etiqueta: valor"
        txt = el.get_text(" ", strip=True)
        if ":" in txt:
            etq, val = txt.split(":", 1)
            guardar(etq, val)
    return datos, extras


_PATRONES_COORD = [
    re.compile(r'"latitude"\s*:\s*"?(-?\d{1,2}\.\d+)"?\s*,\s*"longitude"\s*:\s*"?(-?\d{1,3}\.\d+)'),
    re.compile(r'"lat"\s*:\s*"?(-?\d{1,2}\.\d+)"?\s*,\s*"(?:lng|lon)"\s*:\s*"?(-?\d{1,3}\.\d+)'),
    re.compile(r'center=(-?\d{1,2}\.\d+)(?:%2C|,)\s*(-?\d{1,3}\.\d+)'),
    re.compile(r'[?&](?:q|ll|query)=(-?\d{1,2}\.\d+)(?:%2C|,)\s*(-?\d{1,3}\.\d+)'),
]


def _en_chile(lat, lon) -> bool:
    return -56.5 <= lat <= -17.0 and -76.5 <= lon <= -66.0


def extraer_coordenadas(html: str):
    h = html.replace('\\"', '"')
    for patron in _PATRONES_COORD:
        for m in patron.finditer(h):
            lat, lon = float(m.group(1)), float(m.group(2))
            if _en_chile(lat, lon):
                return lat, lon
    mlat = re.search(r'"latitude"\s*:\s*"?(-?\d{1,2}\.\d+)', h)
    mlon = re.search(r'"longitude"\s*:\s*"?(-?\d{1,3}\.\d+)', h)
    if mlat and mlon:
        lat, lon = float(mlat.group(1)), float(mlon.group(1))
        if _en_chile(lat, lon):
            return lat, lon
    return None, None


def extraer_direccion(soup):
    for sel in (".ui-vip-location__subtitle", ".ui-vip-location p",
                "[class*='vip-location'] p", "[class*='location'] p"):
        el = soup.select_one(sel)
        if el:
            t = el.get_text(" ", strip=True)
            if t and len(t) < 200:
                return t
    return ""


def _es_region(parte: str) -> bool:
    n = re.sub(r"[^a-z ]", "", normalizar(parte))
    n = re.sub(r"^region (de la |del |de )?", "", n).strip()
    return n in REGIONES


def _partes_ubicacion(texto: str) -> list[str]:
    partes = []
    for p in (texto or "").split(","):
        p = re.sub(r"^\s*\d{6,8}\s*", "", p).strip()  # quita codigos postales
        if p and normalizar(p) != "chile":
            partes.append(p)
    while len(partes) >= 3 and _es_region(partes[-1]):  # "..., Concepcion, Biobio" -> sin la region
        partes.pop()
    return partes


def partir_ubicacion(texto: str):
    """'Freire 1165, Centro De Concepcion, Concepcion' -> ('Centro De Concepcion', 'Concepcion')"""
    partes = _partes_ubicacion(texto)
    if not partes:
        return "", ""
    barrio = partes[-2] if len(partes) >= 2 else ""
    if len(partes) == 2 and re.search(r"\d", barrio):  # 'Colon 100, Talcahuano': es calle, no barrio
        barrio = ""
    return barrio, partes[-1]


def elegir_comuna(ubicacion: str, comuna_busqueda: str = "") -> str:
    """Usa la comuna buscada si aparece en la ubicacion del aviso (con sus tildes); si no
    aparece (ej. un aviso destacado de otra comuna), usa la que dice el propio aviso."""
    partes = _partes_ubicacion(ubicacion)
    if comuna_busqueda:
        objetivo = normalizar(comuna_busqueda)
        for p in reversed(partes):
            if normalizar(p) == objetivo:
                return p
    return partes[-1] if partes else (comuna_busqueda or "")


def ficha_valida(html: str) -> bool:
    soup = BeautifulSoup(html, PARSER)
    return soup.select_one("h1") is not None and (
        bool(extraer_caracteristicas(soup)[0]) or extraer_precio(soup)[0] is not None)


def parsear_ficha(html: str, tarjeta: dict, uf: float | None) -> dict:
    soup = BeautifulSoup(html, PARSER)
    fila = {c: "" for c in COLUMNAS}
    fila["id_aviso"], fila["url"] = tarjeta["id_aviso"], tarjeta["url"]

    h1 = soup.select_one("h1.ui-pdp-title") or soup.select_one("h1")
    fila["titulo"] = h1.get_text(" ", strip=True) if h1 else tarjeta.get("titulo", "")

    precio, moneda = extraer_precio(soup)
    if precio is None:  # respaldo: precio de la tarjeta del listado
        precio, moneda = a_numero(tarjeta.get("precio")), tarjeta.get("moneda", "")
    fila["precio"] = "" if precio is None else precio
    fila["moneda"] = moneda
    if precio is not None and moneda == "UF":
        fila["precio_uf"] = precio
    elif precio is not None and moneda == "CLP" and uf:
        fila["precio_uf"] = round(precio / uf, 1)
    fila["uf_usada"] = uf or ""

    caracteristicas, otras = extraer_caracteristicas(soup)
    for col, val in caracteristicas.items():
        if col in CAMPOS_BOOLEANOS:
            fila[col] = a_booleano(val)
        elif col in CAMPOS_TEXTO:
            fila[col] = val
        else:
            fila[col] = a_numero(val)
    for col in ("dormitorios", "banos", "superficie_util_m2", "superficie_total_m2"):
        if fila[col] in ("", None) and tarjeta.get(col) not in ("", None):
            fila[col] = a_numero(tarjeta[col])
    fila["orientacion"], flags = descomponer_orientacion(fila["orientacion_raw"])
    fila.update(flags)
    fila["otras_caracteristicas"] = json.dumps(otras, ensure_ascii=False) if otras else ""

    fila["direccion"] = extraer_direccion(soup) or tarjeta.get("ubicacion", "")
    ubicacion = tarjeta.get("ubicacion") or fila["direccion"]
    fila["barrio"], _ = partir_ubicacion(ubicacion)
    fila["comuna_busqueda"] = tarjeta.get("comuna_busqueda", "")
    fila["comuna"] = elegir_comuna(ubicacion, fila["comuna_busqueda"])
    fila["region"] = tarjeta.get("region", "")

    lat, lon = extraer_coordenadas(html)
    fila["latitud"] = "" if lat is None else lat
    fila["longitud"] = "" if lon is None else lon
    fila["fecha_scraping"] = datetime.now().strftime("%Y-%m-%d")
    return {k: ("" if v is None else v) for k, v in fila.items()}


# --------------------------------------------------------------------------
# robots.txt (con soporte de comodines * y $, como los interpreta Google)
# --------------------------------------------------------------------------
class Robots:
    def __init__(self, texto: str | None):
        self.reglas = []          # (permitir: bool, regex, largo)
        self.crawl_delay = None
        self.disponible = texto is not None
        if not texto:
            return
        aplica, leyendo_agentes = False, False
        for linea in texto.splitlines():
            linea = linea.split("#", 1)[0].strip()
            if ":" not in linea:
                continue
            campo, valor = (x.strip() for x in linea.split(":", 1))
            campo = campo.lower()
            if campo == "user-agent":
                if not leyendo_agentes:
                    aplica = False
                leyendo_agentes = True
                if valor == "*":
                    aplica = True
                continue
            leyendo_agentes = False
            if not aplica:
                continue
            if campo in ("allow", "disallow") and valor:
                self.reglas.append((campo == "allow", self._a_regex(valor), len(valor)))
            elif campo == "crawl-delay":
                try:
                    self.crawl_delay = float(valor)
                except ValueError:
                    pass

    @staticmethod
    def _a_regex(patron: str):
        ancla = patron.endswith("$")
        if ancla:
            patron = patron[:-1]
        cuerpo = "".join(".*" if c == "*" else re.escape(c) for c in patron)
        return re.compile("^" + cuerpo + ("$" if ancla else ""))

    def permitido(self, url: str) -> bool:
        u = urlparse(url)
        ruta = (u.path or "/") + (("?" + u.query) if u.query else "")
        mejor = None
        for permitir, rx, largo in self.reglas:
            if rx.match(ruta) and (mejor is None or largo > mejor[1]
                                   or (largo == mejor[1] and permitir)):
                mejor = (permitir, largo)
        return True if mejor is None else mejor[0]


# --------------------------------------------------------------------------
# Navegacion
# --------------------------------------------------------------------------
class Navegador:
    def __init__(self, page, visible: bool, pausa_min: float, pausa_max: float):
        self.page, self.visible = page, visible
        self.pausa_min, self.pausa_max = pausa_min, pausa_max

    def pausa(self, factor: float = 1.0):
        DETENER.wait(random.uniform(self.pausa_min, self.pausa_max) * factor)

    def _esperar_verificacion(self, es_valida, segundos: int = 300) -> str | None:
        """Espera a que la persona resuelva la verificacion en la ventana del navegador."""
        fin = time.time() + segundos
        while time.time() < fin and not DETENER.is_set():
            DETENER.wait(3)
            try:
                html = self.page.content()
            except Exception:
                continue  # la pagina esta navegando
            if es_valida(html):
                print("     Verificacion resuelta, se continua.")
                return html
        return None

    def abrir(self, url: str, es_valida, intentos: int = 3) -> str | None:
        for intento in range(1, intentos + 1):
            if DETENER.is_set():
                return None
            try:
                resp = self.page.goto(url, wait_until="domcontentloaded", timeout=45000)
                self.page.wait_for_timeout(random.randint(1200, 2500))
                self.page.mouse.wheel(0, 2500)  # carga contenido diferido (mapa, tablas)
                self.page.wait_for_timeout(800)
                html = self.page.content()
            except Exception as e:  # timeouts, red, etc.
                print(f"   ! Error cargando la pagina ({e.__class__.__name__}). Reintento {intento}/{intentos}")
                DETENER.wait(10 * intento)
                continue
            estado = resp.status if resp else 0
            if estado in (404, 410):
                return None
            if es_valida(html):
                return html
            bajo = html.lower()
            bloqueo = (estado in (403, 429) or "account-verification" in self.page.url
                       or any(s in bajo for s in SENALES_BLOQUEO))
            if not bloqueo:
                return html  # pagina sin el contenido esperado, pero sin bloqueo
            if self.visible:
                print(f"   ! El sitio pide una verificacion (HTTP {estado}). Resuelvela en la ventana del\n"
                      "     navegador: el scraper sigue solo apenas cargue la pagina (espera hasta 5 minutos).")
                html = self._esperar_verificacion(es_valida)
                if html is not None:
                    return html
            else:
                espera = 60 * intento
                print(f"   ! Posible bloqueo (HTTP {estado}). Esperando {espera} s...")
                DETENER.wait(espera)
        if DETENER.is_set():
            return None
        raise Bloqueado(url)


# --------------------------------------------------------------------------
# Archivos CSV
# --------------------------------------------------------------------------
def leer_csv(ruta: str) -> list[dict]:
    if not os.path.exists(ruta):
        return []
    with open(ruta, newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def preparar_csv(ruta: str, columnas: list[str]):
    """Si el CSV existe pero tiene las columnas de una version anterior del script, lo renombra
    (sus avisos se vuelven a visitar para sacar las columnas nuevas)."""
    if not os.path.exists(ruta) or os.path.getsize(ruta) == 0:
        return
    with open(ruta, newline="", encoding="utf-8-sig") as f:
        encabezado = next(csv.reader(f), [])
    if encabezado == columnas:
        return
    base, ext = os.path.splitext(ruta)
    anterior = f"{base}_anterior_{datetime.now():%Y%m%d_%H%M%S}{ext}"
    try:
        os.replace(ruta, anterior)
    except PermissionError:
        raise PermissionError(f"No se pudo renombrar {ruta}. Si lo tienes abierto en Excel, cierralo "
                              "y vuelve a correr.") from None
    print(f"! {ruta} tenia columnas de una version anterior del script.\n"
          f"  Se guardo como {anterior} y esos avisos se volveran a visitar.")


def abrir_csv_escritura(ruta: str, columnas: list[str]):
    nuevo = not os.path.exists(ruta) or os.path.getsize(ruta) == 0
    try:
        f = open(ruta, "a", newline="", encoding="utf-8-sig")
    except PermissionError:
        raise PermissionError(f"No se puede escribir en {ruta}. Si lo tienes abierto en Excel, "
                              "cierralo y vuelve a correr (el avance no se pierde).") from None
    w = csv.DictWriter(f, fieldnames=columnas, extrasaction="ignore")
    if nuevo:
        w.writeheader()
    return f, w


def leer_lista(ruta: str) -> set[str]:
    if not os.path.exists(ruta):
        return set()
    with open(ruta, encoding="utf-8") as f:
        return {l.strip() for l in f if l.strip()}


# --------------------------------------------------------------------------
# Etapas
# --------------------------------------------------------------------------
def etapa_listados(nav, robots, busquedas, archivo_urls, max_paginas, incluir_proyectos):
    preparar_csv(archivo_urls, COLUMNAS_URLS)
    vistos = {r["id_aviso"] for r in leer_csv(archivo_urls)}
    f, w = abrir_csv_escritura(archivo_urls, COLUMNAS_URLS)
    total_nuevos = 0
    es_listado = lambda h: bool(parsear_listado(h, True)) or "no hay publicaciones" in h.lower()
    try:
        for url_base, region, comuna in busquedas:
            if DETENER.is_set():
                break
            print(f"\n== Busqueda: {url_base}")
            url = url_base
            paginas_sitio = None
            ids_pagina_anterior = None
            for n_pag in range(1, max_paginas + 1):
                if DETENER.is_set():
                    break
                if not robots.permitido(url):
                    alternativa = construir_pagina(url_base, (n_pag - 1) * AVISOS_POR_PAGINA + 1)
                    if n_pag > 1 and robots.permitido(alternativa):
                        url = alternativa
                    else:
                        print(f"   robots.txt no permite visitar {url}. Se omite.")
                        break
                html = nav.abrir(url, es_listado)
                if html is None:
                    break
                if n_pag == 1:
                    titulo, total, paginas_sitio = resumen_busqueda(html)
                    print(f"   {titulo or 'Resultados'}: {total if total is not None else '?'} resultados"
                          + (f" en {paginas_sitio} paginas" if paginas_sitio else ""))
                    if total and total > MAX_PAGINAS_SITIO * AVISOS_POR_PAGINA:
                        print(f"   ! El sitio muestra solo {MAX_PAGINAS_SITIO} paginas por busqueda: quedaran "
                              f"~{total - MAX_PAGINAS_SITIO * AVISOS_POR_PAGINA} avisos afuera.\n"
                              "     Divide la busqueda con --comunas para obtenerlos todos.")
                todas = parsear_listado(html, True)  # incluye proyectos, solo para saber si hay mas paginas
                ids_pagina = {t["id_aviso"] for t in todas}
                if ids_pagina and ids_pagina == ids_pagina_anterior:
                    break  # el sitio repitio la pagina anterior: no hay mas
                ids_pagina_anterior = ids_pagina
                tarjetas = parsear_listado(html, incluir_proyectos)
                nuevos = 0
                for t in tarjetas:
                    if t["id_aviso"] in vistos:
                        continue
                    t["region"], t["comuna_busqueda"] = region, comuna
                    w.writerow(t)
                    vistos.add(t["id_aviso"])
                    nuevos += 1
                f.flush()
                total_nuevos += nuevos
                omitidos = len(todas) - len(tarjetas)
                print(f"   pagina {n_pag}: {len(tarjetas)} avisos ({nuevos} nuevos)"
                      + (f", {omitidos} proyectos omitidos" if omitidos > 0 else ""))
                if not todas or (paginas_sitio and n_pag >= paginas_sitio):
                    break
                siguiente = url_siguiente(html, n_pag)
                if siguiente is None and len(todas) >= AVISOS_POR_PAGINA - 8:
                    siguiente = construir_pagina(url_base, n_pag * AVISOS_POR_PAGINA + 1)
                if siguiente is None or siguiente == url:
                    break
                url = siguiente
                nav.pausa()
            nav.pausa()
    finally:
        f.close()
    print(f"\nEtapa 1 lista: {total_nuevos} links nuevos (total {len(vistos)}) en {archivo_urls}")


def etapa_fichas(nav, robots, archivo_urls, archivo_salida, archivo_descartados, uf, max_avisos):
    preparar_csv(archivo_salida, COLUMNAS)
    tarjetas = leer_csv(archivo_urls)
    hechos = {r["id_aviso"] for r in leer_csv(archivo_salida)} | leer_lista(archivo_descartados)
    pendientes = [t for t in tarjetas if t["id_aviso"] not in hechos]
    if max_avisos:
        pendientes = pendientes[:max_avisos]
    print(f"\n== Etapa 2: {len(pendientes)} fichas por visitar ({len(hechos)} ya procesadas)")
    if not pendientes:
        return
    f, w = abrir_csv_escritura(archivo_salida, COLUMNAS)
    desc = open(archivo_descartados, "a", encoding="utf-8")
    guardadas = 0
    try:
        for i, t in enumerate(pendientes, 1):
            if DETENER.is_set():
                break
            if not robots.permitido(t["url"]):
                print(f"[{i}/{len(pendientes)}] robots.txt no permite {t['url']}. Se omite.")
                continue
            html = nav.abrir(t["url"], ficha_valida)
            if DETENER.is_set():
                break
            if html is None or "publicacion finalizada" in normalizar(html[:300000]) or not ficha_valida(html):
                print(f"[{i}/{len(pendientes)}] {t['id_aviso']}: aviso finalizado o sin datos. Se descarta.")
                desc.write(t["id_aviso"] + "\n")
                desc.flush()
            else:
                fila = parsear_ficha(html, t, uf)
                w.writerow(fila)
                f.flush()
                guardadas += 1
                print(f"[{i}/{len(pendientes)}] {fila['id_aviso']} | {fila['precio']} {fila['moneda']} | "
                      f"{fila['dormitorios']}D {fila['banos']}B | {fila['superficie_util_m2'] or fila['superficie_total_m2']} m2 | "
                      f"piso {fila['piso']} | {fila['orientacion'] or '-'} | {fila['comuna']}")
            nav.pausa(factor=6 if i % 50 == 0 else 1)  # pausa larga cada 50 fichas
    finally:
        f.close()
        desc.close()
    print(f"\nEtapa 2 lista: {guardadas} departamentos guardados en {archivo_salida}")


# --------------------------------------------------------------------------
# Cargar el resultado en pandas
# --------------------------------------------------------------------------
def cargar_dataset(ruta: str = "departamentos_biobio.csv", expandir: bool = True):
    """Lee el CSV con pandas. Con expandir=True, convierte 'otras_caracteristicas' (JSON)
    en columnas extra_<nombre>, con Si/No como 1/0."""
    import pandas as pd

    df = pd.read_csv(ruta, encoding="utf-8-sig")
    if not expandir or "otras_caracteristicas" not in df.columns:
        return df

    def convertir(v):
        if not isinstance(v, str):
            return v
        n = normalizar(v)
        if n in ("si", "no"):
            return a_booleano(v)
        if re.fullmatch(r"-?\d+(?:[.,]\d+)?", v.strip()) or _RE_MILES.fullmatch(v.strip()):
            return a_numero(v)
        return v

    dicts = df["otras_caracteristicas"].map(lambda s: json.loads(s) if isinstance(s, str) and s else {})
    extras = pd.DataFrame(dicts.tolist(), index=df.index)
    if extras.empty:
        return df.drop(columns="otras_caracteristicas")
    extras = extras.map(convertir) if hasattr(extras, "map") else extras.applymap(convertir)
    extras.columns = ["extra_" + slug(c).replace("-", "_") for c in extras.columns]
    return pd.concat([df.drop(columns="otras_caracteristicas"), extras], axis=1)


# --------------------------------------------------------------------------
# Programa principal
# --------------------------------------------------------------------------
def obtener_uf(uf_manual):
    if uf_manual:
        return float(uf_manual)
    try:
        req = urllib.request.Request("https://mindicador.cl/api/uf", headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=15) as r:
            valor = float(json.load(r)["serie"][0]["valor"])
        print(f"UF del dia (mindicador.cl): {valor:,.2f}")
        return valor
    except Exception:
        print("! No se pudo obtener la UF desde mindicador.cl. Los avisos en pesos quedaran sin precio_uf.\n"
              "  Puedes indicarla a mano con --uf <valor>.")
        return None


def construir_busquedas(args) -> list[tuple[str, str, str]]:
    if args.url:
        return [(u.strip(), args.region or "", "") for u in args.url]
    region = slug(args.region or "biobio")
    cond = {"usadas": "propiedades-usadas/", "nuevas": "propiedades-nuevas/", "todas": ""}[args.condicion]
    if args.comunas:
        return [(f"{BASE}/venta/departamento/{cond}{slug(c)}-{region}", region, c.strip().title())
                for c in args.comunas.split(",") if c.strip()]
    return [(f"{BASE}/venta/departamento/{cond}{region}", region, "")]


def parse_args(argv=None):
    p = argparse.ArgumentParser(prog="scraper_portalinmobiliario",
                                description="Scraper de departamentos en venta - Portal Inmobiliario")
    p.add_argument("--region", help="Slug de la region tal como aparece en la URL del sitio (por defecto: biobio)")
    p.add_argument("--comunas", help='Lista separada por comas, ej: "concepcion,talcahuano,san pedro de la paz"')
    p.add_argument("--url", action="append", help="URL de busqueda copiada del navegador (se puede repetir)")
    p.add_argument("--condicion", choices=["usadas", "nuevas", "todas"], default="usadas")
    p.add_argument("--max-paginas", type=int, default=50, help="Paginas de resultados por busqueda (48 avisos c/u)")
    p.add_argument("--max-avisos", type=int, default=0, help="Maximo de fichas a visitar en esta corrida (0 = todas)")
    p.add_argument("--salida", default="departamentos_biobio.csv")
    p.add_argument("--uf", type=float, help="Valor de la UF para convertir precios en pesos")
    p.add_argument("--headless", action="store_true", help="No mostrar la ventana del navegador")
    p.add_argument("--pausa-min", type=float, default=3.0, help="Segundos minimos entre paginas")
    p.add_argument("--pausa-max", type=float, default=7.0, help="Segundos maximos entre paginas")
    p.add_argument("--solo-urls", action="store_true", help="Solo etapa 1 (juntar links)")
    p.add_argument("--solo-fichas", action="store_true", help="Solo etapa 2 (usa los links ya guardados)")
    p.add_argument("--incluir-proyectos", action="store_true",
                   help="Incluir proyectos nuevos con rango de precios (por defecto se omiten)")
    return p.parse_args(argv)


def _en_kernel() -> bool:
    """True si sys.argv es el de un kernel de Jupyter/Colab (y no argumentos del usuario)."""
    argv = sys.argv or [""]
    return "kernel" in os.path.basename(argv[0]) or any(
        a.endswith(".json") and "kernel" in os.path.basename(a) for a in argv[1:])


def _hay_loop_activo() -> bool:
    try:
        asyncio.get_running_loop()
        return True
    except RuntimeError:
        return False


@contextlib.contextmanager
def _loop_compatible_windows():
    """Jupyter en Windows cambia el tipo de event loop por uno que no puede abrir el navegador.
    Mientras Playwright arranca se usa el loop normal de Windows y despues se restaura."""
    if sys.platform != "win32":
        yield
        return
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        previa = asyncio.get_event_loop_policy()
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    try:
        yield
    finally:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            asyncio.set_event_loop_policy(previa)


MSG_FALTA_PLAYWRIGHT = (
    "Falta Playwright. Instalalo asi:\n"
    "  En una terminal:     pip install -r requirements.txt\n"
    "                       python -m playwright install chromium\n"
    "  En Jupyter (celdas): %pip install beautifulsoup4 lxml playwright\n"
    "                       import sys; !{sys.executable} -m playwright install chromium"
)
MSG_FALTA_CHROMIUM = (
    "Falta el navegador de Playwright. Instalalo asi:\n"
    "  En una terminal:     python -m playwright install chromium\n"
    "  En Jupyter (celda):  import sys; !{sys.executable} -m playwright install chromium"
)


def main(argv=None):
    """Punto de entrada. En Jupyter: main("--max-paginas 1 --max-avisos 10")."""
    if argv is None:
        argv = [] if _en_kernel() else sys.argv[1:]
    elif isinstance(argv, str):
        argv = shlex.split(argv)
    args = parse_args(list(argv))
    DETENER.clear()

    if "google.colab" in sys.modules:
        print("! Estas en Google Colab: no hay ventana de navegador y el sitio suele bloquear las IPs\n"
              "  de Google. Lo mas probable es que no funcione; corre el scraper en tu computador.")
        args.headless = True

    if not _hay_loop_activo():  # terminal normal
        _ejecutar(args)
        return

    # Jupyter ya tiene un event loop corriendo y Playwright (API sincronica) no puede
    # usarse dentro de el, asi que el scraper corre en un hilo aparte.
    errores = []

    def tarea():
        try:
            _ejecutar(args)
        except BaseException as e:  # se relanza en el hilo principal
            errores.append(e)

    hilo = threading.Thread(target=tarea, name="scraper", daemon=True)
    hilo.start()
    while hilo.is_alive():
        try:
            hilo.join(0.5)
        except KeyboardInterrupt:
            if not DETENER.is_set():
                DETENER.set()
                print("\nDeteniendo despues de la pagina actual... (el avance queda guardado)")
    if errores:
        raise errores[0]


def _ejecutar(args):
    busquedas = construir_busquedas(args)
    base_salida = os.path.splitext(args.salida)[0]
    archivo_urls = base_salida + "_urls.csv"
    archivo_desc = base_salida + "_descartados.txt"

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        raise ImportError(MSG_FALTA_PLAYWRIGHT) from None

    uf = None if args.solo_urls else obtener_uf(args.uf)

    with _loop_compatible_windows():
        pw = sync_playwright().start()
    try:
        try:
            ctx = pw.chromium.launch_persistent_context(
                user_data_dir=".perfil_navegador",
                headless=args.headless,
                locale="es-CL",
                timezone_id="America/Santiago",
                viewport={"width": 1366, "height": 900},
            )
        except Exception as e:
            if "Executable doesn't exist" in str(e) or "playwright install" in str(e):
                raise RuntimeError(MSG_FALTA_CHROMIUM) from None
            raise
        _scrapear(ctx, args, busquedas, archivo_urls, archivo_desc, uf)
    finally:
        pw.stop()


def _scrapear(ctx, args, busquedas, archivo_urls, archivo_desc, uf):
    # No descargar imagenes, videos ni fuentes: menos carga para el sitio y mas rapido
    ctx.route("**/*", lambda route: route.abort()
              if route.request.resource_type in ("image", "media", "font") else route.continue_())
    page = ctx.pages[0] if ctx.pages else ctx.new_page()

    texto_robots = None
    try:
        r = ctx.request.get(BASE + "/robots.txt", timeout=20000)
        if r.ok:
            texto_robots = r.text()
    except Exception:
        pass
    robots = Robots(texto_robots)
    if not robots.disponible:
        print("! No se pudo leer robots.txt; se continua con pausas conservadoras.")
    if robots.crawl_delay and robots.crawl_delay > args.pausa_min:
        print(f"robots.txt pide {robots.crawl_delay:.0f} s entre visitas; se ajustan las pausas.")
        args.pausa_min = robots.crawl_delay
        args.pausa_max = max(args.pausa_max, robots.crawl_delay * 1.5)

    nav = Navegador(page, visible=not args.headless, pausa_min=args.pausa_min, pausa_max=args.pausa_max)
    try:
        if not args.solo_fichas:
            etapa_listados(nav, robots, busquedas, archivo_urls, args.max_paginas, args.incluir_proyectos)
        if not args.solo_urls and not DETENER.is_set():
            etapa_fichas(nav, robots, archivo_urls, args.salida, archivo_desc, uf, args.max_avisos)
        if DETENER.is_set():
            print("\nDetenido. El avance quedo guardado; vuelve a correr lo mismo para continuar.")
    except Bloqueado as e:
        print(f"\nEl sitio sigue bloqueando ({e}). El avance quedo guardado.\n"
              "Espera un rato y vuelve a correr con --solo-fichas para continuar.")
    except KeyboardInterrupt:
        print("\nInterrumpido. El avance quedo guardado; vuelve a correr lo mismo para continuar.")
    finally:
        ctx.close()


if __name__ == "__main__":
    if _en_kernel():  # el codigo se pego en una celda de Jupyter/Colab
        print("Scraper cargado. Para ejecutarlo, corre en otra celda, por ejemplo:\n"
              '  main("--max-paginas 1 --max-avisos 10")')
    else:
        main()
