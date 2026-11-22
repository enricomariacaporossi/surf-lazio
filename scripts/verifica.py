"""Verifica automatica (Fase 6): quanto ci prende la previsione, senza diario.

Uso (dalla cartella del progetto):
    .venv\\Scripts\\python scripts\\verifica.py

Lo lancia aggiorna.py a ogni giro e scrive data/verifica.json, che la pagina
mostra in fondo. Parte davvero quando lo storico copre almeno 14 giorni.

Come funziona:
- in data/storico/ ci sono due copie al giorno della previsione;
- per ogni ora gia' passata, il «com'e' andata» e' il valore della copia salvata
  piu' tardi, quando quell'ora era gia' alle spalle: per l'onda e' l'analisi
  Copernicus (il modello corretto con le misure da satellite), per il vento
  il modello rifatto a posteriori;
- si confronta con quello che le copie precedenti prevedevano 1, 2 e 3 giorni
  prima, sugli ultimi 30 giorni.
Limite da ricordare: e' sempre un modello, al largo. Dice quanto cambiano le
previsioni, non com'e' la riva; per quello ci sono webcam e pulsanti Telegram.
"""
import json
import re
from datetime import datetime
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

from comune import RADICE, carica_spot

DATI = RADICE / "data"
STORICO = DATI / "storico"
RISCONTRI = DATI / "telegram" / "riscontri.csv"
GIORNI_MINIMI = 14
FINESTRA_GIORNI = 30
ANTICIPI = (1, 2, 3)                 # giorni di anticipo da valutare
CARDINALI = ["N", "NE", "E", "SE", "S", "SO", "O", "NO"]
NOMI_VENTO = {"N": "Tramontana", "NE": "Grecale", "E": "Levante", "SE": "Scirocco",
              "S": "Ostro", "SO": "Libeccio", "O": "Ponente", "NO": "Maestrale"}
# un caso «sbaglia sempre nello stesso verso» se, con abbastanza ore e giorni,
# lo scarto medio e' grande e quasi sempre dello stesso segno
SCARTO_ONDA = 0.2      # m
SCARTO_VENTO = 6       # km/h
STESSO_VERSO = 0.75
ORE_MINIME = 24
GIORNI_DIVERSI = 3


def numero(x, decimali=1):
    return f"{x:.{decimali}f}".replace(".", ",")


