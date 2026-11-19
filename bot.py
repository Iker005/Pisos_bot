"""
Bot de pisos: revisa varias webs de alquiler y envía al grupo de Telegram
los anuncios nuevos que cumplen los filtros de config.py.

Uso:
    python bot.py            -> funciona sin parar (revisa cada X minutos)
    python bot.py --una-vez  -> hace una sola vuelta y termina
    python bot.py --prueba   -> solo envía un mensaje de prueba al grupo
"""

from __future__ import annotations

import html
import json
import os
import logging
import random
import re
import sys
import time
import unicodedata
from pathlib import Path
from urllib.parse import urlparse

import requests
from playwright.sync_api import sync_playwright

import importlib

# Perfil de búsqueda: "python bot.py --perfil amigos" usa config_amigos.py
# (sin --perfil se usa config.py, vuestra búsqueda de siempre).
PERFIL = next((sys.argv[i + 1] for i, a in enumerate(sys.argv[:-1]) if a == "--perfil"), None)
config = importlib.import_module(f"config_{PERFIL}" if PERFIL else "config")

BASE = Path(__file__).parent
_SUFIJO = f"_{PERFIL}" if PERFIL else ""
ARCHIVO_VISTOS = BASE / f"vistos{_SUFIJO}.txt"  # un piso por línea
ARCHIVO_HISTORICO = BASE / f"historico{_SUFIJO}.json"
PERFIL_NAVEGADOR = BASE / f"perfil_navegador{_SUFIJO}"  # uno por búsqueda, para poder lanzarlas a la vez

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(message)s",
    datefmt="%d/%m %H:%M",
)
log = logging.getLogger("pisos")

# Cómo es el enlace de un anuncio en cada web (de ahí sacamos su ID).
PATRONES = {
    "idealista": re.compile(r"idealista\.com/inmueble/(\d+)"),
    "fotocasa": re.compile(r"fotocasa\.es/es/alquiler/[^?#]*?/(\d{6,})/d"),
    "pisos.com": re.compile(r"pisos\.com/alquilar/[^?#]*?-(\d+_\d+)/?"),
    # formato nuevo (.../vigo/<código>/d) y el antiguo (...-i123456.htm)
    "habitaclia": re.compile(r"habitaclia\.com/alquiler/[^?#]*?/([0-9a-f-]{36})/d"
                             r"|habitaclia\.com/alquiler-[^?#]*?-i(\d{6,})\.htm"),
    "milanuncios": re.compile(r"milanuncios\.com/[^?#]*?-(\d{6,})\.htm"),
    "wallapop": re.compile(r"wallapop\.com/item/([^?#/]+)"),
}

NOMBRES_WEB = {
    "idealista": "Idealista",
    "fotocasa": "Fotocasa",
    "pisos.com": "Pisos.com",
    "habitaclia": "Habitaclia",
    "milanuncios": "Milanuncios",
    "wallapop": "Wallapop",
}

# Código que se ejecuta dentro de la página: recoge cada enlace junto con
# el texto y la foto de la "tarjeta" del anuncio en la que está.
JS_EXTRAER = """
() => {
  const out = [];
  for (const a of document.querySelectorAll('a[href]')) {
    let el = a, card = null;
    for (let i = 0; i < 8 && el; i++) {
      const t = el.innerText || '';
      if (t.includes('€') && t.length > 30) { card = el; break; }
      el = el.parentElement;
    }
    if (!card) continue;
    const art = a.closest('article');
    if (art && (art.innerText || '').length < 2500) card = art;
    const t = card.innerText;
    if (t.length > 2500) continue;
    let img = '';
    for (const im of card.querySelectorAll('img')) {
      const s = im.currentSrc || im.src || im.getAttribute('data-src')
             || im.getAttribute('data-ondemand-img') || '';
      if (s.startsWith('http') && !s.includes('logo')) { img = s; break; }
    }
    out.push({href: a.href, text: t, img: img});
  }
  return out;
}
"""


# ----------------------------------------------------------------- utilidades
def normalizar(texto: str) -> str:
    """minúsculas y sin tildes, para comparar zonas."""
    texto = unicodedata.normalize("NFD", texto.lower())
    return "".join(c for c in texto if unicodedata.category(c) != "Mn")


