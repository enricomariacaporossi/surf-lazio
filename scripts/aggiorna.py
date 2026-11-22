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
- data/telegram/                avvisi gia' mandati e risposte ai pulsanti (se c'e' il bot)
- data/verifica.json            quanto ci prende la previsione (Fase 6)
"""
import json
import math
import sys
from datetime import date, datetime

import pandas as pd

from comune import RADICE, carica_spot
from fronte import assegna_tappe, riassunto_fronte
from voto import FUSO, cardinale, valuta_spot

DATI = RADICE / "data"
STORICO = DATI / "storico"
CREDITI = [
    "Onde: E.U. Copernicus Marine Service Information",
    "Vento e meteo: Open-Meteo.com (CC BY 4.0), modelli ItaliaMeteo ICON-2I ed ECMWF IFS",
    "Secondo parere sull'onda (ECMWF WAM) e temperatura del mare: Open-Meteo.com (CC BY 4.0)",
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
    # una colonna che manca (per esempio Open-Meteo Marine non ha risposto) diventa null
    return {nome: pulisci(riga.get(colonna)) for nome, colonna in campi.items()}


CAMPI_ORA = {
    "ora": "ora_locale", "giorno": "giorno", "di_giorno": "di_giorno", "onda_m": "VHM0",
    "parte": "parte", "parte_m": "h_parte", "periodo_s": "t_parte",
    "direzione_onda": "d_parte", "vento_kmh": "vento", "raffiche_kmh": "raffiche",
    "direzione_vento": "direzione", "colore": "colore", "voto": "voto",
    "livello": "livello", "fiducia": "fiducia", "incerto": "incerto",
    "scaduta": "scaduta", "pioggia_mm": "pioggia", "codice_meteo": "codice",
    "pressione_hpa": "pressione", "fonte_vento": "fonte", "frase": "frase",
    "acqua_c": "acqua", "tappa": "tappa", "aria_c": "aria",
}


CAMPI_SERIE = {
    "ora": "ora_locale", "di_giorno": "di_giorno", "onda_m": "VHM0",
    "periodo_s": "t_parte", "direzione_onda": "d_parte", "vento_kmh": "vento",
    "raffiche_kmh": "raffiche", "direzione_vento": "direzione", "colore": "colore",
    "voto": "voto", "tappa": "tappa", "fronte": "fronte",
    "pioggia_mm": "pioggia", "codice_meteo": "codice", "aria_c": "aria",
}


def cielo_del_giorno(ore):
    """Il tempo delle ore di luce in una parola, come le icone della pagina."""
    if ore.empty or "codice" not in ore:
        return None
    codici = ore["codice"].fillna(0)
    pioggia = ore["pioggia"].fillna(0).sum() if "pioggia" in ore else 0
    if (codici >= 95).any():
        return "temporale"
    ore_bagnate = (codici.between(51, 67) | codici.between(80, 82)).sum()
    if pioggia >= 0.5 or ore_bagnate >= 3:
        return "pioggia"
    if codici.between(71, 77).any() or codici.between(85, 86).any():
        return "neve"
    tipico = codici.median()
    if 45 <= tipico <= 48:
        return "nebbia"
    if tipico >= 3:
        return "coperto"
    return "variabile" if tipico >= 1 else "sereno"


def riassunto_spot(spot, t, fasce, migliore):
    """Il blocco di forecast.json per uno spot."""
    adesso = pd.Timestamp.now(tz=FUSO).floor("h")
    passate = t[t["ora_locale"] <= adesso]
    ora_attuale = passate.iloc[-1] if not passate.empty else t.iloc[0]

    luce = t[t["di_giorno"] & t["giorno"].between(1, 7)]
    giorni = []
    for data, f in fasce[fasce["giorno"] <= 7].groupby("data"):
        ore_giorno = luce[luce["ora_locale"].dt.date == data]
        tutte = t[t["ora_locale"].dt.date == data]
        passaggio = tutte[tutte["fronte"]] if "fronte" in tutte else tutte.iloc[0:0]
        acqua = ore_giorno["acqua"].mean() if "acqua" in ore_giorno else None
        giorni.append({
            "data": pulisci(data),
            "giorno": int(f["giorno"].iloc[0]),
            "fiducia": f["fiducia"].iloc[0],
            "prima_luce": pulisci(ore_giorno["ora_locale"].min()) if not ore_giorno.empty else None,
            "ultima_luce": pulisci(ore_giorno["ora_locale"].max()) if not ore_giorno.empty else None,
            "voto_max": pulisci(f["voto"].max()),
            "acqua_c": pulisci(acqua),
            "cielo": cielo_del_giorno(ore_giorno),
            "pioggia_mm": pulisci(ore_giorno["pioggia"].sum()) if "pioggia" in ore_giorno else None,
            "aria_max": pulisci(ore_giorno["aria"].max()) if "aria" in ore_giorno else None,
            "fronte": passaggio["ora_locale"].iloc[0].strftime("%H:%M") if not passaggio.empty else None,
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
        "fronte": riassunto_fronte(t),
        "ore": [record(r, CAMPI_ORA) for _, r in luce.iterrows()],
        # tutte le ore dei prossimi 7 giorni, notte compresa, per il grafico
        "serie": [record(r, CAMPI_SERIE) for _, r in
                  t[t["giorno"].between(1, 7)].iterrows()],
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
        "tappa_fronte": luce["tappa"].replace(0, pd.NA),
        "pioggia_mm": luce["pioggia"].round(1) if "pioggia" in luce else pd.NA,
        "aria_c": luce["aria"].round(0) if "aria" in luce else pd.NA,
        "acqua_c": luce["acqua"].round(1) if "acqua" in luce else pd.NA,
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
               "raffiche", "pressione", "voto", "livello", "giorno",
               "onda_ecmwf", "acqua", "tappa"]
    t[[c for c in colonne if c in t]].to_csv(file, float_format="%.2f", index_label="ora_utc")


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
        t = assegna_tappe(t)
        risultato["spot"].append(riassunto_spot(spot, t, fasce, migliore))
        salva_settimana(spot, t)
        if not da_csv:
            salva_storico(spot, t)
        print(f"{spot['nome']}: {len(t)} ore elaborate")

    with open(DATI / "forecast.json", "w", encoding="utf-8") as f:
        json.dump(risultato, f, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
    print(f"Scritto data/forecast.json ({(DATI / 'forecast.json').stat().st_size // 1024} KB)")

    # la verifica della Fase 6: parte da sola quando lo storico copre 14 giorni
    try:
        from verifica import main as verifica
        verifica()
    except Exception as errore:  # noqa: BLE001
        print(f"Attenzione: la verifica non ha funzionato ({errore}).")

    if not da_csv:
        # Telegram e' un di piu': se qualcosa va storto la previsione resta salvata
        try:
            from telegram_bot import main as telegram
            telegram()
        except Exception as errore:  # noqa: BLE001
            print(f"Attenzione: Telegram non ha funzionato ({errore}).")


if __name__ == "__main__":
    main(da_csv="--da-csv" in sys.argv)