def cardinale(gradi):
    return CARDINALI[int(((gradi % 360) + 22.5) // 45) % 8]


def ora_del_file(nome):
    """2026-11-22_am_... -> 2026-11-22 00:30 UTC; pm -> 12:30 UTC (primo giro della mezza giornata)."""
    m = re.match(r"(\d{4}-\d{2}-\d{2})_(am|pm)_", nome)
    if not m:
        return None
    base = pd.Timestamp(m.group(1), tz="UTC")
    return base + pd.Timedelta(hours=0 if m.group(2) == "am" else 12, minutes=30)


def carica_storico(spot_id, cartella=STORICO):
    """Elenco (ora della previsione, tabella) di uno spot, dal piu' vecchio."""
    copie = []
    for file in sorted(cartella.glob(f"*_{spot_id}.csv")):
        quando = ora_del_file(file.name)
        if quando is None:
            continue
        t = pd.read_csv(file)
        t.index = pd.to_datetime(t.pop("ora_utc"), utc=True)
        copie.append((quando, t))
    copie.sort(key=lambda c: c[0])
    return copie


def com_e_andata(copie, colonne=("VHM0", "vento", "direzione")):
    """Per ogni ora passata, il valore della copia piu' recente che la contiene
    con almeno 6 ore di distacco (quindi come analisi, non come previsione)."""
    pezzi = []
    for quando, t in copie:
        passate = t[t.index <= quando - pd.Timedelta(hours=6)]
        if not passate.empty:
            pezzi.append(passate[[c for c in colonne if c in passate]])
    if not pezzi:
        return pd.DataFrame(columns=list(colonne))
    tutto = pd.concat(pezzi)
    return tutto[~tutto.index.duplicated(keep="last")].sort_index()


def confronti(copie, vero, dal):
    """Una riga per (copia, ora futura) con previsto, vero e anticipo in giorni."""
    righe = []
    for quando, t in copie:
        future = t[(t.index > quando) & (t.index >= dal)]
        future = future[future.index.isin(vero.index)]
        if future.empty:
            continue
        anticipo = np.ceil((future.index - quando) / pd.Timedelta(hours=24)).astype(int)
        v = vero.loc[future.index]
        righe.append(pd.DataFrame({
            "anticipo": anticipo,
            "onda_prev": future["VHM0"].to_numpy(), "onda_vera": v["VHM0"].to_numpy(),
            "vento_prev": future["vento"].to_numpy(), "vento_vero": v["vento"].to_numpy(),
            "dir_vera": v["direzione"].to_numpy(),
            "giorno": future.index.date,
        }, index=future.index))
    if not righe:
        return pd.DataFrame()
    c = pd.concat(righe).dropna(subset=["onda_prev", "onda_vera"])
    c["err_onda"] = c["onda_prev"] - c["onda_vera"]
    c["err_vento"] = c["vento_prev"] - c["vento_vero"]
    c["settore"] = c["dir_vera"].map(cardinale)
    return c


def riepilogo(c):
    """Errore medio (quanto sbaglia) e scarto (in che verso) per anticipo."""
    tabella = []
    for a in ANTICIPI:
        s = c[c["anticipo"] == a]
        if s.empty:
            continue
        tabella.append({
            "giorni": a, "ore": int(len(s)),
            "onda_errore_m": round(float(s["err_onda"].abs().mean()), 2),
            "onda_scarto_m": round(float(s["err_onda"].mean()), 2),
            "vento_errore_kmh": round(float(s["err_vento"].abs().mean()), 1),
            "vento_scarto_kmh": round(float(s["err_vento"].mean()), 1),
        })
    return tabella


def sempre_nello_stesso_verso(c):
    """I venti con cui la previsione sbaglia quasi sempre dalla stessa parte."""
    proposte = []
    vicini = c[c["anticipo"].isin(ANTICIPI)]
    for settore, s in vicini.groupby("settore"):
        if len(s) < ORE_MINIME or s["giorno"].nunique() < GIORNI_DIVERSI:
            continue
        nome = f"vento da {settore} ({NOMI_VENTO[settore]})"
        for colonna, soglia, cosa, unita, decimali in (
                ("err_onda", SCARTO_ONDA, "l'onda prevista", "m", 1),
                ("err_vento", SCARTO_VENTO, "il vento previsto", "km/h", 0)):
            media = s[colonna].mean()
            stesso = (np.sign(s[colonna]) == np.sign(media)).mean()
            if abs(media) >= soglia and stesso >= STESSO_VERSO:
                verso = "più alta" if media > 0 else "più bassa"
                if colonna == "err_vento":
                    verso = "più forte" if media > 0 else "più debole"
                proposte.append(
                    f"Con {nome} {cosa} è stata quasi sempre {verso} di come è andata: "
                    f"in media {numero(abs(media), decimali)} {unita} "
                    f"({int(len(s))} ore in {s['giorno'].nunique()} giorni). "
                    "Si può correggere il voto in questi casi: decidi tu.")
    return proposte


def leggi_riscontri(spot_id, dal):
    """Le risposte ai pulsanti Telegram: meglio, come previsto, peggio."""
    try:
        r = pd.read_csv(RISCONTRI)
    except (FileNotFoundError, pd.errors.EmptyDataError):
        return None
    r = r[(r["spot"] == spot_id) & (pd.to_datetime(r["giorno"]) >= dal.tz_localize(None))]
    if r.empty:
        return None
    conta = r["esito"].value_counts()
    meglio, come, peggio = (int(conta.get(k, 0)) for k in ("meglio", "come previsto", "peggio"))
    totale = meglio + come + peggio
    giudizio = None
    if totale >= 5:
        if peggio / totale >= 0.6:
            giudizio = "Il voto sembra troppo generoso: più volte è andata peggio del previsto."
        elif meglio / totale >= 0.6:
            giudizio = "Il voto sembra troppo severo: più volte è andata meglio del previsto."
        elif (come / totale) >= 0.5:
            giudizio = "Il voto sembra giusto: quasi sempre è andata come previsto."
    per_chi = {}
    if "chi" in r:
        for chi, g in r.groupby("chi"):
            per_chi[str(int(chi))] = {k: int((g["esito"] == v).sum()) for k, v in
                                      (("meglio", "meglio"), ("come", "come previsto"), ("peggio", "peggio"))}
    return {"meglio": meglio, "come": come, "peggio": peggio,
            "per_chi": per_chi, "giudizio": giudizio}


def verifica_spot(spot, cartella=STORICO, adesso=None):
    adesso = adesso or pd.Timestamp.now(tz="UTC")
    dal = (adesso - pd.Timedelta(days=FINESTRA_GIORNI)).floor("D")
    copie = carica_storico(spot["id"], cartella)
    giorni = sorted({q.date() for q, _ in copie})
    risultato = {
        "id": spot["id"], "nome": spot["nome"],
        "giorni_storico": len(giorni),
        "dal": giorni[0].isoformat() if giorni else None,
        "pronta": len(giorni) >= GIORNI_MINIMI,
        "riscontri": leggi_riscontri(spot["id"], dal),
    }
    if not risultato["pronta"]:
        return risultato
    vero = com_e_andata(copie)
    c = confronti(copie, vero, dal)
    risultato["anticipi"] = riepilogo(c) if not c.empty else []
    risultato["proposte"] = sempre_nello_stesso_verso(c) if not c.empty else []
    return risultato


def main(cartella=STORICO, adesso=None):
    spot = [verifica_spot(s, cartella, adesso) for s in carica_spot()]
    uscita = {
        # ora di Roma: su GitHub il server e' in UTC
        "aggiornato": datetime.now(ZoneInfo("Europe/Rome")).strftime("%Y-%m-%dT%H:%M"),
        "giorni_minimi": GIORNI_MINIMI,
        "finestra_giorni": FINESTRA_GIORNI,
        "spot": spot,
    }
    (DATI / "verifica.json").write_text(
        json.dumps(uscita, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    for s in spot:
        if not s["pronta"]:
            print(f"Verifica {s['nome']}: storico di {s['giorni_storico']} giorni su "
                  f"{GIORNI_MINIMI}, parte più avanti.")
        else:
            righe = ", ".join(f"{a['giorni']} g: onda ±{numero(a['onda_errore_m'], 2)} m"
                              for a in s["anticipi"])
            print(f"Verifica {s['nome']}: {righe}; proposte: {len(s['proposte'])}")
    return uscita


if __name__ == "__main__":
    main()
