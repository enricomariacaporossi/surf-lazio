"""Secondo parere sull'onda e temperatura dell'acqua, da Open-Meteo Marine.

Uso (dalla cartella del progetto):
    .venv\\Scripts\\python scripts\\mare.py

Due chiamate per spot, nella cella di mare dello spot:
- ECMWF WAM (9 km, orario): l'onda di un secondo modello, per dire
  «incerto» quando non va d'accordo con Copernicus;
- temperatura della superficie del mare (MeteoFrance, 8 km, ogni 6 ore):
  serve per scegliere la muta.
Sono un di piu': se Open-Meteo non risponde la previsione si fa lo stesso.
Orari in UTC, come quelli di Copernicus.
"""
import pandas as pd
import requests

from comune import carica_spot
from vento import ATTESA, SESSIONE

URL = "https://marine-api.open-meteo.com/v1/marine"
COLONNE = ["onda_ecmwf", "acqua"]


def chiama_marine(spot, variabile, modello, giorni_prima, giorni_dopo):
    """Una variabile oraria da Open-Meteo Marine, come serie con indice UTC."""
    parametri = {
        "latitude": spot["cella"]["lat"],
        "longitude": spot["cella"]["lon"],
        "hourly": variabile,
        "timezone": "GMT",
        "past_days": giorni_prima,
        "forecast_days": giorni_dopo + 1,
        "cell_selection": "sea",
    }
    if modello:
        parametri["models"] = modello
    risposta = SESSIONE.get(URL, params=parametri, timeout=ATTESA)
    if risposta.status_code != 200:
        raise RuntimeError(f"Open-Meteo Marine ({variabile}) ha risposto "
                           f"{risposta.status_code}: {risposta.text[:300]}")
    orarie = risposta.json()["hourly"]
    serie = pd.Series(orarie[variabile], index=pd.to_datetime(orarie["time"]), dtype=float)
    # la temperatura arriva ogni 6 ore: si riempiono le ore in mezzo
    return serie.interpolate(limit=6, limit_area="inside")


def scarica_mare(spot, giorni_prima=1, giorni_dopo=7):
    """Tabella oraria con onda_ecmwf (m) e acqua (gradi C). Colonna vuota se manca."""
    richieste = {
        "onda_ecmwf": ("wave_height", "ecmwf_wam"),
        "acqua": ("sea_surface_temperature", None),
    }
    colonne = {}
    for nome, (variabile, modello) in richieste.items():
        try:
            serie = chiama_marine(spot, variabile, modello, giorni_prima, giorni_dopo)
            if serie.notna().sum() == 0:
                print(f"Attenzione: {variabile} vuota per {spot['nome']}.")
            colonne[nome] = serie
        except (requests.RequestException, RuntimeError, KeyError, ValueError) as errore:
            print(f"Attenzione: {variabile} non disponibile ({errore}); vado avanti senza.")
    if not colonne:
        return pd.DataFrame(columns=COLONNE, dtype=float)
    return pd.DataFrame(colonne).reindex(columns=COLONNE)


if __name__ == "__main__":
    for spot in carica_spot():
        mare = scarica_mare(spot)
        print(f"\n{spot['nome']}: {mare.notna().sum().to_dict()} ore con dati")
        print(mare.iloc[::12].round(1).to_string())
