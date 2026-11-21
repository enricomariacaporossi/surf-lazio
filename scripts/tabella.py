"""Unisce onde e vento in una tabella oraria per spot (passo 2.3).

Uso (dalla cartella del progetto):
    .venv\\Scripts\\python scripts\\tabella.py

Ogni riga e' un'ora (indice in UTC) con:
- le onde Copernicus (VHM0, VMDR, VTPK, swell, mare di vento);
- vento, raffiche, pressione, pioggia, codice meteo, fonte del vento;
- ora_locale: l'ora italiana;
- di_giorno: True dalla prima luce (mezz'ora prima dell'alba) al tramonto;
- giorno: 1 = oggi, 2 = domani... (0 o meno = ore gia' passate).
"""
import pandas as pd

from comune import RADICE, carica_spot

FUSO = "Europe/Rome"


def tabella_spot(spot, onde=None, vento=None, luce=None):
    """Tabella oraria di uno spot. Se onde e vento non sono dati, li scarica."""
    if onde is None:
        from onde import scarica_onde
        onde = scarica_onde(spot)
    if vento is None or luce is None:
        from vento import scarica_vento
        vento, luce = scarica_vento(spot)

    # solo le ore presenti in entrambe le fonti
    t = onde.join(vento, how="inner")
    t.index = pd.DatetimeIndex(t.index).tz_localize("UTC")
    t.index.name = "ora_utc"

    t["ora_locale"] = t.index.tz_convert(FUSO)

    # alba e tramonto del giorno (UTC) di ogni riga
    giorni_utc = pd.Index(t.index.date)
    alba = pd.to_datetime(giorni_utc.map(luce["alba"])).tz_localize("UTC")
    tramonto = pd.to_datetime(giorni_utc.map(luce["tramonto"])).tz_localize("UTC")
    # si entra in acqua gia' con la prima luce: mezz'ora prima dell'alba
    t["di_giorno"] = (t.index >= alba - pd.Timedelta(minutes=30)) & (t.index <= tramonto)

    oggi = pd.Timestamp.now(tz=FUSO).normalize()
    t["giorno"] = (t["ora_locale"].dt.normalize() - oggi).dt.days + 1
    return t


if __name__ == "__main__":
    cartella = RADICE / "prove"
    cartella.mkdir(exist_ok=True)
    for spot in carica_spot():
        t = tabella_spot(spot)
        uscita = cartella / f"tabella_{spot['id']}.csv"
        t.to_csv(uscita)
        luce = t[t["di_giorno"]]
        print(f"\n{spot['nome']}: {len(t)} ore, di cui {len(luce)} di luce,"
              f" salvate in prove/{uscita.name}")
        # un colpo d'occhio: le 8, le 11 e le 14 italiane di ogni giorno
        scelta = luce[luce["ora_locale"].dt.hour.isin([8, 11, 14])]
        vista = scelta[["ora_locale", "giorno", "VHM0", "VTPK", "VMDR",
                        "vento", "direzione", "fonte"]].copy()
        vista["ora_locale"] = vista["ora_locale"].dt.strftime("%a %d %H:%M")
        print(vista.round(1).to_string(index=False))
