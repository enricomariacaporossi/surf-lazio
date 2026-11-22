"""Collaudo all'indietro: che voto avrebbe dato il sito nelle giornate vere.

Le giornate sono quelle della galleria della Barefoot Surf School
(scuoladisurf.com/gallery), con data e, quando c'e', com'era il mare.
Sono giornate in cui la scuola era in acqua: il voto del sito dovrebbe essere
almeno discreto. Dicono se il sito e' troppo severo, non se e' troppo generoso.

Dati del passato:
- onde: rianalisi Copernicus del Mediterraneo (stesso modello, rifatto sul passato);
- vento e meteo: archivio Open-Meteo (rianalisi ERA5).

Si lancia a mano da GitHub (Actions > collaudo > Run workflow) e scrive
data/collaudo/collaudo.csv; nel registro stampa il riepilogo.
"""
import sys
from datetime import date

import pandas as pd
import requests

from comune import RADICE, carica_spot
from vento import ATTESA, SESSIONE
from voto import FUSO, calcola_ore

# spot: "castello", "fregene" o None (non detto: si guardano tutti e due)
GIORNATE = [
    ("2023-11-18", None, ""), ("2023-10-22", None, ""), ("2023-10-19", None, ""),
    ("2023-10-15", None, ""), ("2023-09-24", None, ""), ("2023-09-19", None, ""),
    ("2023-07-31", None, ""), ("2023-04-25", None, ""), ("2023-04-08", None, ""),
    ("2023-03-25", None, ""), ("2023-03-19", None, ""), ("2023-02-19", None, ""),
    ("2023-02-04", None, ""), ("2023-01-15", None, ""), ("2022-12-24", None, ""),
    ("2022-12-17", None, ""), ("2022-10-02", None, ""), ("2022-09-10", None, ""),
    ("2022-09-04", None, ""), ("2022-04-03", None, ""), ("2022-03-27", None, ""),
    ("2022-01-30", None, ""), ("2021-11-14", None, ""),
    ("2021-10-23", None, "vento zero, onde perfette"),
    ("2021-09-18", None, "onde lunghe e lisce"),
    ("2021-09-11", "fregene", "mezzo metro abbondante, vento debolissimo, il pomeriggio ventoso"),
    ("2021-08-28", "fregene", "onda costante fino a riva, swell dalle Bocche"),
    ("2021-08-19", None, "mezzo metro abbondante, poco vento, principianti e intermedi"),
    ("2021-07-11", None, "onda generosa, pochissimo vento"),
    ("2021-05-16", None, "mare quasi estivo, calmo"),
    ("2021-05-08", None, "al ginocchio, onde lunghe"),
    ("2021-04-10", None, "brutto tempo, allenamento intenso"),
    ("2021-04-11", None, "brutto tempo, allenamento intenso"),
    ("2021-03-13", None, "mezzo metro, poco vento da terra, swell da Sud"),
    ("2021-02-06", None, "mezzo metro facile, poco vento, Sud"),
    ("2021-02-05", None, "piccola, vento zero"),
    ("2021-01-30", "castello", "mezzo metro abbondante, veloce, Sud"),
    ("2021-01-23", None, "a caccia di onde, sessioni dure"),
    ("2021-01-24", None, "a caccia di onde, sessioni dure"),
    ("2020-11-29", None, "sotto il metro, vento da terra leggero, Scirocco"),
    ("2020-11-15", None, "mezzo metro, swell dalle Bocche"),
    ("2020-02-29", None, "mezzo metro, niente vento"),
    ("2020-02-02", "castello", "molto surfabile, poco vento"),
    ("2019-12-24", None, "liscia, niente vento, Nord-Ovest"),
    ("2019-11-30", None, "swell da Ovest dopo la pioggia"),
    ("2019-11-09", None, "liscia, vento da terra, Sud"),
    ("2019-09-28", None, "mezzo metro abbondante, pochissimo vento"),
    ("2019-09-23", "castello", "swell da Sud"),
    ("2019-09-07", "fregene", "vento zero, Nord-Ovest"),
    ("2019-08-02", "fregene", "piccola, poco vento, Sud e Sud-Est"),
    ("2019-08-03", "fregene", "morbida, molto surfabile, Sud"),
    ("2019-08-08", "castello", "buona, poco vento, Sud, tutti i livelli"),
    ("2019-05-04", None, "swell piccolo da Sud, principianti e intermedi"),
    ("2019-04-28", None, "da mezzo metro a un metro"),
    ("2019-04-27", None, "poco vento, swell dalle Bocche"),
    ("2019-04-07", None, "mezzo metro abbondante, brezza dal mare"),
    ("2019-03-17", None, "un metro scarso, poco vento"),
    ("2019-03-10", None, "mezzo metro liscio, pochissimo vento, Ovest"),
    ("2019-01-19", None, "mezzo metro, vento da terra, mareggiata in calo"),
    ("2018-12-23", None, ""), ("2018-12-01", None, ""),
    ("2018-11-04", "castello", "perfetta per imparare"),
    ("2018-11-03", None, "mezzo metro, vento da terra, Scirocco"),
    ("2018-10-07", None, "liscia, facile"),
    ("2018-09-08", None, "liscia, facile"),
    ("2018-09-01", None, "picchi alla spalla, poco vento"),
    ("2018-08-25", None, "mezzo metro, swell dalle Bocche"),
    ("2018-07-22", None, "alla spalla, liscia, vento da terra poi piu' forte, Sud poi Ovest"),
    ("2018-07-07", None, "mezzo metro tutto il giorno, brezza dal mare il pomeriggio, Nord-Ovest"),
    ("2018-04-15", None, "quattro ore a caccia di onde"),
    ("2018-04-02", None, "perfetta per tutti i livelli"),
    ("2018-03-11", None, "mare vuoto e calmo"),
    ("2018-03-04", None, "liscia"),
    ("2018-02-04", None, "un metro, morbida e lunga, niente vento, dopo il Maestrale"),
    ("2018-01-20", None, "mezzo metro abbondante, poco vento"),
    ("2018-01-06", None, "mezzo metro, poco vento da Sud, Sud"),
    ("2017-12-31", None, "mezzo metro in aumento, vento da terra"),
    ("2017-12-08", "castello", "non troppo grande, tutti i livelli"),
    ("2017-11-12", "castello", "piatta, poi piccola, vento da terra leggero"),
    ("2017-11-09", None, "sopra la spalla, vento da terra, Bocche"),
    ("2017-11-05", "castello", "morbida ma veloce, Sud"),
    ("2017-10-29", None, "pulita, vento da terra leggero, Bocche"),
    ("2017-10-22", None, "swell lungo, vento da terra, Bocche"),
    ("2017-10-08", None, "piccola poi sopra la spalla, Sud poi Ovest"),
    ("2017-09-19", None, ""), ("2017-09-16", None, ""),
    ("2017-09-03", None, "swell grosso, vento calato"),
    ("2017-09-02", None, ""),
    ("2017-08-12", None, "poco vento, Maestrale dalle Bocche"),
    ("2017-08-10", None, "bella, poco vento"),
    ("2017-07-26", None, "un metro, niente vento"),
    ("2017-06-29", None, "un metro, mare attivo"),
    ("2017-05-20", None, ""),
    ("2017-04-16", "castello", "ripida, Ovest-Nord-Ovest"),
    ("2017-04-23", "castello", "morbida, Ovest-Nord-Ovest"),
    ("2017-04-02", None, "il vento ha modellato le onde"),
    ("2017-03-19", None, "swell dalle Bocche"),
    ("2017-03-05", None, ""), ("2017-02-09", None, ""),
    ("2017-02-02", None, ""), ("2017-02-04", None, ""), ("2017-02-05", None, ""),
    ("2017-01-28", None, "piu' piccola, un po' di Scirocco"),
    ("2017-01-22", None, "lunghe e morbide, vento da terra, Sud-Est"),
    ("2016-11-25", None, "perfetta"),
]
SPOT = {"castello": "santa-severa", "fregene": "fregene"}
VARIABILI = [  # come in onde.py
    "VHM0", "VMDR", "VTPK",
    "VHM0_SW1", "VMDR_SW1", "VTM01_SW1",
    "VHM0_SW2", "VMDR_SW2", "VTM01_SW2",
    "VHM0_WW", "VMDR_WW", "VTM01_WW",
]
DATASET = [  # la rianalisi ha cambiato nome nel tempo: si prova in ordine
    "cmems_mod_med_wav_my_4.2km_PT1H-i",
    "med-hcmr-wav-rean-h",
    "cmems_mod_med_wav_myint_4.2km_PT1H-i",
]
ARCHIVIO = "https://archive-api.open-meteo.com/v1/archive"
VENTO = {"wind_speed_10m": "vento", "wind_direction_10m": "direzione",
         "wind_gusts_10m": "raffiche", "pressure_msl": "pressione",
         "precipitation": "pioggia", "weather_code": "codice"}