def detectar_web(url: str) -> str | None:
    host = urlparse(url).netloc.lower()
    for clave in PATRONES:
        if clave.replace(".com", "") in host:
            return clave
    return None


def sacar_precio(texto: str) -> int | None:
    """Primer precio en € del anuncio (admite 1.200 €, 650 €, 266,30 €)."""
    # Solo punto o espacio normal como separador de miles (no saltos de línea,
    # para que el "1/7" del contador de fotos no se pegue al precio).
    patron = r"(?<![\d/,.])(\d{1,3}(?:[. \u00a0]\d{3})+|\d+)(?:,\d{1,2})?[ \u00a0]*€"
    for m in re.finditer(patron, texto):
        valor = int(re.sub(r"[. \u00a0]", "", m.group(1)))
        if valor > 0:
            return valor
    return None


def sacar_metros(texto: str) -> int | None:
    m = re.search(r"(\d{2,4})\s*m(?:²|2)(?![a-z])", texto, re.IGNORECASE)
    return int(m.group(1)) if m else None


def sacar_habitaciones(texto: str) -> int | None:
    m = re.search(r"(\d+)\s*(?:hab|dorm)", texto, re.IGNORECASE)
    return int(m.group(1)) if m else None


def sacar_titulo(texto: str) -> str:
    for linea in texto.splitlines():
        linea = linea.strip()
        if len(linea) > 12 and "€" not in linea and re.search(r"[a-zA-Z]{3}", linea):
            return linea[:150]
    return "Piso en alquiler"


def cargar_vistos() -> set:
    vistos = set()
    try:
        vistos |= {l.strip() for l in ARCHIVO_VISTOS.read_text().splitlines() if l.strip()}
    except Exception:
        pass
    try:  # formato antiguo (vistos.json)
        vistos |= set(json.loads(ARCHIVO_VISTOS.with_suffix(".json").read_text()))
    except Exception:
        pass
    return vistos


def guardar_vistos(vistos: set) -> None:
    ARCHIVO_VISTOS.write_text("\n".join(sorted(vistos)) + "\n")


# ------------------------------------------------------------------- filtros
MUNICIPIOS_FUERA = [
    "cangas", "moana", "bueu", "nigran", "baiona", "gondomar", "redondela",
    "porrino", "budino", "soutomaior", "vilaboa", "salceda", "ponteareas",
    "tui", "sabaris", "ramallosa", "panxon", "coiro", "o hio", "chapela",
    "val minor", "pontevedra capital",
]

PALABRAS_EXCLUIDAS = [
    "alquiler temporal", "por temporadas", "temporada de invierno",
    "alquiler de temporada", "curso escolar", "solo estudiantes",
    "alquilamos habitaciones", "alquiler de habitaciones",
]

def evaluar(anuncio: dict) -> dict | None:
    """Devuelve el anuncio enriquecido si pasa los filtros, o None."""
    return evaluar_con_motivo(anuncio)[0]


