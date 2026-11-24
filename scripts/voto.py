"""Colori del vento, livelli, voto, fiducia e scaduta (Fase 3).

Uso (dalla cartella del progetto):
    .venv\\Scripts\\python scripts\\voto.py            scarica dati nuovi
    .venv\\Scripts\\python scripts\\voto.py --da-csv   usa prove/tabella_*.csv

Le regole vengono dalle due guide su Santa Severa e dalle schede di spots.json.
I coefficienti sono valori di partenza: la Fase 6 dira' se correggerli.
"""
import sys

import numpy as np
import pandas as pd

from comune import RADICE, carica_spot

FUSO = "Europe/Rome"

# fattore vento per colore e forza: sotto 10, 10-20, 20-30, oltre 30 km/h
FATTORE_VENTO = {
    "verde": (1.0, 1.0, 0.8, 0.5),
    "giallo": (1.0, 0.7, 0.5, 0.3),
    "rosso": (0.8, 0.5, 0.2, 0.1),
    "grigio": (1.0, 0.8, 0.6, 0.4),
}

# le parti del mare secondo Copernicus: altezza, direzione, periodo medio
PARTI = {
    "swell": ("VHM0_SW1", "VMDR_SW1", "VTM01_SW1"),
    "swell secondario": ("VHM0_SW2", "VMDR_SW2", "VTM01_SW2"),
    "mare di vento": ("VHM0_WW", "VMDR_WW", "VTM01_WW"),
}

# fasce orarie in ora italiana: la prima coincide con la finestra della scaduta
FASCE = [("alba-10", 0, 10), ("10-13", 10, 13), ("13-16", 13, 16), ("16-tramonto", 16, 24)]

CARDINALI = ["N", "NE", "E", "SE", "S", "SO", "O", "NO"]


# ---------------------------------------------------------------- strumenti

def diff_angolo(a, b):
    """Differenza tra due direzioni, da 0 a 180 gradi."""
    return abs((a - b + 540) % 360 - 180)