def onde_storiche(spot, inizio, fine):
    """Serie oraria delle onde nella cella dello spot sul periodo, dalla rianalisi."""
    import copernicusmarine
    lat, lon = spot["cella"]["lat"], spot["cella"]["lon"]
    pezzi = []
    for dataset in DATASET:
        try:
            ds = copernicusmarine.open_dataset(
                dataset_id=dataset,
                minimum_latitude=lat - 0.03, maximum_latitude=lat + 0.03,
                minimum_longitude=lon - 0.03, maximum_longitude=lon + 0.03,
                start_datetime=inizio, end_datetime=fine,
            )
        except Exception as errore:  # noqa: BLE001
            print(f"  {dataset}: non disponibile ({str(errore)[:120]})")
            continue
        presenti = [v for v in VARIABILI if v in ds.data_vars]
        print(f"  {dataset}: {str(ds.time.values[0])[:10]} - {str(ds.time.values[-1])[:10]}, "
              f"variabili {len(presenti)}/{len(VARIABILI)}")
        punto = ds[presenti].sel(latitude=lat, longitude=lon, method="nearest")
        pezzi.append(punto.to_dataframe()[presenti])
        if pd.Timestamp(ds.time.values[-1]) >= pd.Timestamp(fine) - pd.Timedelta(days=1):
            break  # questo copre tutto il periodo: gli altri non servono
    if not pezzi:
        raise RuntimeError("nessuna rianalisi Copernicus disponibile")
    tutto = pd.concat(pezzi)
    tutto = tutto[~tutto.index.duplicated(keep="first")].sort_index()
    return tutto.reindex(columns=VARIABILI)