def evaluar_con_motivo(anuncio: dict) -> tuple[dict | None, str]:
    texto = anuncio["text"]
    norm = normalizar(texto)

    for zona in config.ZONAS_EXCLUIDAS:
        if re.search(rf"\b{re.escape(zona)}\b", norm):
            return None, f"zona excluida ({zona})"

    obligatorio = getattr(config, "TEXTO_OBLIGATORIO", ["vigo"])
    # Wallapop no pone la ciudad en la tarjeta (la búsqueda ya va por zona)
    if anuncio.get("web") != "wallapop" and obligatorio and not any(re.search(rf"\b{re.escape(t)}\b", norm) for t in obligatorio):
        return None, "no es de Vigo"

    # Muchos anuncios de fuera dicen "a 10 min de Vigo" o "vistas a la ría de
    # Vigo", así que también descartamos los que nombran otro municipio.
    for lugar in getattr(config, "MUNICIPIOS_FUERA", MUNICIPIOS_FUERA):
        if re.search(rf"\b{re.escape(lugar)}\b", norm):
            return None, f"es de {lugar}"

    for palabra in getattr(config, "PALABRAS_EXCLUIDAS", PALABRAS_EXCLUIDAS):
        if palabra in norm:
            return None, f"'{palabra}'"

    # Alquileres temporales: "temporal", "temporada", "por meses", "hasta junio"...
    # (pero NO "larga temporada", que es justo lo que buscáis)
    sin_larga = re.sub(r"larga\s+(temporada|duracion)", "", norm)
    # Habitaciones sueltas / pisos compartidos (pero no "piso de 1 habitación")
    if re.search(r"\b(alquil[oa]|se alquila|alquilamos|alquiler de|alquiler)\s+(una\s+)?habitacion\b"
                 r"|^\s*habitacion\b|\bhabitacion (en piso|en casa|en apartamento|en vivienda|para (chica|chico|chicas|chicos|estudiantes?|personas?|trabajador))\b"
                 r"|\bpiso compartido\b|\bcompartir piso\b|\bhabitaciones (sueltas|individuales)\b",
                 sin_larga, re.MULTILINE):
        return None, "es una habitación"

    if re.search(r"\bventa\b|\bse vende\b|\ben venta\b", sin_larga):
        return None, "es una venta"

    if re.search(r"\btempora(l|les|da|das)\b|\bvaca(c|s)ional\b|\bvacaciones\b|\bturistic[oa]s?\b|\bpor (dias|noches|semanas)\b|\bpor meses\b"
                 r"|\bhasta (junio|julio|mayo|verano)\b|\bde (septiembre|octubre) a (junio|julio)\b"
                 r"|\bestudiantes\b|\bcurso (escolar|academico|20\d\d)\b", sin_larga):
        return None, "alquiler temporal"

    precio = sacar_precio(texto)
    metros = sacar_metros(texto)
    habs = sacar_habitaciones(texto)

    if precio is not None and precio > config.PRECIO_MAXIMO:
        return None, f"precio {precio} €"
    if precio is not None and precio < getattr(config, "PRECIO_MINIMO", 400):
        return None, f"precio {precio} € (seguramente habitación)"
    if metros is not None and metros < config.METROS_MINIMOS:
        return None, f"{metros} m²"
    maximas = getattr(config, "HABITACIONES_MAXIMAS", None)
    if habs is not None and maximas is not None and habs > maximas:
        return None, f"{habs} hab (máximo {maximas})"
    if habs is not None and habs < config.HABITACIONES_MINIMAS:
        return None, f"{habs} hab"

    avisos = [msg for zona, msg in config.ZONAS_AVISO.items()
              if re.search(rf"\b{re.escape(zona)}\b", norm)]
    preferida = next((z for z in config.ZONAS_PREFERIDAS
                      if re.search(rf"\b{re.escape(z)}\b", norm)), None)
    extras = []
    for palabra, etiqueta in config.EXTRAS.items():
        if palabra in norm and etiqueta not in extras:
            extras.append(etiqueta)

    return ({**anuncio, "precio": precio, "metros": metros, "habs": habs,
             "avisos": avisos, "preferida": preferida, "extras": extras,
             "titulo": sacar_titulo(texto)}, "OK")


# ------------------------------------------------------------------ telegram
def telegram(metodo: str, datos: dict) -> dict:
    url = f"https://api.telegram.org/bot{config.TELEGRAM_TOKEN}/{metodo}"
    try:
        r = requests.post(url, data=datos, timeout=30)
        return r.json()
    except Exception as e:
        return {"ok": False, "error": str(e)}


