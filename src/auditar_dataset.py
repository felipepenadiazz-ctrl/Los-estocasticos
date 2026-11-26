#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Auditoria del dataset de departamentos (salida de scraper_portalinmobiliario.py).

Revisa estructura, cobertura respecto del indice de URLs, completitud de cada columna,
tipos y rangos, coherencia entre columnas y valores atipicos. Escribe un reporte en
Markdown y devuelve los problemas encontrados por aviso en un CSV aparte.

Uso (desde la raiz del repositorio):
  python src/auditar_dataset.py --datos data/raw/departamentos_biobio.csv --reporte docs/auditoria_datos.md
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import date

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import scraper_portalinmobiliario as sc  # noqa: E402

# Caja aproximada de la Region del Biobio (con margen)
LAT_MIN, LAT_MAX = -38.6, -36.3
LON_MIN, LON_MAX = -74.0, -71.0

NUMERICAS = sorted(sc.CAMPOS_NUMERICOS | {"precio", "precio_uf", "latitud", "longitud", "uf_usada"})
BOOLEANAS = sorted(sc.CAMPOS_BOOLEANOS | {"orient_norte", "orient_sur", "orient_oriente", "orient_poniente"})


def pct(n, d):
    return f"{100 * n / d:.1f}%" if d else "-"