def vento_storico(spot, inizio, fine):
    """Vento e meteo orari dall'archivio Open-Meteo, con alba e tramonto."""
    punto = spot["vento_punto"]
    parametri = {
        "latitude": punto["lat"], "longitude": punto["lon"],
        "start_date": inizio.isoformat(), "end_date": fine.isoformat(),
        "hourly": ",".join(VENTO), "daily": "sunrise,sunset",
        "timezone": "GMT", "wind_speed_unit": "kmh",
    }
    r = SESSIONE.get(ARCHIVIO, params=parametri, timeout=(15, 180))
    r.raise_for_status()
    dati = r.json()
    orarie = pd.DataFrame(dati["hourly"])
    orarie["time"] = pd.to_datetime(orarie["time"])
    orarie = orarie.set_index("time").rename(columns=VENTO)
    giornaliere = pd.DataFrame(dati["daily"])
    giornaliere["time"] = pd.to_datetime(giornaliere["time"]).dt.date
    luce = giornaliere.set_index("time").rename(columns={"sunrise": "alba", "sunset": "tramonto"})
    luce["alba"] = pd.to_datetime(luce["alba"])
    luce["tramonto"] = pd.to_datetime(luce["tramonto"])
    return orarie, luce


def giornata(spot, onde, vento, luce, giorno):
    """Il voto ora per ora di una giornata del passato, come lo darebbe il sito oggi."""
    inizio = pd.Timestamp(giorno)
    fine = inizio + pd.Timedelta(hours=23)
    t = onde.loc[inizio:fine].join(vento.loc[inizio:fine], how="inner")
    if t.empty or t["VHM0"].isna().all():
        return None
    t.index = pd.DatetimeIndex(t.index).tz_localize("UTC")
    t["ora_locale"] = t.index.tz_convert(FUSO)
    alba = pd.Timestamp(luce.loc[giorno, "alba"]).tz_localize("UTC")
    tramonto = pd.Timestamp(luce.loc[giorno, "tramonto"]).tz_localize("UTC")
    t["di_giorno"] = (t.index >= alba - pd.Timedelta(minutes=30)) & (t.index <= tramonto)
    t["giorno"] = 1
    t["fonte"] = "ERA5"
    t["vento_ecmwf"], t["direzione_ecmwf"] = t["vento"], t["direzione"]
    t = calcola_ore(t, spot)
    luce_ore = t[t["di_giorno"]]
    if luce_ore.empty:
        return None
    m = luce_ore.loc[luce_ore["voto"].idxmax()]
    return {
        "voto_max": m["voto"], "ora": m["ora_locale"].strftime("%H:%M"),
        "onda_riva": round(m["onda_riva"], 2), "onda_largo": round(m["VHM0"], 2),
        "parte": m["parte"], "periodo": round(m["t_parte"], 1), "dir_onda": round(m["d_parte"]),
        "vento": round(m["vento"]), "dir_vento": round(m["direzione"]), "colore": m["colore"],
        "livello": m["livello"],
        "onda_media_giorno": round(luce_ore["VHM0"].mean(), 2),
        "vento_medio_giorno": round(luce_ore["vento"].mean()),
    }


