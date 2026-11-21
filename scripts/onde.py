"""Scarica le onde Copernicus per ogni spot di spots.json.

Uso (dalla cartella del progetto):
    .venv\\Scripts\\python scripts\\onde.py

Le credenziali Copernicus vengono lette dal file creato con
`copernicusmarine login` oppure dalle variabili d'ambiente
COPERNICUSMARINE_SERVICE_USERNAME e COPERNICUSMARINE_SERVICE_PASSWORD.
"""
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import copernicusmarine

DATASET = "cmems_mod_med_wav_anfc_4.2km_PT1H-i"
VARIABILI = [
    "VHM0", "VMDR", "VTPK",                  # onda totale
    "VHM0_SW1", "VMDR_SW1", "VTM01_SW1",     # swell primario
    "VHM0_SW2", "VMDR_SW2", "VTM01_SW2",     # swell secondario
    "VHM0_WW", "VMDR_WW", "VTM01_WW",        # mare di vento
]
RADICE = Path(__file__).resolve().parent.parent


def carica_spot():
    """Legge le schede degli spot da spots.json."""
    with open(RADICE / "spots.json", encoding="utf-8") as f:
        return json.load(f)


def scarica_onde(spot, giorni_prima=1, giorni_dopo=7):
    """Serie oraria delle onde nella cella dello spot, orari UTC."""
    adesso = datetime.now(timezone.utc).replace(
        tzinfo=None, minute=0, second=0, microsecond=0
    )
    lat, lon = spot["cella"]["lat"], spot["cella"]["lon"]
    ds = copernicusmarine.open_dataset(
        dataset_id=DATASET,
        minimum_latitude=lat - 0.03, maximum_latitude=lat + 0.03,
        minimum_longitude=lon - 0.03, maximum_longitude=lon + 0.03,
        start_datetime=adesso - timedelta(days=giorni_prima),
        end_datetime=adesso + timedelta(days=giorni_dopo),
    )
    presenti = [v for v in VARIABILI if v in ds.data_vars]
    mancanti = [v for v in VARIABILI if v not in ds.data_vars]
    if mancanti:
        print(f"Attenzione, variabili non trovate: {mancanti}")
        print(f"Variabili disponibili: {sorted(ds.data_vars)}")
    punto = ds[presenti].sel(latitude=lat, longitude=lon, method="nearest")
    return punto.to_dataframe()[presenti]


if __name__ == "__main__":
    cartella = RADICE / "prove"
    cartella.mkdir(exist_ok=True)
    for spot in carica_spot():
        df = scarica_onde(spot)
        uscita = cartella / f"onde_{spot['id']}.csv"
        df.to_csv(uscita)
        print(f"\n{spot['nome']}: {len(df)} ore salvate in prove/{uscita.name}")
        colonne = [c for c in ["VHM0", "VTPK", "VHM0_SW1", "VMDR_SW1",
                               "VTM01_SW1", "VHM0_WW"] if c in df]
        print(df[colonne].iloc[::6].round(2).to_string())