def auditar(ruta_datos: str, ruta_urls: str, ruta_desc: str):
    df = pd.read_csv(ruta_datos, encoding="utf-8-sig", dtype=str, keep_default_na=False)
    urls = pd.read_csv(ruta_urls, encoding="utf-8-sig", dtype=str, keep_default_na=False)
    descartados = set()
    if os.path.exists(ruta_desc):
        with open(ruta_desc, encoding="utf-8") as f:
            descartados = {l.strip() for l in f if l.strip()}

    n = len(df)
    secciones = []
    problemas = []  # (id_aviso, tipo, detalle)

    def marcar(mask, tipo, detalle_fn):
        for _, r in df[mask].iterrows():
            problemas.append((r["id_aviso"], tipo, detalle_fn(r)))
        return int(mask.sum())

    # ---------------- Estructura ----------------
    faltan = [c for c in sc.COLUMNAS if c not in df.columns]
    sobran = [c for c in df.columns if c not in sc.COLUMNAS]
    dup_id = df["id_aviso"].duplicated(keep=False)
    vacios_id = (df["id_aviso"] == "") | (df["url"] == "")
    estructura = [
        f"- Filas: **{n}**, columnas: **{len(df.columns)}** (esperadas {len(sc.COLUMNAS)}).",
        f"- Columnas faltantes: {faltan or 'ninguna'}; columnas sobrantes: {sobran or 'ninguna'}.",
        f"- `id_aviso` duplicados: **{int(df['id_aviso'].duplicated().sum())}**; filas sin id o url: **{int(vacios_id.sum())}**.",
    ]
    marcar(dup_id, "id_duplicado", lambda r: r["id_aviso"])
    secciones.append(("Estructura", estructura))

    # ---------------- Cobertura ----------------
    ids_idx = set(urls["id_aviso"])
    ids_df = set(df["id_aviso"])
    pendientes = ids_idx - ids_df - descartados
    fuera_idx = ids_df - ids_idx
    fechas = df["fecha_scraping"].value_counts().sort_index()
    cobertura = [
        f"- Avisos en el indice de URLs (`*_urls.csv`): **{len(ids_idx)}**.",
        f"- Con ficha en el dataset: **{len(ids_idx & ids_df)}** ({pct(len(ids_idx & ids_df), len(ids_idx))}).",
        f"- Descartados (aviso finalizado o sin datos): **{len(descartados & ids_idx)}** ({pct(len(descartados & ids_idx), len(ids_idx))}).",
        f"- Pendientes (ni ficha ni descartado): **{len(pendientes)}**.",
        f"- Filas del dataset que no estan en el indice: **{len(fuera_idx)}**.",
        "- Fichas por fecha de extraccion: " + ", ".join(f"{k}: {v}" for k, v in fechas.items()) + ".",
    ]
    secciones.append(("Cobertura respecto del indice de URLs", cobertura))

    # ---------------- Tipos ----------------
    num = {}
    tipos = []
    for c in NUMERICAS:
        s = df[c]
        conv = pd.to_numeric(s.where(s != ""), errors="coerce")
        malos = (s != "") & conv.isna()
        num[c] = conv
        if malos.any():
            tipos.append(f"- `{c}`: {int(malos.sum())} valores no numericos (ej. {s[malos].iloc[0]!r}).")
            marcar(malos, "no_numerico", lambda r, c=c: f"{c}={r[c]!r}")
    for c in BOOLEANAS:
        malos = ~df[c].isin(["", "0", "1"])
        if malos.any():
            tipos.append(f"- `{c}`: {int(malos.sum())} valores fuera de 1/0 (ej. {df.loc[malos, c].iloc[0]!r}).")
            marcar(malos, "booleano_invalido", lambda r, c=c: f"{c}={r[c]!r}")
    json_malo = []
    claves_extra = {}
    for i, v in df["otras_caracteristicas"].items():
        if not v:
            continue
        try:
            d = json.loads(v)
            if not isinstance(d, dict):
                raise ValueError
            for k in d:
                claves_extra[k] = claves_extra.get(k, 0) + 1
        except ValueError:
            json_malo.append(i)
    if json_malo:
        tipos.append(f"- `otras_caracteristicas`: {len(json_malo)} filas con JSON invalido.")
        for i in json_malo:
            problemas.append((df.at[i, "id_aviso"], "json_invalido", df.at[i, "otras_caracteristicas"][:80]))
    monedas = df["moneda"].value_counts().to_dict()
    malas_mon = ~df["moneda"].isin(["UF", "CLP", "USD"])
    if malas_mon.any():
        tipos.append(f"- `moneda`: {int(malas_mon.sum())} valores fuera de UF/CLP/USD.")
        marcar(malas_mon, "moneda_invalida", lambda r: r["moneda"])
    if not tipos:
        tipos.append("- Todas las columnas numericas son numericas, las 1/0 solo tienen 1, 0 o vacio, "
                     "y `otras_caracteristicas` es JSON valido en todas las filas.")
    tipos.append(f"- Monedas: {monedas}.")
    secciones.append(("Tipos de datos", tipos))

    # ---------------- Completitud ----------------
    filas_comp = ["| Columna | Con dato | % |", "|---|---:|---:|"]
    vacias = []
    for c in sc.COLUMNAS:
        llenos = int((df[c] != "").sum())
        filas_comp.append(f"| `{c}` | {llenos} | {pct(llenos, n)} |")
        if llenos == 0:
            vacias.append(c)
    if vacias:
        filas_comp += ["", f"Columnas vacias en todas las filas: {', '.join(f'`{c}`' for c in vacias)}. "
                       "Si la etiqueta tampoco aparece en `otras_caracteristicas`, el sitio no la publica "
                       "(no es un error del scraper)."]
    secciones.append(("Completitud por columna", filas_comp))

    top_extra = sorted(claves_extra.items(), key=lambda kv: -kv[1])[:25]
    secciones.append(("Caracteristicas extra mas frecuentes (`otras_caracteristicas`)",
                      [f"- {k}: {v} avisos ({pct(v, n)})" for k, v in top_extra] or ["- (ninguna)"]))

    # ---------------- Rangos y coherencia ----------------
    p_uf, uf = num["precio_uf"], num["uf_usada"]
    precio = num["precio"]
    sup_u, sup_t = num["superficie_util_m2"], num["superficie_total_m2"]
    sup = sup_u.fillna(sup_t)
    reglas = [
        ("sin_precio_uf", p_uf.isna(), "Sin `precio_uf` (variable objetivo)",
         lambda r: f"precio={r['precio']} {r['moneda']}"),
        ("precio_uf_fuera_rango", (p_uf < 300) | (p_uf > 60000), "`precio_uf` fuera de 300 a 60.000 UF",
         lambda r: f"precio_uf={r['precio_uf']}"),
        ("precio_uf_incoherente_uf",
         (df["moneda"] == "UF") & p_uf.notna() & ((p_uf - precio).abs() > 0.5),
         "Moneda UF pero `precio_uf` distinto de `precio`", lambda r: f"{r['precio']} vs {r['precio_uf']}"),
        ("precio_uf_incoherente_clp",
         (df["moneda"] == "CLP") & p_uf.notna() & uf.notna() & (((precio / uf) - p_uf).abs() > 1),
         "Moneda CLP pero `precio_uf` distinto de `precio / uf_usada`",
         lambda r: f"{r['precio']}/{r['uf_usada']} vs {r['precio_uf']}"),
        ("sin_superficie", sup.isna(), "Sin superficie util ni total", lambda r: ""),
        ("superficie_fuera_rango", (sup < 15) | (sup > 600), "Superficie fuera de 15 a 600 m2",
         lambda r: f"util={r['superficie_util_m2']} total={r['superficie_total_m2']}"),
        ("superficie_no_positiva", (sup_u <= 0) | (sup_t <= 0), "Superficie util o total menor o igual a 0",
         lambda r: f"util={r['superficie_util_m2']} total={r['superficie_total_m2']}"),
        ("bodegas_fuera_rango", (num["bodegas"] < 0) | (num["bodegas"] > 10), "Bodegas fuera de 0 a 10",
         lambda r: r["bodegas"]),
        ("estacionamientos_fuera_rango", (num["estacionamientos"] < 0) | (num["estacionamientos"] > 10),
         "Estacionamientos fuera de 0 a 10", lambda r: r["estacionamientos"]),
        ("total_mucho_mayor_util", sup_t > 3 * sup_u, "Superficie total mayor que 3 veces la util",
         lambda r: f"util={r['superficie_util_m2']} total={r['superficie_total_m2']}"),
        ("util_mayor_total", sup_u > sup_t * 1.05, "Superficie util mayor que la total",
         lambda r: f"util={r['superficie_util_m2']} total={r['superficie_total_m2']}"),
        ("dormitorios_fuera_rango", (num["dormitorios"] < 0) | (num["dormitorios"] > 8),
         "Dormitorios fuera de 0 a 8", lambda r: r["dormitorios"]),
        ("banos_fuera_rango", (num["banos"] < 1) | (num["banos"] > 8), "Banos fuera de 1 a 8",
         lambda r: r["banos"]),
        ("piso_mayor_que_edificio", num["piso"] > num["pisos_edificio"],
         "`piso` mayor que `pisos_edificio`", lambda r: f"{r['piso']} > {r['pisos_edificio']}"),
        ("piso_fuera_rango", (num["piso"] < -3) | (num["piso"] > 40), "`piso` fuera de -3 a 40",
         lambda r: r["piso"]),
        ("antiguedad_fuera_rango", (num["antiguedad_anios"] < 0) | (num["antiguedad_anios"] > 100),
         "Antiguedad fuera de 0 a 100 anios", lambda r: r["antiguedad_anios"]),
        ("gc_igual_precio", num["gastos_comunes_clp"].notna() & (num["gastos_comunes_clp"] == precio),
         "Gastos comunes iguales al precio (error de tipeo)", lambda r: r["gastos_comunes_clp"]),
        ("gc_fuera_rango", (num["gastos_comunes_clp"] > 1_000_000) | (num["gastos_comunes_clp"] < 0),
         "Gastos comunes fuera de 0 a $1.000.000", lambda r: r["gastos_comunes_clp"]),
        ("sin_coordenadas", num["latitud"].isna() | num["longitud"].isna(), "Sin coordenadas", lambda r: ""),
        ("coord_fuera_biobio",
         num["latitud"].notna() & ~(num["latitud"].between(LAT_MIN, LAT_MAX)
                                    & num["longitud"].between(LON_MIN, LON_MAX)),
         "Coordenadas fuera de la Region del Biobio", lambda r: f"{r['latitud']},{r['longitud']}"),
        ("comuna_distinta_busqueda",
         (df["comuna_busqueda"] != "") & (df["comuna"].map(sc.normalizar) != df["comuna_busqueda"].map(sc.normalizar)),
         "`comuna` distinta de `comuna_busqueda` (aviso destacado de otra comuna)",
         lambda r: f"{r['comuna']} / {r['comuna_busqueda']}"),
    ]
    # Orientacion: las banderas deben coincidir con el texto
    flags_esp = df["orientacion_raw"].map(lambda v: sc.descomponer_orientacion(v)[1] if v else {})
    incoh_or = pd.Series(False, index=df.index)
    for c in ("orient_norte", "orient_sur", "orient_oriente", "orient_poniente"):
        esp = flags_esp.map(lambda d, c=c: str(d.get(c, "")) if d else "")
        incoh_or |= (df["orientacion_raw"] != "") & (esp != df[c])
    reglas.append(("orientacion_incoherente", incoh_or, "Banderas `orient_*` no calzan con `orientacion_raw`",
                   lambda r: r["orientacion_raw"]))

    filas_r = ["| Revision | Filas | % |", "|---|---:|---:|"]
    for tipo, mask, desc, det in reglas:
        mask = mask.fillna(False)
        k = marcar(mask, tipo, det)
        filas_r.append(f"| {desc} | {k} | {pct(k, n)} |")
    secciones.append(("Rangos y coherencia", filas_r))

    # ---------------- Duplicados probables ----------------
    clave = df[["latitud", "longitud", "superficie_util_m2", "piso", "dormitorios", "banos"]].astype(str).agg("|".join, axis=1)
    con_coord = (df["latitud"] != "") & (df["superficie_util_m2"] != "")
    dup_prob = clave.duplicated(keep=False) & con_coord
    k = marcar(dup_prob, "duplicado_probable", lambda r: f"grupo {r['latitud']},{r['longitud']} piso {r['piso']}")
    grupos = clave[dup_prob].nunique()
    secciones.append(("Duplicados probables", [
        f"- {k} filas ({pct(k, n)}) en {grupos} grupos comparten coordenadas, superficie util, piso, dormitorios "
        "y banos: probablemente el mismo departamento publicado por varios corredores. No se borran; "
        "decidir al limpiar."]))

    # ---------------- Estadisticos ----------------
    desc_cols = ["precio_uf", "superficie_util_m2", "superficie_total_m2", "dormitorios", "banos",
                 "estacionamientos", "bodegas", "piso", "pisos_edificio", "antiguedad_anios", "gastos_comunes_clp"]
    d = pd.DataFrame({c: num[c] for c in desc_cols}).describe(percentiles=[.05, .5, .95]).T
    filas_d = ["| Variable | n | media | p5 | mediana | p95 | min | max |", "|---|---:|---:|---:|---:|---:|---:|---:|"]
    for c, r in d.iterrows():
        filas_d.append(f"| `{c}` | {int(r['count'])} | {r['mean']:,.1f} | {r['5%']:,.1f} | {r['50%']:,.1f} | "
                       f"{r['95%']:,.1f} | {r['min']:,.1f} | {r['max']:,.1f} |")
    uf_m2 = (p_uf / sup_u).where(sup_u > 0)
    filas_d.append("")
    filas_d.append(f"UF/m2 util: mediana {uf_m2.median():,.1f}, p5 {uf_m2.quantile(.05):,.1f}, "
                   f"p95 {uf_m2.quantile(.95):,.1f}.")
    por_comuna = df.assign(uf_m2=uf_m2).groupby("comuna").agg(n=("id_aviso", "size"), uf_m2=("uf_m2", "median"))
    por_comuna = por_comuna.sort_values("n", ascending=False)
    filas_d += ["", "| Comuna | Avisos | Mediana UF/m2 |", "|---|---:|---:|"]
    for c, r in por_comuna.iterrows():
        filas_d.append(f"| {c or '(vacia)'} | {int(r['n'])} | {r['uf_m2']:,.1f} |")
    secciones.append(("Estadisticos descriptivos", filas_d))

    return n, secciones, pd.DataFrame(problemas, columns=["id_aviso", "problema", "detalle"])


