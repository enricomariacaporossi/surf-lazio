"""Fronte in arrivo: in quale delle sette tappe della seconda guida siamo.

Uso (dalla cartella del progetto):
    .venv\\Scripts\\python scripts\\fronte.py --da-csv

«Il vento che gira», sezione 4: al passaggio di un fronte freddo la pressione
scende, tocca un minimo e risale, mentre il vento gira in senso orario
da Sud-Est a Sud, Sud-Ovest, Ovest, Nord-Ovest e Nord. Lo script cerca questi
minimi nella previsione e da li' assegna a ogni ora la sua tappa.
E' uno schema semplificato, come quello della guida: i fronti veri non sono
mai cosi' ordinati, e le ore che non tornano restano senza tappa.
"""
import sys

import numpy as np
import pandas as pd

from comune import RADICE, carica_spot

# nome della tappa e cosa succede in spiaggia, dalla tabella della guida
TAPPE = {
    1: ("prima", "Vento debole e alta pressione: mare tranquillo, a volte onda residua."),
    2: ("avvicinamento", "Vento da Sud-Est in aumento e pressione che comincia a scendere: "
                         "di lato, surfabile quasi sempre, ma sporca."),
    3: ("pre-frontale", "Vento da Sud e Sud-Ovest, pressione in calo, onde corte e disordinate: "
                        "da evitare, è mareggiata."),
    4: ("fronte", "Il vento gira a Ovest con raffiche, minimo di pressione, temporali: "
                  "fuori dall'acqua."),
    5: ("dopo il fronte", "Ovest, poi Nord-Ovest, forte ma in calo; la pressione risale. "
                          "Con Ovest da evitare, con Nord-Ovest arriva la scaduta."),
    6: ("scaduta", "Nord-Ovest, Nord, Nord-Est, il vento cala: il meglio dall'alba "
                   "alle 10 circa, poi l'onda cala e il mare si spiana."),
    7: ("bel tempo", "Vento debole, spesso da Est, alta pressione: onda piccola, quasi piatto."),
}

# soglie dello schema (hPa, gradi, ore)
CALO_MINIMO = 3.0       # la pressione deve essere scesa almeno di tanto nelle 36 ore prima
RISALITA_MINIMA = 1.0   # e risalire almeno di tanto nelle 24 ore dopo
GIRO_MINIMO = 45        # rotazione oraria del vento intorno al minimo


def tra(d, da, a):
    """Direzione d (gradi) dentro il settore da-a, anche a cavallo del Nord."""
    d = np.asarray(d, dtype=float) % 360
    return (d >= da) & (d <= a) if da <= a else (d >= da) | (d <= a)


def giro(direzioni):
    """Somma dei cambi di direzione: positiva = senso orario."""
    d = np.asarray(direzioni, dtype=float)
    d = d[~np.isnan(d)]
    return float(((np.diff(d) + 540) % 360 - 180).sum()) if len(d) > 1 else 0.0


def trova_fronti(t):
    """Indici (posizioni) dei minimi di pressione che sono passaggi di fronte."""
    p = t["pressione"].rolling(3, center=True, min_periods=1).mean().to_numpy()
    direzioni = t["direzione"].to_numpy()
    n = len(p)
    fronti = []
    for m in range(n):
        finestra = p[max(0, m - 12): m + 13]
        if np.isnan(p[m]) or p[m] > np.nanmin(finestra):
            continue
        prima, dopo = p[max(0, m - 36): m], p[m + 1: m + 25]
        if len(prima) < 6 or len(dopo) < 6:
            continue  # troppo vicino all'inizio o alla fine della previsione
        if np.nanmax(prima) - p[m] < CALO_MINIMO or np.nanmax(dopo) - p[m] < RISALITA_MINIMA:
            continue
        if giro(direzioni[max(0, m - 12): m + 13]) < GIRO_MINIMO:
            continue
        if fronti and m - fronti[-1] < 18:
            # due minimi vicini sono lo stesso fronte: vale il piu' basso
            if p[m] < p[fronti[-1]]:
                fronti[-1] = m
            continue
        fronti.append(m)
    return fronti, p


