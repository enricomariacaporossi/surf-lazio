"""Scarica vento e meteo da Open-Meteo per ogni spot di spots.json.

Uso (dalla cartella del progetto):
    .venv\\Scripts\\python scripts\\vento.py

Due modelli, una chiamata ciascuno:
- ICON-2I di ItaliaMeteo (circa 2 km, 3 giorni): il vento dei primi giorni;
- ECMWF IFS (9 km, fino a 15 giorni): il vento dei giorni dopo e il secondo
  parere per misurare la fiducia.
Tutti gli orari sono in UTC, come quelli di Copernicus.
"""
import requests
import pandas as pd
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from comune import RADICE, carica_spot

URL = "https://api.open-meteo.com/v1/forecast"

# Open-Meteo gratuito a volte risponde lento: fino a 4 nuovi tentativi,
# con attese crescenti (5, 10, 20, 40 secondi), anche per errori 429 e 5xx.
SESSIONE = requests.Session()
SESSIONE.mount("https://", HTTPAdapter(max_retries=Retry(
    total=4, connect=4, read=4, status=4, backoff_factor=5,
    status_forcelist=(429, 500, 502, 503, 504), allowed_methods=("GET",),
)))
ATTESA = (15, 90)  # secondi: per collegarsi, per ricevere la risposta
MODELLI = {
    "ICON-2I": "italia_meteo_arpae_icon_2i",
    "ECMWF": "ecmwf_ifs",
}
VARIABILI = {
    "wind_speed_10m": "vento",          # km/h, come nelle guide
    "wind_direction_10m": "direzione",  # gradi di provenienza
    "wind_gusts_10m": "raffiche",       # km/h
    "pressure_msl": "pressione",        # hPa, serve per la scaduta
    "precipitation": "pioggia",         # mm nell'ora
    "weather_code": "codice",           # 95-99 = temporale
}


def chiama_open_meteo(spot, modello, giorni_prima, giorni_dopo):
    """Una chiamata a Open-Meteo per un modello. Restituisce (orarie, giornaliere)."""
    punto = spot["vento_punto"]
    parametri = {
        "latitude": punto["lat"],
        "longitude": punto["lon"],
        "hourly": ",".join(VARIABILI),
        "daily": "sunrise,sunset",
        "models": modello,
        "timezone": "GMT",
        "wind_speed_unit": "kmh",
        "past_days": giorni_prima,
        "forecast_days": giorni_dopo + 1,
    }
    risposta = SESSIONE.get(URL, params=parametri, timeout=ATTESA)
    if risposta.status_code != 200:
        raise RuntimeError(
            f"Open-Meteo ({modello}) ha risposto {risposta.status_code}: "
            f"{risposta.text[:300]}"
        )
    dati = risposta.json()

    orarie = pd.DataFrame(dati["hourly"])
    orarie["time"] = pd.to_datetime(orarie["time"])
    orarie = orarie.set_index("time").rename(columns=VARIABILI)

    giornaliere = pd.DataFrame(dati.get("daily", {}))
    if not giornaliere.empty:
        giornaliere["time"] = pd.to_datetime(giornaliere["time"]).dt.date
        for colonna in ("sunrise", "sunset"):
            giornaliere[colonna] = pd.to_datetime(giornaliere[colonna])
        giornaliere = giornaliere.set_index("time").rename(
            columns={"sunrise": "alba", "sunset": "tramonto"}
        )
    return orarie, giornaliere


def scarica_vento(spot, giorni_prima=1, giorni_dopo=7):
    """Vento orario dello spot: ICON-2I dove c'e', altrimenti ECMWF.

    Colonne: vento, direzione, raffiche, pressione, pioggia, codice, fonte,
    piu' vento_ecmwf e direzione_ecmwf per il confronto tra modelli.
    Restituisce anche alba e tramonto di ogni giorno (UTC).
    """
    # ECMWF e' indispensabile (copre tutti i giorni); ICON-2I e' un di piu':
    # se non risponde si va avanti con il solo ECMWF.
    ecmwf, luce = chiama_open_meteo(spot, MODELLI["ECMWF"], giorni_prima, giorni_dopo)
    try:
        icon, _ = chiama_open_meteo(spot, MODELLI["ICON-2I"], giorni_prima, giorni_dopo)
    except (requests.RequestException, RuntimeError) as errore:
        print(f"Attenzione: ICON-2I non disponibile ({errore}); uso solo ECMWF.")
        icon = pd.DataFrame(index=ecmwf.index, columns=list(VARIABILI.values()), dtype=float)

    icon = icon.reindex(ecmwf.index)
    risultato = icon[list(VARIABILI.values())].combine_first(
        ecmwf[list(VARIABILI.values())]
    )
    risultato["fonte"] = "ECMWF"
    risultato.loc[icon["vento"].notna(), "fonte"] = "ICON-2I"
    risultato["vento_ecmwf"] = ecmwf["vento"]
    risultato["direzione_ecmwf"] = ecmwf["direzione"]
    return risultato, luce


if __name__ == "__main__":
    cartella = RADICE / "prove"
    cartella.mkdir(exist_ok=True)
    for spot in carica_spot():
        vento, luce = scarica_vento(spot)
        uscita = cartella / f"vento_{spot['id']}.csv"
        vento.to_csv(uscita)
        print(f"\n{spot['nome']}: {len(vento)} ore salvate in prove/{uscita.name}")
        print(vento[["vento", "direzione", "raffiche", "pressione", "fonte",
                     "vento_ecmwf"]].iloc[::6].round(0).to_string())
        print("\nAlba e tramonto (UTC):")
        print(luce.head(3).to_string())