def formatear(a: dict, marcar: bool = False) -> str:
    lineas = []
    if marcar:
        lineas.append("🆕 <b>Nuevo</b>" if a.get("nuevo") else "🔁 Sigue disponible")
    if a["preferida"]:
        lineas.append(f"⭐ <b>ZONA PREFERIDA ({a['preferida'].title()})</b>")
    lineas.append(f"🏠 <b>{html.escape(a['titulo'])}</b>")
    datos = [f"💶 {a['precio']} €/mes" if a["precio"] else "💶 precio ?"]
    if a["metros"]:
        datos.append(f"📐 {a['metros']} m²")
    if a["habs"]:
        datos.append(f"🛏 {a['habs']} hab")
    lineas.append(" · ".join(datos))
    ideal = getattr(config, "PRECIO_IDEAL", 700)
    if a["precio"] and a["precio"] > ideal:
        lineas.append(f"💸 Se pasa de {ideal} € (+{a['precio'] - ideal} €)")
    if a["extras"]:
        lineas.append(" · ".join(a["extras"]))
    for aviso in a["avisos"]:
        lineas.append(f"⚠️ {html.escape(aviso)}")
    lineas.append(f'🔗 <a href="{html.escape(a["href"])}">Ver en {NOMBRES_WEB[a["web"]]}</a>')
    return "\n".join(lineas)[:1000]


def enviar(a: dict, marcar: bool = False) -> bool:
    texto = formatear(a, marcar)
    if a.get("img"):
        r = telegram("sendPhoto", {"chat_id": config.TELEGRAM_CHAT_ID,
                                   "photo": a["img"], "caption": texto,
                                   "parse_mode": "HTML"})
        if r.get("ok"):
            return True
    r = telegram("sendMessage", {"chat_id": config.TELEGRAM_CHAT_ID,
                                 "text": texto, "parse_mode": "HTML"})
    if not r.get("ok"):
        log.warning("Telegram ha dado error: %s", r)
    return bool(r.get("ok"))


# ------------------------------------------------------------------ navegador
def abrir_navegador(p):
    opciones = dict(user_data_dir=str(PERFIL_NAVEGADOR),
                    headless=config.OCULTAR_NAVEGADOR or bool(os.environ.get("CI")),
                    locale="es-ES",
                    viewport={"width": 1280, "height": 900})
    try:  # Si tienes Google Chrome instalado se usa ese (lo bloquean menos)
        return p.chromium.launch_persistent_context(channel="chrome", **opciones)
    except Exception:
        return p.chromium.launch_persistent_context(**opciones)


def revisar_busqueda(pagina, url: str) -> list[dict]:
    web = detectar_web(url)
    if not web:
        log.warning("No reconozco la web de %s, la salto", url)
        return []
    pagina.goto(url, wait_until="domcontentloaded", timeout=60000)
    pagina.wait_for_timeout(random.randint(3000, 5000))
    for _ in range(6):  # bajar para que carguen todos los anuncios
        pagina.mouse.wheel(0, 2500)
        pagina.wait_for_timeout(random.randint(600, 1200))

    if DIAGNOSTICO:
        (BASE / f"debug_{web}.html").write_text(pagina.content(), encoding="utf-8")

    anuncios, ids = [], set()
    for item in pagina.evaluate(JS_EXTRAER):
        m = PATRONES[web].search(item["href"])
        if not m:
            continue
        clave = f"{web}:{next(g for g in m.groups() if g)}"
        if clave in ids:
            continue
        ids.add(clave)
        anuncios.append({**item, "web": web, "clave": clave,
                         "href": item["href"].split("?")[0]})

    if not anuncios:
        contenido = normalizar(pagina.content()[:20000])
        if any(p in contenido for p in ("captcha", "robot", "datadome", "acceso denegado", "pardon")):
            log.warning("%s: parece que pide captcha o nos ha bloqueado", NOMBRES_WEB[web])
        else:
            log.warning("%s: no he encontrado anuncios (revisa la URL)", NOMBRES_WEB[web])
        try:  # pista de qué página está viendo (útil en GitHub, donde no se ve)
            texto = re.sub(r"\s+", " ", pagina.inner_text("body"))[:400]
            log.warning("   título: %s | url final: %s", pagina.title(), pagina.url)
            log.warning("   texto: %s", texto)
        except Exception:
            pass
    else:
        log.info("%s: %d anuncios en la página", NOMBRES_WEB[web], len(anuncios))
    return anuncios


def _media(valores: list) -> float | None:
    return sum(valores) / len(valores) if valores else None


def _eur_m2(pisos: list) -> float | None:
    return _media([a["precio"] / a["metros"] for a in pisos if a["precio"] and a["metros"]])


