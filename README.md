# Bot de pisos (Vigo)

Busca pisos de alquiler en Fotocasa, Pisos.com, Habitaclia y Wallapop cada 30 minutos
(GitHub Actions) y envía los nuevos al grupo de Telegram.

- **Filtros y webs:** `config.py` (búsqueda principal) y `config_amigos.py` (2-3 habitaciones).
- **Token de Telegram:** secreto `TELEGRAM_TOKEN` del repositorio (nunca en el código).
- **Lanzar a mano / resumen semanal:** pestaña *Actions* → *Buscar pisos* → *Run workflow* → modo `semanal`.
- **Búsqueda de amigos:** se activa creando la variable `AMIGOS_CHAT_ID` con el ID de su grupo.