def main():
    sys.stdout.reconfigure(line_buffering=True)
    spot_per_id = {s["id"]: s for s in carica_spot()}
    date_tutte = sorted({date.fromisoformat(g) for g, _, _ in GIORNATE})
    inizio, fine = date_tutte[0], date_tutte[-1]
    dati = {}
    for chiave, spot_id in SPOT.items():
        spot = spot_per_id[spot_id]
        print(f"{spot['nome']}: scarico onde {inizio} - {fine}...")
        onde = onde_storiche(spot, pd.Timestamp(inizio), pd.Timestamp(fine) + pd.Timedelta(hours=23))
        print(f"{spot['nome']}: {onde['VHM0'].notna().sum()} ore di onde; scarico il vento...")
        vento, luce = vento_storico(spot, inizio, fine)
        dati[chiave] = (spot, onde, vento, luce)

    righe = []
    for g, dove, didascalia in GIORNATE:
        giorno = date.fromisoformat(g)
        for chiave in ([dove] if dove else list(SPOT)):
            spot, onde, vento, luce = dati[chiave]
            r = giornata(spot, onde, vento, luce, giorno)
            righe.append({"data": g, "spot": chiave, "spot_detto": bool(dove),
                          "didascalia": didascalia, **(r or {"voto_max": None})})
    tab = pd.DataFrame(righe)
    cartella = RADICE / "data" / "collaudo"
    cartella.mkdir(parents=True, exist_ok=True)
    tab.to_csv(cartella / "collaudo.csv", index=False)

    # una riga per giornata: lo spot detto, oppure il migliore dei due
    per_giorno = (tab.dropna(subset=["voto_max"]).sort_values("voto_max", ascending=False)
                  .drop_duplicates("data").sort_values("data"))
    pd.set_option("display.width", 250)
    pd.set_option("display.max_rows", 300)
    print("\n=== Giornata per giornata (spot detto o il migliore dei due) ===")
    print(per_giorno[["data", "spot", "voto_max", "ora", "onda_largo", "periodo", "dir_onda",
                      "vento", "dir_vento", "colore", "livello", "didascalia"]].to_string(index=False))
    print("\n=== Riepilogo ===")
    fasce = pd.cut(per_giorno["voto_max"], [-0.1, 0.9, 1.9, 2.9, 5], labels=["0-0,5", "1-1,5", "2-2,5", "3-5"])
    print(fasce.value_counts().sort_index().to_string())
    print(f"Giornate: {len(per_giorno)}; voto medio {per_giorno['voto_max'].mean():.2f}")
    for chiave in SPOT:
        s = tab[(tab["spot"] == chiave)].dropna(subset=["voto_max"])
        print(f"{chiave}: voto medio {s['voto_max'].mean():.2f} su {len(s)} giornate")


if __name__ == "__main__":
    main()
