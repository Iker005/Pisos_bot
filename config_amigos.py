# ============================================================
#  BÚSQUEDA PARA LOS AMIGOS  (2 o 3 habitaciones)
# ============================================================
# Coge TODO de config.py (token, grupo, webs, precio, zonas...) y aquí
# solo se cambia lo que es distinto. Si quieres cambiar algo más para
# ellos, copia la línea de config.py aquí debajo y cambia el valor.

import os

from config import *  # noqa: F401,F403

NOMBRE_BUSQUEDA = "Búsqueda amigos (2-3 hab)"

# GitHub busca para ellos cada 30 minutos (False para pararlo)
BUSCAR_EN_GITHUB = True

HABITACIONES_MINIMAS = 2
HABITACIONES_MAXIMAS = 3

# Grupo de Telegram de los amigos: en GitHub se pone como variable
# AMIGOS_CHAT_ID (Settings → Secrets and variables → Actions → Variables).
# Mientras no exista, sus pisos llegan a vuestro grupo.
TELEGRAM_CHAT_ID = os.environ.get("AMIGOS_CHAT_ID") or TELEGRAM_CHAT_ID  # noqa: F405

# --- Precio: hasta 850 € ---------------------------------------
PRECIO_MAXIMO = 850
PRECIO_IDEAL = 850          # por debajo de esto no sale el aviso 💸

# --- Zonas: nada en Teis ----------------------------------------
ZONAS_EXCLUIDAS = ZONAS_EXCLUIDAS + ["teis"]  # noqa: F405
ZONAS_AVISO = {}            # el aviso de Teis ya no hace falta

# Las mismas webs, con el precio de las URLs subido a 850 €.
# (En Pisos.com la URL va hasta 900 € porque no tiene el corte de 850;
#  el bot descarta igualmente lo que pase de 850.)
BUSQUEDAS = [u.replace("maxPrice=800", "maxPrice=850")  # noqa: F405
             .replace("/hasta-800/", "/hasta-900/") for u in BUSQUEDAS]  # noqa: F405

# Ejemplos de otros ajustes que puedes cambiar solo para ellos
# (quita el # para activarlos):
# METROS_MINIMOS = 70
# ZONAS_PREFERIDAS = ["coia", "bouzas"]
