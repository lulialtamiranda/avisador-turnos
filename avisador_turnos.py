"""
Avisa por Telegram cuando aparece un turno ANTES de una fecha límite.

Variables de entorno necesarias:
  TELEGRAM_TOKEN     token que te dio @BotFather
  TELEGRAM_CHAT_ID   tu chat id (ver instrucciones en el chat)

Opcionales:
  FECHA_LIMITE       solo avisa turnos anteriores a esta fecha (default 2026-10-15)
  INTERVALO_MIN      cada cuántos minutos revisa (default 10)
"""
import json
import os
import time
from datetime import date, datetime, timezone

import requests

URL = "https://api.drapp.la/teams/27c09f07/availability"
TOKEN = os.environ["TELEGRAM_TOKEN"]
CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]
LIMITE = os.environ.get("FECHA_LIMITE", "2026-10-15")
INTERVALO = int(os.environ.get("INTERVALO_MIN", "10")) * 60
PORTAL = (
    "https://consultoriosuruguay.cartilla.drapp.com.ar/equipos/27c09f07/"
    "place-20a40a/65119967/clinica-medica/consulta/osde/310/2026-10-04"
)
ARCHIVO_VISTOS = "vistos.json"


def cargar_vistos():
    try:
        with open(ARCHIVO_VISTOS) as f:
            return set(json.load(f))
    except (FileNotFoundError, json.JSONDecodeError):
        return set()


def guardar_vistos(vistos):
    with open(ARCHIVO_VISTOS, "w") as f:
        json.dump(sorted(vistos), f)


def consultar():
    # La ventana va desde hoy hasta la fecha límite (en milisegundos, UTC)
    fin = datetime.fromisoformat(LIMITE).replace(tzinfo=timezone.utc)
    payload = {
        "visibility": "unlisted",
        "team": "teams/27c09f07",
        "location": "place-20a40a",
        "startsAt": date.today().isoformat(),
        "endsAt": int(fin.timestamp() * 1000),
        "financier": "pms_financiers:osde/310",
        "marketplace": "cartilla",
        "price": "cartilla",
        "resource": "resources/65119967",
        "service": "pms_specialties:clinica-medica/pms_practices:consulta",
        "valid": "cartilla",
    }
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Origin": "https://consultoriosuruguay.cartilla.drapp.com.ar",
    }
    r = requests.post(URL, json=payload, headers=headers, timeout=20)
    r.raise_for_status()
    return r.json().get("slots", {})


def avisar(texto):
    requests.post(
        f"https://api.telegram.org/bot{TOKEN}/sendMessage",
        data={"chat_id": CHAT_ID, "text": texto},
        timeout=20,
    ).raise_for_status()


def revisar():
    slots = consultar()
    vistos = cargar_vistos()
    nuevos = []
    for dia, horas in sorted(slots.items()):
        if dia >= LIMITE:  # las fechas ISO se comparan bien como texto
            continue
        for hora in sorted(horas):
            clave = f"{dia} {hora}"
            if clave not in vistos:
                nuevos.append(clave)
    if nuevos:
        avisar("Turno disponible antes del " + LIMITE + ":\n" + "\n".join(nuevos) + "\n\n" + PORTAL)
        guardar_vistos(vistos | set(nuevos))
    return nuevos


if __name__ == "__main__":
    if os.environ.get("UNA_VEZ") == "1":
        # Modo nube (GitHub Actions): revisa una vez y termina. Si hay error, la ejecución falla y GitHub avisa.
        print("Turnos nuevos:", revisar())
        raise SystemExit(0)
    print("Revisando cada", INTERVALO // 60, "minutos. Ctrl+C para cortar.")
    while True:
        try:
            nuevos = revisar()
            print(time.strftime("%H:%M"), "-", f"{len(nuevos)} turnos nuevos" if nuevos else "nada nuevo")
        except Exception as e:  # no cortar el loop por un error de red
            print(time.strftime("%H:%M"), "- error:", e)
        time.sleep(INTERVALO)
