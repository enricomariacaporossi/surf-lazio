"""Avvisi su Telegram e pulsanti «meglio / come previsto / peggio» (Fasi 6 e 7).

Lo lancia aggiorna.py alla fine di ogni giro. Serve due Secrets su GitHub:
- TELEGRAM_TOKEN    il token del bot, dato da @BotFather;
- TELEGRAM_CHAT_ID  il numero della tua chat con il bot; per mandare gli
                    stessi messaggi anche a un istruttore, i due numeri separati
                    da una virgola, senza spazi: il tuo per primo.
Se mancano non fa niente. Token e numeri non vanno mai scritti in un file o in
un messaggio: il repository e i registri del workflow sono pubblici.
Chi scrive /start al bot riceve il proprio numero, da dare al proprietario.

A ogni giro:
1. legge le risposte ai pulsanti arrivate dal giro prima e le salva in
   data/telegram/riscontri.csv (servono alla verifica della Fase 6);
2. se una fascia di oggi o domani arriva a 3,5 o c'e' una scaduta, manda un
   avviso, una volta sola (di nuovo solo se il voto sale di mezzo punto);
3. la mattina, se oggi c'e' qualcosa da surfare, manda il riepilogo del
   giorno con i pulsanti per dire, dopo, com'era davvero.
Di notte (dalle 22 alle 7) non scrive: gli avvisi aspettano il mattino.
"""
import csv
import json
import os
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import requests

from comune import RADICE

DATI = RADICE / "data"
CARTELLA = DATI / "telegram"
STATO = CARTELLA / "stato.json"
RISCONTRI = CARTELLA / "riscontri.csv"
SITO = "https://enricomariacaporossi.github.io/surf-lazio/"
FUSO = ZoneInfo("Europe/Rome")

SOGLIA_AVVISO = 3.5      # come nel progetto: «una fascia supera 3,5»
SOGLIA_MATTINO = 2.0     # sotto, il riepilogo del mattino non parte
ORE_SVEGLIO = range(7, 22)
ESITI = {"meglio": "meglio", "come": "come previsto", "peggio": "peggio"}
FASCE = {"alba-10": "dall'alba alle 10", "10-13": "dalle 10 alle 13",
         "13-16": "dalle 13 alle 16", "16-tramonto": "dalle 16 al tramonto"}
LIVELLI = {"principianti": "principianti", "intermedi": "intermedi", "esperti": "esperti"}


def numero(x):
    return f"{x:.1f}".replace(".", ",").replace(",0", "")


class Bot:
    def __init__(self, token, chat_ids):
        self.url = f"https://api.telegram.org/bot{token}/"
        # il primo numero e' il tuo; gli altri (l'istruttore) ricevono gli stessi messaggi
        self.chat_ids = [c.strip() for c in str(chat_ids).split(",") if c.strip()]

    def chiama(self, metodo, **parametri):
        risposta = requests.post(self.url + metodo, json=parametri, timeout=(10, 30))
        dati = risposta.json()
        if not dati.get("ok"):
            # niente token nel messaggio d'errore: si vede solo il metodo
            raise RuntimeError(f"Telegram {metodo}: {dati.get('description', risposta.status_code)}")
        return dati["result"]

    def chi(self, chat_id):
        """1 = il primo numero (tu), 2 = il secondo...; None = sconosciuto."""
        chat_id = str(chat_id)
        return self.chat_ids.index(chat_id) + 1 if chat_id in self.chat_ids else None

    def scrivi(self, testo, pulsanti=None, a=None):
        """Manda il messaggio a una chat (a) o a tutte; un errore su una non ferma le altre."""
        destinatari = [str(a)] if a is not None else self.chat_ids
        mandati = 0
        for chat_id in destinatari:
            parametri = {"chat_id": chat_id, "text": testo,
                         "link_preview_options": {"is_disabled": True}}
            if pulsanti:
                parametri["reply_markup"] = {"inline_keyboard": pulsanti}
            try:
                self.chiama("sendMessage", **parametri)
                mandati += 1
            except (RuntimeError, requests.RequestException) as errore:
                n = self.chi(chat_id)
                print(f"Telegram: messaggio alla chat n. {n or '?'} non riuscito ({errore}).")
        return mandati