def cardinale(gradi):
    """Da gradi a punto cardinale in italiano (8 settori)."""
    return CARDINALI[int(((gradi % 360) + 22.5) // 45) % 8]


def numero(x, decimali=1):
    """Numero con la virgola, come si scrive in italiano."""
    return f"{x:.{decimali}f}".replace(".", ",")


# ---------------------------------------------------------- 1. colore vento

def colore_vento(direzione, spot):
    d = round(direzione) % 360
    for colore, settori in spot["vento"].items():
        if any(da <= d <= a for da, a in settori):
            return colore
    return "giallo"


def fattore_direzione(d, tabella, predefinito=1.0):
    """Il fattore di una tabella [[da, a, fattore], ...] per la direzione d (gradi).
    Serve agli spot riparati: quanta onda arriva a riva, quanto vento arriva in acqua."""
    if not tabella or d is None or pd.isna(d):
        return predefinito
    d = float(d) % 360
    for da, a, f in tabella:
        if (da <= d <= a) if da <= a else (d >= da or d <= a):
            return f
    return predefinito


def fattore_vento(vento, raffiche, colore):
    """Quanto il vento lascia del voto (da 0,1 a 1).

    I valori sono quelli delle quattro fasce della prima guida (sotto 10, 10-20,
    20-30, oltre 30 km/h), messi al centro di ogni fascia (5, 15, 25, 35 km/h)
    e uniti a rampa: cosi' 10 km/h non vale molto meno di 9.
    """
    f = float(np.interp(vento, [5, 15, 25, 35], FATTORE_VENTO[colore]))
    # vento rafficato: onde meno regolari (fino a -0,1, a rampa tra 5 e 15 km/h di scarto)
    f -= 0.1 * float(np.clip((raffiche - vento - 5) / 10, 0, 1))
    return max(f, 0.1)


# ------------------------------------------------------- 2. punteggio onda

def punteggio_altezza(h, a):
    """0 sotto il minimo; da 0,2 a 1 fino all'ottimale; 1 fino al massimo;
    poi cala fino a 0 all'altezza "zero" della scheda (oltre non si esce:
    troppa schiuma e onde che rompono lontano da riva)."""
    zero = a.get("zero", 2 * a["max"])
    if h < a["min"]:
        return 0.0
    if h <= a["ottimale"]:
        return 0.2 + 0.8 * (h - a["min"]) / (a["ottimale"] - a["min"])
    if h <= a["max"]:
        return 1.0
    return max(0.0, (zero - h) / (zero - a["max"]))


def punteggio_periodo(t, t_min):
    """0 sotto il periodo minimo; da 0,5 a 1 nei 3 secondi successivi."""
    if t < t_min:
        return 0.0
    return min(1.0, 0.5 + 0.5 * (t - t_min) / 3)


def punteggio_direzione(d, swell):
    """1 nel settore pieno; cala fino a 0,3 ai bordi della finestra; 0 fuori."""
    lo, hi = swell["finestra"]
    p_lo, p_hi = swell["pieno"]
    if not lo <= d <= hi:
        return 0.0
    if p_lo <= d <= p_hi:
        return 1.0
    if d < p_lo:
        return 0.3 + 0.7 * (d - lo) / (p_lo - lo)
    return 0.3 + 0.7 * (hi - d) / (hi - p_hi)


def parte_dominante(riga):
    """La parte del mare piu' alta in quell'ora: swell o mare di vento."""
    migliore = max(PARTI.items(), key=lambda kv: riga.get(kv[1][0], 0) or 0)
    nome, (h, d, t) = migliore
    return nome, riga[h], riga[d], riga[t]


# ------------------------------------------------------------ 3. livello

def livello(h, vento, colore, codice, spot):
    if 95 <= codice <= 99:
        return "nessuno (temporale)"
    if colore == "rosso" and vento > 30:
        return "nessuno"
    altezze = spot["altezzaVoto"]
    if h > altezze.get("zero", 2 * altezze["max"]):
        return "nessuno (troppo grosso)"
    if h < altezze["min"]:
        return "piatto"
    soglie = spot["livelli"]
    if h <= soglie["principianti"] and vento < 20 and colore != "rosso":
        return "principianti"
    if h <= soglie["intermedi"]:
        # su sabbia i principianti con le tavole morbide escono sulle schiume
        # o su qualche onda piccola (Enrico), se il vento non e' troppo forte
        if spot.get("fondale") == "sabbia" and vento < 30:
            return "intermedi, principianti sulle schiume"
        return "intermedi"
    # su sabbia, sopra la soglia degli intermedi ci vanno anche loro, se accompagnati
    # (Enrico, Castello del 24/10: «intermedi accompagnati perche' il fondo e' sabbia»)
    if soglie.get("accompagnati"):
        return "esperti o intermedi accompagnati"
    return "esperti"


# ---------------------------------------------------- 4. voto ora per ora

def calcola_ore(t, spot):
    """Aggiunge alla tabella oraria colore, fattore vento, voto, livello,
    fiducia, incertezza e la frase che spiega il voto."""
    t = t.copy()
    righe = []
    for _, r in t.iterrows():
        colore = colore_vento(r["direzione"], spot)
        # spot riparati: con certe direzioni in acqua il vento arriva piu' debole
        riparo = fattore_direzione(r["direzione"], spot.get("riduzioneVento"))
        vento_acqua, raffiche_acqua = r["vento"] * riparo, r["raffiche"] * riparo
        f_vento = fattore_vento(vento_acqua, raffiche_acqua, colore)
        nome, h_parte, d_parte, t_parte = parte_dominante(r)
        # spot riparati: a riva arriva solo una parte dell'onda del largo
        riduzione = fattore_direzione(d_parte, spot.get("riduzione"))
        h_riva, h_parte = r["VHM0"] * riduzione, h_parte * riduzione
        p_h = punteggio_altezza(h_riva, spot["altezzaVoto"])
        # periodo per il voto: quello della parte dominante (predefinito) oppure
        # il periodo di picco di tutto il mare, piu' vicino a quello delle app
        t_voto = t_parte
        if spot.get("periodo") == "picco" and pd.notna(r.get("VTPK")):
            t_voto = r["VTPK"]
        p_t = punteggio_periodo(t_voto, spot["periodoMin"])
        p_d = punteggio_direzione(d_parte, spot["swell"])
        mare_vento = spot.get("fattoreMareVento", 0.8)  # mare attivo: meno ordinato
        onda = np.sqrt(p_h * p_t) * p_d * (mare_vento if nome == "mare di vento" else 1.0)
        voto = round(5 * onda * f_vento * 2) / 2
        frase = (f"{nome} {numero(h_parte)} m, {numero(t_voto, 0)} s da "
                 f"{cardinale(d_parte)} · vento {numero(r['vento'], 0)} km/h da "
                 f"{cardinale(r['direzione'])} ({colore})")
        righe.append({
            "colore": colore, "fattore_vento": f_vento, "parte": nome,
            "h_parte": h_parte, "d_parte": d_parte, "t_parte": t_parte, "t_voto": t_voto,
            "punteggio_onda": round(onda, 2), "voto": voto, "onda_riva": h_riva,
            "livello": livello(h_riva, vento_acqua, colore, r["codice"], spot),
            "frase": frase,
        })
    t = t.join(pd.DataFrame(righe, index=t.index))

    # fiducia per distanza: come nelle guide
    t["fiducia"] = np.select(
        [t["giorno"] <= 0, t["giorno"] <= 3, t["giorno"] <= 7],
        ["passato", "previsione", "tendenza"], "fantameteo")

    # fiducia per accordo tra modelli. Vento: ICON-2I contro ECMWF, dove c'e' ICON-2I
    calmo = (t["vento"] < 5) | (t["vento_ecmwf"] < 5)
    diff_dir = diff_angolo(t["direzione"], t["direzione_ecmwf"])
    t["incerto_vento"] = (t["fonte"] == "ICON-2I") & (
        ((t["vento"] - t["vento_ecmwf"]).abs() > 10) | (~calmo & (diff_dir > 45)))
    # onda: Copernicus contro ECMWF WAM; oltre 0,3 m di differenza, o oltre un
    # quarto dell'onda quando il mare e' grosso (li' 0,3 m sono poca cosa)
    if "onda_ecmwf" in t:
        soglia = np.maximum(0.3, 0.25 * t["VHM0"])
        t["incerto_onda"] = (t["VHM0"] - t["onda_ecmwf"]).abs() > soglia
    else:
        t["incerto_onda"] = False
    t["incerto"] = t["incerto_vento"] | t["incerto_onda"]
    return t


# ------------------------------------------------------------- 5. scaduta

def rotazione(direzioni):
    """Somma dei cambi di direzione: positiva = senso orario."""
    d = np.asarray(direzioni, dtype=float)
    return float(((np.diff(d) + 540) % 360 - 180).sum())


def rileva_scaduta(t, spot):
    """Segna le ore dall'alba alle 10 dei giorni di scaduta (seconda guida):
    nelle 28 ore prima il vento e' girato in senso orario da S/SO a NO,
    la pressione ha toccato un minimo e risale, il periodo e' salito."""
    t = t.copy()
    t["scaduta"] = False
    t["antiorario"] = False
    for giorno in sorted(set(t["ora_locale"].dt.date)):
        mezzanotte = pd.Timestamp(giorno).tz_localize(FUSO)
        finestra = t[(t["ora_locale"] >= mezzanotte - pd.Timedelta(hours=18))
                     & (t["ora_locale"] <= mezzanotte + pd.Timedelta(hours=10))]
        mattino = finestra[finestra["ora_locale"] >= mezzanotte + pd.Timedelta(hours=6)]
        prima = finestra[finestra["ora_locale"] < mezzanotte + pd.Timedelta(hours=6)]
        if len(prima) < 12 or mattino.empty:
            continue

        # 2) pressione: minimo prima del mattino, poi risale di almeno 1 hPa
        risale = mattino["pressione"].mean() > prima["pressione"].min() + 1
        # 3) periodo dello swell salito di almeno 1 secondo
        periodo_sale = mattino["VTM01_SW1"].mean() - prima["VTM01_SW1"].min() >= 1
        # 4) c'e' onda
        onda = mattino["VHM0"].mean() >= spot["altezzaVoto"]["min"]
        if not (risale and periodo_sale and onda):
            continue

        # 1) rotazione del vento da S/SO verso NO
        direzioni = finestra["direzione"].to_numpy()
        da_sud = [i for i, d in enumerate(direzioni) if 150 <= d <= 250]
        if not da_sud:
            continue
        giro = rotazione(direzioni[da_sud[0]:])
        arriva_a_no = any((290 <= d <= 340) and v >= 10 for d, v in
                          zip(direzioni[da_sud[0]:], finestra["vento"].to_numpy()[da_sud[0]:]))
        ore_mattino = (t["ora_locale"].dt.date == giorno) & t["di_giorno"] \
            & (t["ora_locale"].dt.hour < 10)
        if giro > 60 and arriva_a_no:
            t.loc[ore_mattino, "scaduta"] = True
        elif giro < -60:
            t.loc[ore_mattino, "antiorario"] = True
    return t


def rileva_dopo_mareggiata(t, spot, ore=48):
    """Fondale di sabbia: dopo una mareggiata i banchi si spostano e i picchi
    vanno ritrovati (prima guida, sezione sicurezza)."""
    t = t.copy()
    soglia = spot.get("mareggiata", 2.0)
    massimo_prima = t["VHM0"].rolling(f"{ore}h", closed="left").max()
    t["dopo_mareggiata"] = (massimo_prima >= soglia) & (t["VHM0"] < soglia)
    return t


# un mare che cala in fretta con vento da terra da ore puo' essere, a riva,
# piu' piccolo di quanto dice il modello (Enrico, Levante 24 novembre).
# Per ora e' solo un avviso: il voto non cambia finche' non ci sono altre giornate.
CALO_MINIMO = 0.4        # l'onda e' scesa almeno del 40%...
CALO_ORE = 12            # ...nelle 12 ore prima
DA_TERRA_ORE = 8         # e il vento e' verde (da terra) da almeno 8 ore di fila


def rileva_calo_da_terra(t):
    t = t.copy()
    onda = t["VHM0"].astype(float)
    prima = onda.reindex(t.index - pd.Timedelta(hours=CALO_ORE)).to_numpy()
    calo = onda.to_numpy() <= (1 - CALO_MINIMO) * prima
    verde = (t["colore"] == "verde").astype(float)
    di_fila = verde.rolling(f"{DA_TERRA_ORE}h").min() >= 1
    # le prime ore della serie non hanno 8 ore alle spalle
    abbastanza = verde.rolling(f"{DA_TERRA_ORE}h").count() >= DA_TERRA_ORE
    t["calo_da_terra"] = calo & (di_fila & abbastanza).to_numpy()
    return t


# ------------------------------------------------- 6. fasce e finestra

def calcola_fasce(t):
    """Una riga per giorno e fascia oraria: vale l'ora migliore della fascia."""
    luce = t[t["di_giorno"] & (t["giorno"] >= 1)]
    righe = []
    for data, g in luce.groupby(luce["ora_locale"].dt.date):
        for nome, h0, h1 in FASCE:
            ore = g["ora_locale"].dt.hour
            sel = g[(ore >= h0) & (ore < h1)]
            if sel.empty:
                continue
            migliore = sel.loc[sel["voto"].idxmax()]
            segnali = []
            if sel["scaduta"].any() and migliore["voto"] > 0:
                segnali.append("scaduta: il meglio dall'alba alle 10, poi l'onda cala")
            elif sel["scaduta"].any():
                segnali.append("scaduta in corso, ma l'onda è ancora troppo grossa")
            # «dopo la mareggiata» non va qui: la pagina lo dice una volta sola,
            # accanto alla finestra migliore (vedi aggiorna.py)
            if sel["antiorario"].any():
                segnali.append("il vento gira al contrario: guarda la carta")
            if "calo_da_terra" in sel and sel["calo_da_terra"].any() and migliore["voto"] > 0:
                segnali.append("mare in calo con vento da terra: a riva può essere più piccolo del previsto")
            su = [cosa for cosa, colonna in (("onda", "incerto_onda"), ("vento", "incerto_vento"))
                  if sel[colonna].any()]
            if su:
                dove = ("su onda e vento" if len(su) == 2
                        else "sull'onda" if su[0] == "onda" else "sul vento")
                segnali.append(f"incerto: i modelli non sono d'accordo {dove}")
            righe.append({
                "data": data, "giorno": int(migliore["giorno"]), "fascia": nome,
                "ora": migliore["ora_locale"].strftime("%H:%M"),
                "voto": migliore["voto"], "livello": migliore["livello"],
                "colore": migliore["colore"], "fiducia": migliore["fiducia"],
                "onda_m": round(migliore["onda_riva"], 1),
                "vento_kmh": round(migliore["vento"]),
                "segnali": "; ".join(segnali), "frase": migliore["frase"],
                "dopo_mareggiata": bool(migliore["dopo_mareggiata"]),
                # ore di luce della fascia: d'inverno «16–tramonto» ne ha una sola
                # (meno di un'ora vera) e non si propone come momento migliore
                "ore_luce": int(len(sel)),
            })
    return pd.DataFrame(righe)


# una fascia con meno di un'ora di luce (d'inverno «16–tramonto», il tramonto
# e' alle 16:45) resta nella griglia ma non e' un momento da proporre
ORE_LUCE_MINIME = 2


def fascia_piena(f):
    return f.get("ore_luce", ORE_LUCE_MINIME) >= ORE_LUCE_MINIME


def finestra_migliore(fasce, giorni=5):
    """La fascia con il voto piu' alto nei prossimi giorni; a parita', la prima.
    Non le fasce con meno di un'ora di luce."""
    candidate = fasce[(fasce["giorno"] <= giorni) & (fasce["fiducia"] != "fantameteo")]
    if "ore_luce" in candidate:
        candidate = candidate[candidate["ore_luce"] >= ORE_LUCE_MINIME]
    if candidate.empty or candidate["voto"].max() == 0:
        return None
    return candidate.loc[candidate["voto"].idxmax()]


# ------------------------------------------------------------- utilita'

def carica_tabella_csv(percorso):
    """Rilegge una tabella salvata da tabella.py."""
    t = pd.read_csv(percorso)
    t.index = pd.to_datetime(t.pop("ora_utc"), utc=True)
    t["ora_locale"] = pd.to_datetime(t["ora_locale"], utc=True).dt.tz_convert(FUSO)
    t["di_giorno"] = t["di_giorno"].astype(str).str.lower() == "true"
    return t


def valuta_spot(spot, t):
    """Tutta la Fase 3 per uno spot: ore, scaduta, fasce, finestra migliore."""
    t = rileva_scaduta(calcola_ore(t, spot), spot)
    t = rileva_dopo_mareggiata(t, spot)
    t = rileva_calo_da_terra(t)
    fasce = calcola_fasce(t)
    return t, fasce, finestra_migliore(fasce)


if __name__ == "__main__":
    da_csv = "--da-csv" in sys.argv
    pd.set_option("display.width", 200)
    for spot in carica_spot():
        if da_csv:
            t = carica_tabella_csv(RADICE / "prove" / f"tabella_{spot['id']}.csv")
        else:
            from tabella import tabella_spot
            t = tabella_spot(spot)
        t, fasce, migliore = valuta_spot(spot, t)
        fasce.to_csv(RADICE / "prove" / f"fasce_{spot['id']}.csv", index=False)

        print(f"\n=== {spot['nome']} ===")
        if spot.get("avviso"):
            print(f"Attenzione: {spot['avviso']}")
        if migliore is None:
            print("Finestra migliore: nessuna nei prossimi 5 giorni.")
        else:
            print(f"Finestra migliore: {migliore['data']:%a %d} {migliore['fascia']}, "
                  f"voto {numero(migliore['voto'])}/5, {migliore['livello']} - "
                  f"{migliore['frase']}")
        vista = fasce[fasce["giorno"] <= 7][["data", "fascia", "voto", "livello",
                                             "colore", "fiducia", "segnali"]]
        print(vista.to_string(index=False))