def _tendencia(actual: float | None, anterior: float | None, unidad: str, dec: int = 0) -> str:
    if actual is None or anterior is None:
        return ""
    dif = actual - anterior
    if abs(dif) < (0.05 if dec else 1):
        return " (= que la semana pasada)"
    flecha = "▲" if dif > 0 else "▼"
    return f" ({flecha} {abs(dif):.{dec}f}{unidad} vs semana pasada)".replace(".", ",")


def resumen_semanal(pisos: list) -> str:
    """Mensaje de resumen con estadísticas de precios y comparación semanal."""
    fecha = time.strftime("%d/%m")
    titulo = getattr(config, "NOMBRE_BUSQUEDA", "Búsqueda semanal")
    if not pisos:
        return f"📋 <b>{titulo} {fecha}</b>\nEsta semana no hay pisos que encajen."

    try:
        historico = json.loads(ARCHIVO_HISTORICO.read_text())
    except Exception:
        historico = []
    anterior = historico[-1] if historico else {}

    precios = [a["precio"] for a in pisos if a["precio"]]
    media = _media(precios)
    m2 = _eur_m2(pisos)
    pref = [a for a in pisos if a["preferida"]]
    resto = [a for a in pisos if not a["preferida"]]
    ideal = getattr(config, "PRECIO_IDEAL", 700)
    dentro = sum(1 for p in precios if p <= ideal)
    n_nuevos = sum(a["nuevo"] for a in pisos)

    def fmt(x, dec=0):
        return f"{x:.{dec}f}".replace(".", ",") if x is not None else "?"

    lineas = [f"📋 <b>{titulo} {fecha}</b>",
              f"🏠 {len(pisos)} pisos ({n_nuevos} nuevos) · {dentro} dentro de {ideal} €"]
    if precios:
        lineas.append(f"💶 Precio medio: <b>{fmt(media)} €</b>"
                      + _tendencia(media, anterior.get("media"), " €"))
        lineas.append(f"⬇️ Más barato: {min(precios)} € · ⬆️ Más caro: {max(precios)} €")
    if m2:
        lineas.append(f"📐 Precio por m²: <b>{fmt(m2, 1)} €/m²</b>"
                      + _tendencia(m2, anterior.get("m2"), " €/m²", 1))
    etiqueta = "/".join(z.title() for z in config.ZONAS_PREFERIDAS) or "Zonas preferidas"
    for nombre, grupo in ((f"⭐ {etiqueta}", pref), ("🏙️ Resto de Vigo", resto)):
        pg = [a["precio"] for a in grupo if a["precio"]]
        if grupo:
            lineas.append(f"{nombre}: {len(grupo)} piso{'s' if len(grupo) != 1 else ''} · media {fmt(_media(pg))} € · "
                          f"{fmt(_eur_m2(grupo), 1)} €/m²")
        else:
            lineas.append(f"{nombre}: ninguno esta semana")

    if leidos_por_web:
        lineas.append(f"🌐 {_estado_webs()}")

    historico.append({"fecha": time.strftime("%Y-%m-%d"), "pisos": len(pisos),
                      "media": media, "m2": m2})
    try:
        ARCHIVO_HISTORICO.write_text(json.dumps(historico[-104:], indent=1))
    except Exception:
        pass
    return "\n".join(lineas)


fallos_seguidos: dict[str, int] = {}
leidos_por_web: dict[str, int] = {}


def NOMBRE_WEB_O(web: str) -> str:
    return NOMBRES_WEB.get(web, web)
DIAGNOSTICO = "--diagnostico" in sys.argv


def diagnostico() -> None:
    """Una vuelta sin enviar nada: muestra qué lee y por qué descarta."""
    with sync_playwright() as p:
        nav = abrir_navegador(p)
        pagina = nav.pages[0] if nav.pages else nav.new_page()
        for url in config.BUSQUEDAS:
            try:
                encontrados = revisar_busqueda(pagina, url)
            except Exception as e:
                print(f"ERROR en {url}: {e}")
                continue
            for c in encontrados[:12]:
                _, motivo = evaluar_con_motivo(c)
                t = c["text"]
                print(f"[{NOMBRES_WEB[c['web']]}] precio={sacar_precio(t)} "
                      f"m2={sacar_metros(t)} hab={sacar_habitaciones(t)} -> {motivo}")
                print("     texto: " + " | ".join(t.split("\n"))[:160])
            print()
        nav.close()
    print("Se han guardado los archivos debug_*.html en la carpeta.")