def carica_stato():
    try:
        return json.loads(STATO.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return {"offset": 0, "avvisi": {}, "mattino": {}}


def salva_stato(stato):
    CARTELLA.mkdir(parents=True, exist_ok=True)
    # si tengono solo gli ultimi giorni
    limite = (date.today() - timedelta(days=3)).isoformat()
    stato["avvisi"] = {k: v for k, v in stato["avvisi"].items() if k.split("|")[1] >= limite}
    stato["mattino"] = {k: v for k, v in stato["mattino"].items() if k >= limite}
    STATO.write_text(json.dumps(stato, ensure_ascii=False, indent=1), encoding="utf-8")


def nome_breve(spot):
    return spot["nome"].split("–")[-1].strip()


GIORNI = ["lunedì", "martedì", "mercoledì", "giovedì", "venerdì", "sabato", "domenica"]


def nome_giorno(testo, oggi):
    giorno = date.fromisoformat(testo)
    if giorno == oggi:
        return "oggi"
    if giorno == oggi + timedelta(days=1):
        return "domani"
    return f"{GIORNI[giorno.weekday()]} {giorno.day}"


# --------------------------------------------------------- 1. le risposte

def leggi_risposte(bot, stato, nomi):
    """Salva le risposte ai pulsanti delle chat in elenco; le altre le ignora."""
    aggiornamenti = bot.chiama("getUpdates", offset=stato["offset"], timeout=0,
                               allowed_updates=["callback_query", "message"])
    nuove, estranei = [], 0
    for u in aggiornamenti:
        stato["offset"] = u["update_id"] + 1
        domanda = u.get("callback_query")
        messaggio = u.get("message")
        chat_id = ((domanda or {}).get("message") or messaggio or {}).get("chat", {}).get("id")
        chi = bot.chi(chat_id)

        if messaggio and messaggio.get("text", "").startswith("/start"):
            if chi:
                bot.scrivi("Ciao! Ti scrivo quando una fascia di oggi o domani arriva a "
                           f"{numero(SOGLIA_AVVISO)} o quando c'è una scaduta. La mattina, se c'è "
                           "qualcosa da surfare, ti mando il riepilogo con tre pulsanti: "
                           "dopo l'uscita dimmi se era meglio, come previsto o peggio.\n" + SITO,
                           a=chat_id)
            else:
                # il numero lo vede solo chi l'ha chiesto, mai nel registro pubblico
                bot.scrivi(f"Ciao! Questo bot manda le previsioni di Surf Lazio solo a chi è in "
                           f"elenco. Il tuo numero è {chat_id}: dallo a chi ha creato il bot "
                           "se vuoi ricevere gli avvisi.", a=chat_id)
            continue
        if chat_id is not None and not chi:
            estranei += 1
            continue
        if not domanda:
            continue
        parti = domanda.get("data", "").split("|")
        if len(parti) != 4 or parti[0] != "v" or parti[3] not in ESITI:
            continue
        _, spot_id, giorno, esito = parti
        previsto = stato["mattino"].get(giorno, {}).get(spot_id, {})
        nuove.append({
            "risposto": datetime.now(FUSO).strftime("%Y-%m-%d %H:%M"),
            "chi": chi,  # 1 = tu, 2 = l'istruttore (l'ordine dei numeri nel Secret)
            "giorno": giorno, "spot": spot_id,
            "fascia": previsto.get("fascia", ""), "voto_previsto": previsto.get("voto", ""),
            "esito": ESITI[esito],
        })
        try:  # se e' passato troppo tempo Telegram rifiuta: non importa
            bot.chiama("answerCallbackQuery", callback_query_id=domanda["id"], text="Segnato, grazie")
        except (RuntimeError, requests.RequestException):
            pass
        bot.scrivi(f"Segnato: {nomi.get(spot_id, spot_id)} {nome_giorno(giorno, date.today())}, "
                   f"{ESITI[esito]}. Grazie, serve a capire se il voto è giusto.", a=chat_id)

    if estranei:
        # nessun numero nel registro (e' pubblico): solo il conteggio
        print(f"Telegram: {estranei} messaggi da chat che non sono in TELEGRAM_CHAT_ID, ignorati.")
    if nuove:
        CARTELLA.mkdir(parents=True, exist_ok=True)
        nuovo_file = not RISCONTRI.exists()
        with open(RISCONTRI, "a", newline="", encoding="utf-8") as f:
            scrittore = csv.DictWriter(f, fieldnames=list(nuove[0]))
            if nuovo_file:
                scrittore.writeheader()
            scrittore.writerows(nuove)
    return nuove


# --------------------------------------------------------- 2. gli avvisi

def cerca_avvisi(forecast, stato, oggi):
    """Le fasce di oggi e domani da segnalare, nuove o migliorate."""
    trovate = []
    for spot in forecast["spot"]:
        for g in spot["giorni"]:
            if g["giorno"] > 2:
                continue
            for f in g["fasce"]:
                scaduta = any(s.startswith("scaduta:") for s in f["segnali"])
                if not (f["voto"] >= SOGLIA_AVVISO or (scaduta and f["voto"] > 0)):
                    continue
                if g["giorno"] == 1 and f["fascia"] in FASCE and _fascia_passata(f, g, oggi):
                    continue
                chiave = f"{spot['id']}|{g['data']}|{f['fascia']}"
                prima = stato["avvisi"].get(chiave)
                if prima is None or f["voto"] >= prima + 0.5:
                    trovate.append((chiave, spot, g, f, scaduta))
    return trovate


def _fascia_passata(f, g, oggi):
    """Una fascia di oggi che e' gia' finita non si segnala."""
    fine = {"alba-10": 10, "10-13": 13, "13-16": 16, "16-tramonto": 17}[f["fascia"]]
    return datetime.now(FUSO).hour >= fine


def testo_avvisi(trovate, oggi):
    righe = ["Surf Lazio: c'è da andare."]
    for _, spot, g, f, scaduta in trovate:
        livello = LIVELLI.get(f["livello"], f["livello"])
        riga = (f"\n{nome_breve(spot)}, {nome_giorno(g['data'], oggi)} {FASCE[f['fascia']]}: "
                f"{numero(f['voto'])} su 5, {livello}.")
        if scaduta:
            riga += " Scaduta: il meglio dall'alba alle 10, poi l'onda cala."
        riga += f"\n{f['frase']}."
        if any(s.startswith("incerto") for s in f["segnali"]):
            riga += " I modelli non sono d'accordo: ricontrolla."
        righe.append(riga)
    righe.append("\nPrima di entrare guarda il mare dal vivo.\n" + SITO)
    return "\n".join(righe)


# --------------------------------------------------------- 3. il mattino

def riepilogo_mattino(forecast, oggi):
    """Un messaggio per spot con la fascia migliore di oggi, se vale la pena,
    e i tre pulsanti per dire dopo com'era."""
    messaggi, ricordo = [], {}
    for spot in forecast["spot"]:
        g = next((g for g in spot["giorni"] if g["giorno"] == 1), None)
        if not g or not g["fasce"]:
            continue
        f = max(g["fasce"], key=lambda x: x["voto"])
        if f["voto"] < SOGLIA_MATTINO:
            continue
        testo = (f"{nome_breve(spot)}, oggi {FASCE[f['fascia']]}: {numero(f['voto'])} su 5, "
                 f"{LIVELLI.get(f['livello'], f['livello'])}.\n{f['frase']}.\n\n"
                 "Se vai, dopo dimmi com'era rispetto alla previsione.")
        pulsanti = [[{"text": etichetta, "callback_data": f"v|{spot['id']}|{oggi.isoformat()}|{codice}"}
                     for codice, etichetta in ESITI.items()]]
        messaggi.append((testo, pulsanti))
        ricordo[spot["id"]] = {"fascia": f["fascia"], "voto": f["voto"]}
    return messaggi, ricordo


# --------------------------------------------------------- tutto insieme

def main():
    token = os.environ.get("TELEGRAM_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        print("Telegram: TELEGRAM_TOKEN o TELEGRAM_CHAT_ID mancanti, salto.")
        return
    bot = Bot(token, chat_id)
    forecast = json.loads((DATI / "forecast.json").read_text(encoding="utf-8"))
    stato = carica_stato()
    adesso = datetime.now(FUSO)
    oggi = adesso.date()

    nomi = {spot["id"]: nome_breve(spot) for spot in forecast["spot"]}
    try:
        risposte = leggi_risposte(bot, stato, nomi)
        print(f"Telegram: {len(risposte)} risposte nuove.")
        # la prima volta, per ogni numero nuovo, un messaggio di prova: se il numero e'
        # sbagliato Telegram risponde «chat not found» e si vede nel registro del workflow
        gia = stato.pop("collegato", False) and 1 or stato.get("collegati", 0)
        for chat_id in bot.chat_ids[gia:]:
            if bot.scrivi("Surf Lazio è collegato. Da qui arriveranno gli avvisi e, le mattine in "
                          "cui c'è da surfare, il riepilogo con i pulsanti.\n" + SITO, a=chat_id):
                print(f"Telegram: messaggio di prova alla chat n. {bot.chi(chat_id)}.")
        stato["collegati"] = len(bot.chat_ids)
        if adesso.hour in ORE_SVEGLIO:
            trovate = cerca_avvisi(forecast, stato, oggi)
            if trovate:
                bot.scrivi(testo_avvisi(trovate, oggi))
                for chiave, _, _, f, _ in trovate:
                    stato["avvisi"][chiave] = f["voto"]
                print(f"Telegram: avviso per {len(trovate)} fasce.")
            if oggi.isoformat() not in stato["mattino"]:
                messaggi, ricordo = riepilogo_mattino(forecast, oggi)
                for testo, pulsanti in messaggi:
                    bot.scrivi(testo, pulsanti)
                print(f"Telegram: {len(messaggi)} messaggi del mattino.")
                stato["mattino"][oggi.isoformat()] = ricordo
    finally:
        salva_stato(stato)


if __name__ == "__main__":
    main()
