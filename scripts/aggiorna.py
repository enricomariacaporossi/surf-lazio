"""Aggiorna le previsioni (Fase 5): scarica, calcola e scrive la cartella data/.

Lo lancia GitHub Actions ogni 3 ore; in locale si prova cosi':
    .venv\\Scripts\\python scripts\\aggiorna.py            dati nuovi
    .venv\\Scripts\\python scripts\\aggiorna.py --da-csv   usa prove/tabella_*.csv

Scrive:
- data/forecast.json            tutto quello che serve alla pagina
- data/settimana_<spot>.csv     la settimana ora per ora, per le guide
                                (separatore ; e virgola decimale, come Excel in italiano)
- data/storico/<data>_<am|pm>_<spot>.csv
                                due copie al giorno della previsione, per la verifica
"""
import json
import math
import sys
from datetime import date, datetime

import pandas as pd

from comune import RADICE, carica_spot
from voto import FUSO, cardinale, valuta_spot

DATI = RADICE / "data"
STORICO = DATI / "storico"
CREDITI = [
    "Onde: E.U. Copernicus Marine Service Information",
    "Vento e meteo: Open-Meteo.com (CC BY 4.0), modelli ItaliaMeteo ICON-2I ed ECMWF IFS",
]


def pulisci(x):
    """Valori pronti per il JSON: niente NaN, date come testo, numeri arrotondati."""
    if hasattr(x, "item") and not isinstance(x, (pd.Timestamp, datetime)):
        x = x.item()  # tipi numpy -> tipi Python
    if isinstance(x, float):
        return None if math.isnan(x) else round(x, 2)
    if isinstance(x, (pd.Timestamp, datetime)):
        return x.strftime("%Y-%m-%dT%H:%M")
    if isinstance(x, date):
        return x.isoformat()
    return x


def record(riga, campi):
    return {nome: pulisci(riga[colonna]) for nome, colonna in campi.items()}


CAMPI_ORA = {
    "ora": "ora_locale", "giorno": "giorno", "di_giorno": "di_giorno", "onda_m": "VHM0",
    "parte": "parte", "parte_m": "h_parte", "periodo_s": "t_parte",
    "direzione_onda": "d_parte", "vento_kmh": "vento", "raffiche_kmh": "raffiche",
    "direzione_vento": "direzione", "colore": "colore", "voto": "voto",
    "livello": "livello", "fiducia": "fiducia", "incerto": "incerto",
    "scaduta": "scaduta", "pioggia_mm": "pioggia", "codice_meteo": "codice",
    "pressione_hpa": "pressione", "fonte_vento": "fonte", "frase": "frase",
}


def riassunto_spot(spot, t, fasce, migliore):
    """Il blocco di forecast.json per uno spot."""
    adesso = pd.Timestamp.now(tz=FUSO).floor("h")
    passate = t[t["ora_locale"] <= adesso]
    ora_attuale = passate.iloc[-1] if not passate.empty else t.iloc[0]

    luce = t[t["di_giorno"] & t["giorno"].between(1, 7)]
    giorni = []
    for data, f in fasce[fasce["giorno"] <= 7].groupby("data"):
        ore_giorno = luce[luce["ora_locale"].dt.date == data]
        giorni.append({
            "data": pulisci(data),
            "giorno": int(f["giorno"].iloc[0]),
            "fiducia": f["fiducia"].iloc[0],
            "prima_luce": pulisci(ore_giorno["ora_locale"].min()) if not ore_giorno.empty else None,
            "ultima_luce": pulisci(ore_giorno["ora_locale"].max()) if not ore_giorno.empty else None,
            "voto_max": pulisci(f["voto"].max()),
            "fasce": [
                {**{k: pulisci(v) for k, v in r.items() if k not in ("data", "segnali")},
                 "segnali": [s for s in r["segnali"].split("; ") if s]}
                for r in f.to_dict("records")
            ],
        })

    return {
        "id": spot["id"],
        "nome": spot["nome"],
        "avviso": spot.get("avviso"),
        "riva": spot.get("riva"),
        "webcam": spot.get("webcam", []),
        "confronto": spot.get("confronto"),
        "adesso": record(ora_attuale, CAMPI_ORA),
        "finestra_migliore": None if migliore is None else {
            k: pulisci(v) for k, v in migliore.items()},
        "giorni": giorni,
        "ore": [record(r, CAMPI_ORA) for _, r in luce.iterrows()],
    }


def salva_settimana(spot, t):
    """CSV della settimana, ore di luce, pronto per Excel in italiano."""
    luce = t[t["di_giorno"] & t["giorno"].between(1, 7)]
    tabella = pd.DataFrame({
        "ora": luce["ora_locale"].dt.strftime("%Y-%m-%d %H:%M"),
        "onda_m": luce["VHM0"].round(2),
        "parte": luce["parte"],
        "periodo_s": luce["t_parte"].round(1),
        "provenienza_onda": luce["d_parte"].map(cardinale),
        "vento_kmh": luce["vento"].round(0),
        "raffiche_kmh": luce["raffiche"].round(0),
        "provenienza_vento": luce["direzione"].map(cardinale),
        "colore_vento": luce["colore"],
        "voto": luce["voto"],
        "livello": luce["livello"],
        "fiducia": luce["fiducia"],
        "scaduta": luce["scaduta"].map({True: "si", False: ""}),
    })
    tabella.to_csv(DATI / f"settimana_{spot['id']}.csv", index=False,
                   sep=";", decimal=",", encoding="utf-8-sig")


def salva_storico(spot, t):
    """Una copia ogni mezza giornata (la prima di ogni mattina e pomeriggio)."""
    STORICO.mkdir(parents=True, exist_ok=True)
    adesso = pd.Timestamp.now(tz="UTC")
    meta = "am" if adesso.hour < 12 else "pm"
    file = STORICO / f"{adesso:%Y-%m-%d}_{meta}_{spot['id']}.csv"
    if file.exists():
        return
    colonne = ["VHM0", "VTM01_SW1", "VMDR_SW1", "VHM0_WW", "vento", "direzione",
               "raffiche", "pressione", "voto", "livello", "giorno"]
    t[colonne].to_csv(file, float_format="%.2f", index_label="ora_utc")


def main(da_csv=False):
    DATI.mkdir(exist_ok=True)
    risultato = {
        "aggiornato": pulisci(pd.Timestamp.now(tz=FUSO)),
        "fuso": FUSO,
        "crediti": CREDITI,
        "spot": [],
    }
    for spot in carica_spot():
        if da_csv:
            from voto import carica_tabella_csv
            t = carica_tabella_csv(RADICE / "prove" / f"tabella_{spot['id']}.csv")
        else:
            from tabella import tabella_spot
            t = tabella_spot(spot)
        t, fasce, migliore = valuta_spot(spot, t)
        risultato["spot"].append(riassunto_spot(spot, t, fasce, migliore))
        salva_settimana(spot, t)
        if not da_csv:
            salva_storico(spot, t)
        print(f"{spot['nome']}: {len(t)} ore elaborate")

    with open(DATI / "forecast.json", "w", encoding="utf-8") as f:
        json.dump(risultato, f, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
    print(f"Scritto data/forecast.json ({(DATI / 'forecast.json').stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main(da_csv="--da-csv" in sys.argv)
