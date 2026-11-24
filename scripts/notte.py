"""Com'erano onda e vento nelle ore prima di un'osservazione.

Serve a capire se un mare in calo con vento da terra da molte ore cala
piu' in fretta di quanto dice il modello. Stampa soltanto: non scrive file.

    python scripts/notte.py          (le osservazioni di OSSERVAZIONI)
"""
import sys

import pandas as pd

from comune import carica_spot
from osservazioni import onde_del_giorno, vento_del_giorno
from voto import FUSO

sys.stdout.reconfigure(line_buffering=True)

# (spot, giorno e ora dell'osservazione, ora di Roma, giudizio di Enrico)
OSSERVAZIONI = [
    ("fregene", "2026-11-14 15:30", "4, principianti"),
    ("fregene", "2026-11-24 09:30", "2,5, ondine a riva"),
    ("santa-severa", "2026-10-22 12:00", "4-4,5"),
    ("santa-severa", "2026-10-24 11:00", "3"),
]
ORE_PRIMA = 24


def da_terra(direzione, esposizione, ampiezza=60):
    """True se il vento viene da terra: entro ampiezza gradi dall'opposto dell'esposizione."""
    return abs((direzione - (esposizione + 180) + 180) % 360 - 180) <= ampiezza


def main():
    spot_per_id = {s["id"]: s for s in carica_spot()}
    for sid, quando, giudizio in OSSERVAZIONI:
        spot = spot_per_id[sid]
        t = pd.Timestamp(quando).tz_localize(FUSO)
        giorno = t.date()
        try:
            onde = onde_del_giorno(spot, giorno)
            onde.index = pd.to_datetime(onde.index).tz_localize("UTC").tz_convert(FUSO)
            vento, _, _ = vento_del_giorno(spot, giorno)
            vento.index = pd.to_datetime(vento.index).tz_localize("UTC").tz_convert(FUSO)
        except Exception as errore:  # noqa: BLE001
            print(f"{sid} {quando}: dati non disponibili ({str(errore)[:120]})")
            continue
        tab = onde.join(vento[["vento", "direzione", "raffiche"]], how="inner")
        tab = tab.loc[t - pd.Timedelta(hours=ORE_PRIMA): t + pd.Timedelta(hours=1)]
        tab["da_terra"] = [da_terra(d, spot["esposizione"]) and v >= 4
                           for d, v in zip(tab["direzione"], tab["vento"])]
        # ore di fila con vento da terra, contando all'indietro dall'osservazione
        fila = 0
        for x in tab.loc[:t, "da_terra"][::-1]:
            if not x:
                break
            fila += 1
        h_ora = tab["VHM0"].asof(t)
        h_prima = tab["VHM0"].asof(t - pd.Timedelta(hours=12))
        print(f"\n=== {spot['nome']}, {quando} (Enrico: {giudizio})")
        print(f"onda {h_prima:.2f} m 12 ore prima -> {h_ora:.2f} m ({100 * (h_ora / h_prima - 1):+.0f}%), "
              f"vento da terra da {fila} ore di fila")
        colonne = [c for c in ["VHM0", "VTM01_SW1", "VTPK", "VMDR", "VHM0_WW", "vento", "direzione", "raffiche", "da_terra"]
                   if c in tab.columns]
        righe = tab[colonne].iloc[::2].round(2)
        righe.index = righe.index.strftime("%d %H:%M")
        print(righe.to_string())


if __name__ == "__main__":
    main()