def assegna_tappe(t):
    """Aggiunge le colonne tappa (0 = nessuna, 1-7) e fronte (True al passaggio)."""
    t = t.copy()
    n = len(t)
    tappa = np.zeros(n, dtype=int)
    fronti, p = trova_fronti(t)
    d = t["direzione"].to_numpy(dtype=float)
    v = t["vento"].to_numpy(dtype=float)
    codice = t["codice"].fillna(0).to_numpy()
    cala6 = np.r_[np.full(6, np.nan), p[6:] - p[:-6]]  # variazione nelle ultime 6 ore

    # prima le tappe che portano al fronte (2, 3, 4): hanno la precedenza
    margini = {}
    for m in fronti:
        dentro = [i for i in range(max(0, m - 6), min(n, m + 7))
                  if abs(i - m) <= 2 or codice[i] >= 95]
        tappa[dentro] = 4
        margini[m] = (min(dentro), max(dentro))
        i = margini[m][0] - 1
        while i >= 0 and m - i <= 24 and tappa[i] == 0 and tra(d[i], 150, 260):
            tappa[i] = 3
            i -= 1
        inizio = i
        while i >= 0 and inizio - i <= 36 and tappa[i] == 0 and tra(d[i], 80, 180) \
                and not (cala6[i] > 0.5):
            tappa[i] = 2
            i -= 1

    # poi quelle che lo seguono (5, 6), solo dove non c'e' gia' il fronte dopo
    for m in fronti:
        i = margini[m][1] + 1
        while i < n and i - m <= 30 and tappa[i] == 0 and tra(d[i], 220, 345) and v[i] >= 15:
            tappa[i] = 5
            i += 1
        inizio = i
        while i < n and i - inizio <= 36 and tappa[i] == 0 \
                and (tra(d[i], 290, 70) or v[i] < 10) and not (cala6[i] < -1):
            tappa[i] = 6
            i += 1

    # infine la calma: 7 se un fronte e' passato da poco, 1 se il prossimo e' vicino
    calmo = (v < 15) & ~(cala6 < -1)
    for i in range(n):
        if tappa[i] or not calmo[i]:
            continue
        passato = [i - m for m in fronti if i > m]
        arriva = [m - i for m in fronti if m > i]
        if passato and min(passato) <= 48:
            tappa[i] = 7
        elif arriva and min(arriva) <= 48:
            tappa[i] = 1
        elif passato and min(passato) <= 72:
            tappa[i] = 7

    # buchi di poche ore tra due ore della stessa tappa: si riempiono
    for i in range(1, n - 1):
        if tappa[i]:
            continue
        prima = next((tappa[j] for j in range(i - 1, max(-1, i - 4), -1) if tappa[j]), 0)
        dopo = next((tappa[j] for j in range(i + 1, min(n, i + 4)) if tappa[j]), 0)
        if prima and prima == dopo:
            tappa[i] = prima

    t["tappa"] = tappa
    t["fronte"] = False
    if fronti:
        t.iloc[fronti, t.columns.get_loc("fronte")] = True
    return t


def riassunto_fronte(t):
    """Per la pagina: la tappa di adesso e quando passa il prossimo fronte."""
    from voto import FUSO
    adesso = pd.Timestamp.now(tz=FUSO).floor("h")
    passate = t[t["ora_locale"] <= adesso]
    riga = passate.iloc[-1] if not passate.empty else t.iloc[0]
    n = int(riga["tappa"])
    prossimi = t[t["fronte"] & (t["ora_locale"] > adesso - pd.Timedelta(hours=3))]
    passaggi = []
    for ora, r in prossimi.iterrows():
        dopo = t[(t.index > ora) & (t.index <= ora + pd.Timedelta(hours=48)) & t["scaduta"]]
        passaggi.append({
            "ora": r["ora_locale"].strftime("%Y-%m-%dT%H:%M"),
            "scaduta": dopo["ora_locale"].iloc[0].strftime("%Y-%m-%dT%H:%M") if not dopo.empty else None,
        })
    return {
        "tappa": n,
        "nome": TAPPE[n][0] if n else None,
        "spiaggia": TAPPE[n][1] if n else None,
        "passaggi": passaggi[:2],
        # cosi' la pagina puo' ricalcolare la tappa all'ora in cui la apri
        "descrizioni": {str(k): v[1] for k, v in TAPPE.items()},
    }


if __name__ == "__main__":
    from voto import carica_tabella_csv, valuta_spot
    for spot in carica_spot():
        if "--da-csv" in sys.argv:
            t = carica_tabella_csv(RADICE / "prove" / f"tabella_{spot['id']}.csv")
        else:
            from tabella import tabella_spot
            t = tabella_spot(spot)
        t, _, _ = valuta_spot(spot, t)
        t = assegna_tappe(t)
        print(f"\n=== {spot['nome']} ===")
        for ora, r in t[t["fronte"]].iterrows():
            print(f"Fronte: {r['ora_locale']:%a %d %H:%M}, {r['pressione']:.0f} hPa")
        cambi = t[t["tappa"].ne(t["tappa"].shift())]
        for _, r in cambi.iterrows():
            nome = TAPPE[r["tappa"]][0] if r["tappa"] else "-"
            print(f"  dalle {r['ora_locale']:%a %d %H:%M}: tappa {r['tappa']} {nome}"
                  f"  (vento {r['vento']:.0f} da {r['direzione']:.0f}°, {r['pressione']:.0f} hPa)")
        print(riassunto_fronte(t))
