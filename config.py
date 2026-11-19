# ============================================================
#  CONFIGURACIÓN DEL BOT DE PISOS  (versión para GitHub)
# ============================================================
# ¡OJO! Este repositorio es PÚBLICO: NO escribas aquí el token de Telegram.
# El token se guarda en GitHub como secreto (Settings → Secrets → TELEGRAM_TOKEN).

import os

# --- Telegram -------------------------------------------------
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "")
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
# (Idealista y Milanuncios bloquean al bot, por eso no están.)
BUSQUEDAS = [
    "https://www.fotocasa.es/es/alquiler/viviendas/vigo/todas-las-zonas/l?maxPrice=800&minSurface=60&sortType=publicationDate",
    "https://www.pisos.com/alquiler-residencial/pisos-vigo/desde-60-m2/hasta-800/",
    "https://www.habitaclia.com/alquiler/viviendas/pontevedra-provincia/vigo/s?maxPrice=800&minSurface=60&minRooms=1",
    # Wallapop con la ubicación de Vigo puesta en la URL (los servidores de
    # GitHub no están en Vigo, así que sin esto buscaría en otra ciudad).
    "https://es.wallapop.com/search?keywords=pisos+alquiler&latitude=42.2328&longitude=-8.7226&distance_in_km=10&order_by=newest",
]

# --- Funcionamiento -------------------------------------------
INTERVALO_MINUTOS = 30
OCULTAR_NAVEGADOR = True
MAX_ENVIOS_POR_VUELTA = 15
MAX_ENVIOS_SEMANAL = 40