def main(argv=None):
    p = argparse.ArgumentParser(description="Auditoria del dataset de departamentos")
    p.add_argument("--datos", default="data/raw/departamentos_biobio.csv")
    p.add_argument("--reporte", default="docs/auditoria_datos.md")
    p.add_argument("--problemas", default="", help="CSV con los problemas por aviso (opcional)")
    a = p.parse_args(argv)
    base = os.path.splitext(a.datos)[0]
    n, secciones, problemas = auditar(a.datos, base + "_urls.csv", base + "_descartados.txt")

    lineas = [f"# Auditoria de `{os.path.basename(a.datos)}`", "",
              f"Generado el {date.today():%Y-%m-%d} con `src/auditar_dataset.py`. "
              "Las revisiones no modifican los datos: marcan lo que hay que limpiar antes de modelar.", ""]
    for titulo, cuerpo in secciones:
        lineas += [f"## {titulo}", "", *cuerpo, ""]
    os.makedirs(os.path.dirname(os.path.abspath(a.reporte)), exist_ok=True)
    with open(a.reporte, "w", encoding="utf-8") as f:
        f.write("\n".join(lineas))
    if a.problemas:
        problemas.to_csv(a.problemas, index=False, encoding="utf-8-sig")
    print(f"{n} filas auditadas. Reporte: {a.reporte}"
          + (f". Problemas por aviso: {a.problemas} ({len(problemas)})" if a.problemas else ""))


if __name__ == "__main__":
    main()
