# ============================================================
#  CONFIGURACIÓN DEL BOT DE PISOS  (versión para GitHub)
# ============================================================
# ¡OJO! Este repositorio es PÚBLICO: NO escribas aquí el token de Telegram.
# En GitHub está guardado como secreto (TELEGRAM_TOKEN). En el Mac se lee del
# archivo token.txt de esta carpeta, que NUNCA se sube (está en .gitignore).

import os
from pathlib import Path

EN_GITHUB = bool(os.environ.get("CI"))

# --- Búsqueda automática en GitHub (cada 30 min) ----------------
# False = GitHub NO busca para vosotros (desde el Mac sí podéis lanzarla a mano).
# Cuando volváis a buscar piso, cambiadlo a True.
BUSCAR_EN_GITHUB = False

# --- Telegram -------------------------------------------------
_token_txt = Path(__file__).with_name("token.txt")
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN") or (
    _token_txt.read_text().strip() if _token_txt.exists() else "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "-1003964340602")

# --- Filtros --------------------------------------------------
PRECIO_MAXIMO = 800        # € al mes (lo que pase de PRECIO_IDEAL sale con 💸)
PRECIO_IDEAL = 700
METROS_MINIMOS = 60        # m²
HABITACIONES_MINIMAS = 1

# Si el texto del anuncio menciona alguna de estas palabras, NO se envía.
# (sin tildes, en minúsculas)
ZONAS_EXCLUIDAS = [
    "torrecedeira",
    "puerto",
    "porto",
    "berbes",
]

# Si menciona alguna de estas, se envía pero con un aviso.
ZONAS_AVISO = {
    "teis": "Es Teis: comprueba que no sea la parte baja",
}

# Zonas preferidas: salen marcadas con ⭐ arriba del mensaje.
ZONAS_PREFERIDAS = [
    "lavadores",
    "camelias",
]

# Extras que se marcan si aparecen en el anuncio.
EXTRAS = {
    "garaje": "🚗 Garaje",
    "plaza de garaje": "🚗 Garaje",
    "parking": "🚗 Garaje",
    "trastero": "📦 Trastero",
}

# --- Búsquedas ------------------------------------------------
# Para desactivar una web, pon # delante de su línea.
# Idealista y Milanuncios bloquean al bot, por eso no están.
BUSQUEDAS = [
    "https://www.pisos.com/alquiler-residencial/pisos-vigo/desde-60-m2/hasta-800/",
    "https://www.habitaclia.com/alquiler/viviendas/pontevedra-provincia/vigo/s?maxPrice=800&minSurface=60&minRooms=1",
]

# Fotocasa y Wallapop bloquean a los servidores de GitHub (error 403), así
# que solo se buscan cuando el bot se lanza desde el Mac.
if not EN_GITHUB:
    BUSQUEDAS += [
        "https://www.fotocasa.es/es/alquiler/viviendas/vigo/todas-las-zonas/l?maxPrice=800&minSurface=60&sortType=publicationDate",
        # Wallapop con la ubicación de Vigo puesta en la URL
        "https://es.wallapop.com/search?keywords=pisos+alquiler&latitude=42.2328&longitude=-8.7226&distance_in_km=10&order_by=newest",
    ]

# --- Funcionamiento -------------------------------------------
INTERVALO_MINUTOS = 30
# En el Mac el navegador se abre a la vista: Fotocasa y Wallapop bloquean el
# navegador oculto. En GitHub siempre va oculto (no hay pantalla).
OCULTAR_NAVEGADOR = EN_GITHUB
MAX_ENVIOS_POR_VUELTA = 15
MAX_ENVIOS_SEMANAL = 40