def mensaje_html(texto: str) -> bool:
    """Envía un mensaje con formato; si Telegram lo rechaza, lo manda sin formato."""
    r = telegram("sendMessage", {"chat_id": config.TELEGRAM_CHAT_ID,
                                 "parse_mode": "HTML", "text": texto})
    if not r.get("ok"):
        log.warning("Telegram rechazó el mensaje: %s", r)
        r = telegram("sendMessage", {"chat_id": config.TELEGRAM_CHAT_ID,
                                     "text": re.sub(r"<[^>]+>", "", texto)})
    return bool(r.get("ok"))


def _desde() -> str:
    return "GitHub" if os.environ.get("CI") else "Mac"


def _hora() -> str:
    # GitHub funciona en hora UTC: la pasamos a la de España
    try:
        from zoneinfo import ZoneInfo
        from datetime import datetime
        return datetime.now(ZoneInfo("Europe/Madrid")).strftime("%d/%m %H:%M")
    except Exception:
        return time.strftime("%d/%m %H:%M")


def separador() -> str:
    """Mensaje 'en blanco' que separa una búsqueda de la anterior."""
    blanco = "\u2800\n" * getattr(config, "LINEAS_SEPARADOR", 10)
    titulo = getattr(config, "NOMBRE_BUSQUEDA", "Nueva búsqueda")
    modo = "semanal" if "--una-vez" in sys.argv else "nuevos"
    return (f"{blanco}━━━━━━━━━━━━━━━━━━\n"
            f"🔎 <b>{titulo}</b> · {_hora()}\n"
            f"<i>({modo}, desde el {_desde()})</i>")


def _estado_webs() -> str:
    return " · ".join(f"{NOMBRE_WEB_O(w)} {'✅' if n else '❌'}"
                      for w, n in leidos_por_web.items())


def resumen_busqueda(pisos: list) -> str:
    """Resumen corto al final de una búsqueda de pisos nuevos."""
    lineas = [f"📋 <b>Fin de la búsqueda</b> · {_hora()}",
              f"🆕 {len(pisos)} piso{'s' if len(pisos) != 1 else ''} "
              f"nuevo{'s' if len(pisos) != 1 else ''}"]
    precios = [a["precio"] for a in pisos if a["precio"]]
    if precios:
        media = round(sum(precios) / len(precios))
        rango = f" ({min(precios)}–{max(precios)} €)" if len(precios) > 1 else ""
        lineas.append(f"💶 Precio medio: <b>{media} €</b>{rango}")
    ideal = getattr(config, "PRECIO_IDEAL", 700)
    dentro = sum(1 for p in precios if p <= ideal)
    if precios:
        lineas.append(f"✅ {dentro} dentro de {ideal} €")
    pref = sum(1 for a in pisos if a["preferida"])
    if pref:
        zonas = "/".join(z.title() for z in config.ZONAS_PREFERIDAS)
        lineas.append(f"⭐ {pref} en {zonas}")
    if leidos_por_web:
        lineas.append(f"🌐 {_estado_webs()}")
    return "\n".join(lineas)


