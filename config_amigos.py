# ============================================================
#  BÚSQUEDA PARA LOS AMIGOS  (2 o 3 habitaciones)
# ============================================================
# Coge TODO de config.py (token, grupo, webs, precio, zonas...) y aquí
# solo se cambia lo que es distinto. Si quieres cambiar algo más para
# ellos, copia la línea de config.py aquí debajo y cambia el valor.

import os

from config import *  # noqa: F401,F403

NOMBRE_BUSQUEDA = "Búsqueda amigos (2-3 hab)"

HABITACIONES_MINIMAS = 2
HABITACIONES_MAXIMAS = 3

# Grupo de Telegram de los amigos: en GitHub se pone como variable
# AMIGOS_CHAT_ID (Settings → Secrets and variables → Actions → Variables).
# Mientras no exista, la búsqueda de los amigos no se lanza.
TELEGRAM_CHAT_ID = os.environ.get("AMIGOS_CHAT_ID") or TELEGRAM_CHAT_ID  # noqa: F405

# Ejemplos de otros ajustes que puedes cambiar solo para ellos
# (quita el # para activarlos):
# PRECIO_MAXIMO = 900
# PRECIO_IDEAL = 800
# METROS_MINIMOS = 70
# ZONAS_PREFERIDAS = ["coia", "bouzas"]
