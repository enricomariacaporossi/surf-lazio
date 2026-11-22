"""Cosa diceva il modello nelle ore delle osservazioni dal vivo (data/osservazioni.csv).

Per ogni riga (data, ora italiana, spot) scarica onde Copernicus e vento
Open-Meteo di quel giorno, ricalcola il voto con le regole di adesso e scrive
data/osservazioni_modello.csv. Si lancia da GitHub: Actions > collaudo >
Run workflow, scegliendo «osservazioni».
"""
import sys
from datetime import date, timedelta

import pandas as pd

from comune import RADICE, carica_spot
from voto import FUSO, calcola_ore

URL_ARCHIVIO = "https://historical-forecast-api.open-meteo.com/v1/forecast"
OSSERVAZIONI = RADICE / "data" / "osservazioni.csv"
USCITA = RADICE / "data" / "osservazioni_modello.csv"


def onde_del_giorno(spot, giorno):
    import copernicusmarine
    from onde import DATASET, VARIABILI
    lat, lon = spot["cella"]["lat"], spot["cella"]["lon"]
    ds = copernicusmarine.open_dataset(
        dataset_id=DATASET,
        minimum_latitude=lat - 0.03, maximum_latitude=lat + 0.03,
        minimum_longitude=lon - 0.03, maximum_longitude=lon + 0.03,
        start_datetime=pd.Timestamp(giorno) - pd.Timedelta(days=1),
        end_datetime=pd.Timestamp(giorno) + pd.Timedelta(hours=23),
    )
    presenti = [v for v in VARIABILI if v in ds.data_vars]
    punto = ds[presenti].sel(latitude=lat, longitude=lon, method="nearest")
    return punto.to_dataframe()[presenti].reindex(columns=VARIABILI)


def ha_dati(risposta):
    """True se la risposta ha almeno un valore orario non vuoto."""
    orarie = risposta.json().get("hourly", {})
    return any(v is not None for k, valori in orarie.items() if k != "time" for v in valori)


def vento_del_giorno(spot, giorno):
    """Come vento.scarica_vento, ma per un giorno passato (date di inizio e fine)."""
    from vento import MODELLI, URL, VARIABILI, ATTESA, SESSIONE
    punto = spot["vento_punto"]
    tabelle = {}
    for nome, modello in MODELLI.items():
        parametri = {
            "latitude": punto["lat"], "longitude": punto["lon"],
            "hourly": ",".join(VARIABILI), "daily": "sunrise,sunset",
            "models": modello, "timezone": "GMT", "wind_speed_unit": "kmh",
            "start_date": (giorno - timedelta(days=1)).isoformat(),
            "end_date": giorno.isoformat(),
        }
        r = None
        # il servizio delle previsioni tiene circa 3 mesi; per i giorni piu'
        # vecchi si passa all'archivio delle previsioni (stessa forma)
        for indirizzo in (URL, URL_ARCHIVIO):
            try:
                r = SESSIONE.get(indirizzo, params=parametri, timeout=ATTESA)
            except Exception as errore:  # noqa: BLE001  ICON-2I e' un di piu', ECMWF no
                print(f"  {nome}: non risponde ({str(errore)[:80]})")
                r = None
                continue
            if r.status_code == 200 and ha_dati(r):
                break
            print(f"  {nome}: niente da {indirizzo.split('/')[2]} ({r.status_code})")
            r = None
        if r is None:
            continue
        dati = r.json()
        orarie = pd.DataFrame(dati["hourly"])
        orarie["time"] = pd.to_datetime(orarie["time"])
        tabelle[nome] = (orarie.set_index("time").rename(columns=VARIABILI), dati["daily"])
    ecmwf, giornaliere = tabelle["ECMWF"]
    icon = tabelle.get("ICON-2I", (pd.DataFrame(index=ecmwf.index, columns=ecmwf.columns), None))[0]
    v = icon.reindex(ecmwf.index)[list(VARIABILI.values())].combine_first(ecmwf[list(VARIABILI.values())])
    v["fonte"] = "ECMWF"
    v.loc[icon.reindex(ecmwf.index)["vento"].notna(), "fonte"] = "ICON-2I"
    v["vento_ecmwf"], v["direzione_ecmwf"] = ecmwf["vento"], ecmwf["direzione"]
    luce = pd.DataFrame(giornaliere)
    luce["time"] = pd.to_datetime(luce["time"]).dt.date
    luce = luce.set_index("time")
    return v, pd.to_datetime(luce.loc[giorno, "sunrise"]), pd.to_datetime(luce.loc[giorno, "sunset"])


def main():
    sys.stdout.reconfigure(line_buffering=True)
    spot_per_id = {s["id"]: s for s in carica_spot()}
    oss = pd.read_csv(OSSERVAZIONI, dtype=str)
    # quelle gia' calcolate restano: si fanno solo le nuove
    try:
        fatte = pd.read_csv(USCITA, dtype=str)
    except FileNotFoundError:
        fatte = pd.DataFrame(columns=["osservazione", "spot"])
    gia = set(zip(fatte["osservazione"], fatte["spot"]))
    righe = []
    for _, o in oss.iterrows():
        if (f"{o['data']} {o['ora']}", o["spot"]) in gia:
            continue
        spot = spot_per_id[o["spot"]]
        giorno = date.fromisoformat(o["data"])
        print(f"{o['data']} {o['ora']} {spot['nome']}...")
        try:
            onde = onde_del_giorno(spot, giorno)
            vento, alba, tramonto = vento_del_giorno(spot, giorno)
        except Exception as errore:  # noqa: BLE001
            print(f"  saltata: {str(errore)[:160]}")
            continue
        t = onde.join(vento, how="inner")
        t.index = pd.DatetimeIndex(t.index).tz_localize("UTC")
        t["ora_locale"] = t.index.tz_convert(FUSO)
        t["di_giorno"] = (t.index >= alba.tz_localize("UTC") - pd.Timedelta(minutes=30)) \
            & (t.index <= tramonto.tz_localize("UTC"))
        t["giorno"] = 1
        t = calcola_ore(t, spot)
        quando = pd.Timestamp(f"{o['data']} {o['ora']}").tz_localize(FUSO).floor("h")
        intorno = t[(t["ora_locale"] >= quando - pd.Timedelta(hours=1))
                    & (t["ora_locale"] <= quando + pd.Timedelta(hours=1))]
        for _, r in intorno.iterrows():
            righe.append({
                "osservazione": f"{o['data']} {o['ora']}", "spot": o["spot"],
                "ora": r["ora_locale"].strftime("%Y-%m-%d %H:%M"),
                "onda_largo": round(r["VHM0"], 2), "onda_riva": round(r["onda_riva"], 2),
                "periodo_picco": round(r["VTPK"], 1), "parte": r["parte"],
                "dir_onda": round(r["d_parte"]), "vento": round(r["vento"]),
                "raffiche": round(r["raffiche"]), "dir_vento": round(r["direzione"]),
                "colore": r["colore"], "voto": r["voto"], "livello": r["livello"],
                "cosa_si_vede": o["cosa_si_vede"],
            })
    nuove = pd.DataFrame(righe)
    pd.concat([fatte, nuove.astype(str)] if not fatte.empty else [nuove]).to_csv(USCITA, index=False)
    pd.set_option("display.width", 250)
    if nuove.empty:
        print("Nessuna osservazione nuova.")
    else:
        print(nuove.drop(columns=["cosa_si_vede"]).to_string(index=False))


if __name__ == "__main__":
    main()