def vuelta() -> None:
    vistos = cargar_vistos()
    candidatos = []
    with sync_playwright() as p:
        nav = abrir_navegador(p)
        pagina = nav.pages[0] if nav.pages else nav.new_page()
        for url in config.BUSQUEDAS:
            try:
                encontrados = revisar_busqueda(pagina, url)
            except Exception as e:
                log.warning("Error en %s: %s", url, e)
                encontrados = []
            web = detectar_web(url) or url
            fallos_seguidos[web] = 0 if encontrados else fallos_seguidos.get(web, 0) + 1
            if fallos_seguidos[web] == 6:  # unas 2 horas sin resultados
                telegram("sendMessage", {"chat_id": config.TELEGRAM_CHAT_ID,
                         "text": f"🤖 Aviso: llevo un rato sin poder leer {NOMBRES_WEB.get(web, web)}."})
            leidos_por_web[web] = len(encontrados)
            candidatos.extend(encontrados)
            time.sleep(random.uniform(2, 5))
        nav.close()

    # Modo semanal (--una-vez): envía TODOS los que encajan, marcando si son
    # nuevos o ya se habían enviado. Modo continuo: solo los nuevos.
    semanal = "--una-vez" in sys.argv
    validos, claves = [], set()
    for c in candidatos:
        if c["clave"] in claves:
            continue
        claves.add(c["clave"])
        evaluado = evaluar(c)  # si no cumple, se vuelve a revisar la próxima vez
        if evaluado is None:
            continue
        firma = (evaluado["precio"], evaluado["metros"], evaluado["habs"])
        if None not in firma:  # mismo piso anunciado en dos webs
            if firma in claves:
                continue
            claves.add(firma)
        evaluado["nuevo"] = c["clave"] not in vistos
        if semanal or evaluado["nuevo"]:
            validos.append(evaluado)

    if semanal:
        validos.sort(key=lambda a: (not a["nuevo"], not a["preferida"]))
        limite = getattr(config, "MAX_ENVIOS_SEMANAL", 40)
    else:
        validos.sort(key=lambda a: not a["preferida"])
        limite = config.MAX_ENVIOS_POR_VUELTA
    a_enviar = validos[:limite]

    # Sin pisos que mandar (búsqueda normal) -> no se manda nada al grupo.
    if not a_enviar and not semanal:
        guardar_vistos(vistos)
        log.info("Vuelta terminada: 0 anuncios enviados (no se manda nada al grupo)")
        return

    mensaje_html(separador())
    time.sleep(1.5)

    enviados = []
    for a in a_enviar:
        if enviar(a, marcar=semanal):
            vistos.add(a["clave"])
            enviados.append(a)
            time.sleep(1.5)
    guardar_vistos(vistos)

    # El resumen va al final, para que sea lo último que se vea
    resumen = resumen_semanal(validos) if semanal else resumen_busqueda(enviados)
    ok = mensaje_html(resumen)
    log.info("Resumen %s", "enviado ✅" if ok else "NO enviado")
    enviados = len(enviados)
    log.info("Vuelta terminada: %d anuncios enviados", enviados)
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        try:
            with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as f:
                f.write(f"### {getattr(config, 'NOMBRE_BUSQUEDA', 'Vuestra búsqueda')}\n")
                for web, n in sorted(leidos_por_web.items()):
                    f.write(f"- {NOMBRE_WEB_O(web)}: {'✅ ' + str(n) + ' anuncios' if n else '❌ no se pudo leer'}\n")
                f.write(f"- Enviados al grupo: **{enviados}**\n\n")
        except Exception:
            pass


def main() -> None:
    if not config.TELEGRAM_TOKEN or "PEGA_AQUI" in config.TELEGRAM_TOKEN \
            or "PEGA_AQUI" in str(config.TELEGRAM_CHAT_ID):
        sys.exit("Falta el TOKEN (secreto TELEGRAM_TOKEN en GitHub) o el CHAT_ID en config.py")

    if "--prueba" in sys.argv:
        r = telegram("sendMessage", {"chat_id": config.TELEGRAM_CHAT_ID,
                     "text": "🤖 ¡Hola! El bot de pisos está conectado al grupo."})
        print("Mensaje enviado ✅" if r.get("ok") else f"Error: {r}")
        return

    if DIAGNOSTICO:
        diagnostico()
        return

    while True:
        try:
            vuelta()
        except Exception:
            log.exception("Fallo inesperado en la vuelta")
        if "--una-vez" in sys.argv or "--nuevos" in sys.argv:
            break
        espera = max(300, config.INTERVALO_MINUTOS * 60 + random.randint(-120, 180))
        log.info("Próxima revisión en %d minutos", espera // 60)
        time.sleep(espera)


if __name__ == "__main__":
    main()
