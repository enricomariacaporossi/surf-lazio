/* Surf Lazio: disegna la pagina da data/forecast.json.
   Tutti i calcoli li fa lo script su GitHub; qui si mostrano e basta. */

const DATI = "data/forecast.json";
const CHIAVE_CACHE = "surf-lazio-dati";
const CHIAVE_SPOT = "surf-lazio-spot";
const ORE_VECCHIE = 6; // oltre, l'aggiornamento automatico potrebbe essersi fermato

// link alle guide: incolla qui gli indirizzi quando le metti su Drive
const GUIDE = {
  scaduta: null,   // "Il vento che gira", sezioni 4 e 9
  vento: null,     // "Il mare e il vento", sezione 6
};

const FASCE = {
  "alba-10": { nome: "alba–10", da: 0, a: 10, frase: "dall'alba alle 10" },
  "10-13": { nome: "10–13", da: 10, a: 13, frase: "dalle 10 alle 13" },
  "13-16": { nome: "13–16", da: 13, a: 16, frase: "dalle 13 alle 16" },
  "16-tramonto": { nome: "16–tramonto", da: 16, a: 24, frase: "dalle 16 al tramonto" },
};
const CARDINALI = ["Nord", "Nord-Est", "Est", "Sud-Est", "Sud", "Sud-Ovest", "Ovest", "Nord-Ovest"];
const VENTO_A_PAROLE = {
  verde: "da terra, verde",
  giallo: "di lato, giallo",
  rosso: "dal mare, rosso",
  grigio: "tramontana, grigio",
};
const LIVELLO_BREVE = {
  "principianti": "principianti",
  "intermedi": "intermedi",
  "esperti": "esperti",
  "piatto": "piatto",
  "nessuno": "nessuno",
  "nessuno (troppo grosso)": "troppo grosso",
  "nessuno (temporale)": "temporale",
};
// nella griglia lo spazio e' poco: parole corte
const LIVELLO_CELLA = {
  "principianti": "princ.",
  "intermedi": "interm.",
  "esperti": "esperti",
  "piatto": "piatto",
  "nessuno": "vento",
  "nessuno (troppo grosso)": "grosso",
  "nessuno (temporale)": "temporale",
};
const MOTIVI_ZERO = ["piatto", "nessuno", "nessuno (troppo grosso)", "nessuno (temporale)"];

let stato = { dati: null, offline: false, spot: 0, aperta: null };

/* ------------------------------------------------------------- strumenti */

const $ = (sel) => document.querySelector(sel);

function cardinale(gradi) {
  return CARDINALI[Math.floor((((gradi % 360) + 360) % 360 + 22.5) / 45) % 8];
}

function numero(x, decimali = 1) {
  return Number(x).toLocaleString("it-IT", {
    minimumFractionDigits: decimali, maximumFractionDigits: decimali,
  });
}

function voto(x) {
  // 3 invece di 3,0; 3,5 resta 3,5
  return Number.isInteger(x) ? String(x) : numero(x);
}

function nodi(kmh) { return Math.round(kmh / 1.852); }

function comeData(testo) {
  // "2026-11-24" oppure "2026-11-24T07:00": ora italiana
  return new Date(testo.length === 10 ? testo + "T12:00" : testo);
}

function nomeGiorno(testo, lungo = true) {
  const d = comeData(testo);
  const oggi = new Date();
  const domani = new Date(Date.now() + 864e5);
  if (d.toDateString() === oggi.toDateString()) return "Oggi";
  if (d.toDateString() === domani.toDateString()) return "Domani";
  const f = new Intl.DateTimeFormat("it-IT", { weekday: lungo ? "long" : "short", day: "numeric" });
  const s = f.format(d);
  return s.charAt(0).toUpperCase() + s.slice(1);
}

function ora(testo) { return testo.slice(11, 16); }

function maiuscola(s) { return s.charAt(0).toUpperCase() + s.slice(1); }

function freccia(direzione) {
  // la punta indica dove va il vento, come nelle guide
  const verso = (direzione + 180) % 360;
  return `<svg class="freccia" viewBox="0 0 24 24" aria-hidden="true" style="transform:rotate(${verso}deg)"><path d="M12 2l6 10h-4v10h-4V12H6z"/></svg>`;
}

function ondeVoto(voto) {
  // cinque onde: piene, a meta' o vuote
  const cresta = "M2 16c4 0 5-9 11-9 4 0 6 4 4 6-2 1-4 0-4-2 2 6 8 6 13 5";
  let html = "";
  for (let i = 1; i <= 5; i++) {
    const riempi = voto >= i ? "currentColor" : voto >= i - 0.5 ? "url(#mezza)" : "none";
    html += `<svg viewBox="0 0 30 20" aria-hidden="true"><path d="${cresta}" fill="${riempi}" stroke="currentColor" stroke-width="1.6" stroke-linejoin="round"/></svg>`;
  }
  return html;
}

function oraDelGiorno(spot, data, hh) {
  return spot.ore.find((o) => o.ora === `${data}T${hh}`);
}

function fraseOra(o) {
  if (!o) return "";
  return `${maiuscola(o.parte)} ${numero(o.parte_m)} m, periodo ${numero(o.periodo_s, 0)} s, da ${cardinale(o.direzione_onda)}. ` +
    `Vento ${Math.round(o.vento_kmh)} km/h (${nodi(o.vento_kmh)} nodi) da ${cardinale(o.direzione_vento)}: ${VENTO_A_PAROLE[o.colore]}.`;
}

/* ------------------------------------------------------------- dati */

async function caricaDati() {
  try {
    const risposta = await fetch(`${DATI}?t=${Date.now()}`, { cache: "no-store" });
    if (!risposta.ok) throw new Error(`risposta ${risposta.status}`);
    const dati = await risposta.json();
    try { localStorage.setItem(CHIAVE_CACHE, JSON.stringify(dati)); } catch (e) { /* spazio pieno o privato */ }
    return { dati, offline: false };
  } catch (errore) {
    let copia = null;
    try { copia = JSON.parse(localStorage.getItem(CHIAVE_CACHE)); } catch (e) { /* niente copia */ }
    if (copia) return { dati: copia, offline: true };
    throw errore;
  }
}

/* ------------------------------------------------------------- disegno */

function disegnaScelta() {
  const nav = $("#scelta-spot");
  nav.innerHTML = stato.dati.spot.map((s, i) => {
    const corto = s.nome.split("–").pop().trim();
    return `<button type="button" data-spot="${i}" aria-pressed="${i === stato.spot}">${corto}</button>`;
  }).join("");
  nav.querySelectorAll("button").forEach((b) => b.addEventListener("click", () => {
    stato.spot = Number(b.dataset.spot);
    stato.aperta = null;
    try { localStorage.setItem(CHIAVE_SPOT, stato.spot); } catch (e) { /* non importa */ }
    disegna();
  }));
}

function disegnaRisposta(spot) {
  const m = spot.finestra_migliore;
  const luogo = spot.nome.split("–")[0].trim();
  if (!m) {
    return `<section class="risposta">
      <h2>Niente da fare nei prossimi 5 giorni a ${luogo}.</h2>
      <p class="perche">Il mare resta piatto, troppo grosso o con il vento contro. Ricontrolla domani: le previsioni cambiano.</p>
      ${spot.avviso ? `<ul class="segnali"><li class="attenzione">${spot.avviso}</li></ul>` : ""}
    </section>`;
  }
  const fascia = FASCE[m.fascia];
  const o = oraDelGiorno(spot, m.data, m.ora);
  const segnali = (m.segnali || "").split("; ").filter(Boolean);
  const avviso = spot.avviso ? `<li class="attenzione">${spot.avviso}</li>` : "";
  const perche = (testo) => testo.startsWith("scaduta") && GUIDE.scaduta
    ? ` <a href="${GUIDE.scaduta}">Perché?</a>` : "";
  return `<section class="risposta">
    <h2>${nomeGiorno(m.data)}, ${fascia.frase}.</h2>
    <div class="onde-voto" aria-label="Voto ${numero(m.voto)} su 5">${ondeVoto(m.voto)}
      <span class="numero">${voto(m.voto)} su 5, ${LIVELLO_BREVE[m.livello] || m.livello}</span></div>
    <p class="perche">${fraseOra(o)} Onda totale ${numero(m.onda_m)} m. ${m.fiducia === "tendenza" ? "È una tendenza: ricontrolla nei prossimi giorni." : ""}</p>
    ${segnali.length || avviso ? `<ul class="segnali">${avviso}${segnali.map((s) =>
      `<li class="${s.startsWith("scaduta") ? "scaduta" : ""}">${maiuscola(s)}.${perche(s)}</li>`).join("")}</ul>` : ""}
  </section>`;
}

function disegnaAdesso(spot) {
  const a = spot.adesso;
  const webcam = (spot.webcam || []).map((w) =>
    `<li><a href="${w.url}" target="_blank" rel="noopener">${w.nome}</a></li>`).join("");
  const vento = a ? `Vento previsto adesso: ${Math.round(a.vento_kmh)} km/h (${nodi(a.vento_kmh)} nodi) da ${cardinale(a.direzione_vento)}, ${VENTO_A_PAROLE[a.colore]}. Onda ${numero(a.onda_m)} m.` : "";
  return `<section class="adesso">
    <h3>Prima di uscire</h3>
    <p>${vento}</p>
    ${webcam ? `<p class="titoletto">Webcam vicine:</p><ul class="webcam">${webcam}</ul>` : ""}
    <p class="mare-dal-vivo">Il modello non è la riva: guarda il mare per 10 minuti prima di entrare e non entrare da solo. Emergenza: 112.</p>
  </section>`;
}

function disegnaGriglia(spot) {
  const intestazione = Object.values(FASCE).map((f) => `<th scope="col">${f.nome}</th>`).join("");
  const righe = spot.giorni.map((g) => {
    const celle = Object.keys(FASCE).map((chiave) => {
      const f = g.fasce.find((x) => x.fascia === chiave);
      if (!f) return "<td></td>";
      const id = `${g.data}|${chiave}`;
      const marche = [];
      if (f.segnali.some((s) => s.startsWith("scaduta"))) marche.push("S");
      if (f.segnali.some((s) => s.startsWith("incerto"))) marche.push("?");
      const livello = LIVELLO_BREVE[f.livello] || f.livello;
      const sotto = f.voto > 0 || MOTIVI_ZERO.includes(f.livello) ? (LIVELLO_CELLA[f.livello] || "") : "";
      const etichetta = `${nomeGiorno(g.data)} ${FASCE[chiave].frase}: voto ${numero(f.voto)}, ${livello}, vento ${f.colore}`;
      return `<td><button type="button" class="cella v${Math.floor(f.voto)} vento-${f.colore}${marche.includes("?") ? " incerto" : ""}"
        data-cella="${id}" aria-expanded="${stato.aperta === id}" aria-label="${etichetta}">
        <span class="voto">${voto(f.voto)}</span><span class="livello">${sotto}</span>
        ${marche.length ? `<span class="marca" aria-hidden="true">${marche.join(" ")}</span>` : ""}
      </button></td>`;
    }).join("");
    const nota = g.fiducia === "tendenza" ? "<small>tendenza</small>" : "";
    const riga = `<tr class="${g.fiducia}"><th scope="row" class="giorno">${nomeGiorno(g.data, false)}${nota}</th>${celle}</tr>`;
    const aperta = stato.aperta && stato.aperta.startsWith(g.data + "|")
      ? `<tr><td colspan="5">${disegnaDettaglio(spot, g, stato.aperta.split("|")[1])}</td></tr>` : "";
    return riga + aperta;
  }).join("");
  return `<section class="settimana">
    <h3>I prossimi giorni</h3>
    <table class="griglia">
      <thead><tr><th class="giorno"></th>${intestazione}</tr></thead>
      <tbody>${righe}</tbody>
    </table>
  </section>`;
}

function disegnaDettaglio(spot, giorno, chiave) {
  const f = FASCE[chiave];
  const ore = spot.ore.filter((o) => o.ora.startsWith(giorno.data) &&
    Number(ora(o.ora).slice(0, 2)) >= f.da && Number(ora(o.ora).slice(0, 2)) < f.a);
  const fascia = giorno.fasce.find((x) => x.fascia === chiave);
  const segnali = fascia ? fascia.segnali : [];
  const righe = ore.map((o) => `<tr>
      <td>${ora(o.ora)}</td>
      <td>${numero(o.onda_m)} m<br><small>${o.parte}, ${numero(o.periodo_s, 0)} s</small></td>
      <td>${freccia(o.direzione_onda)} ${cardinale(o.direzione_onda)}</td>
      <td class="vento-${o.colore}"><span class="pallino"></span>${freccia(o.direzione_vento)} ${Math.round(o.vento_kmh)} <small>(${nodi(o.vento_kmh)} kn)</small><br><small>da ${cardinale(o.direzione_vento)}, raffiche ${Math.round(o.raffiche_kmh)}</small></td>
      <td class="voto-ora">${voto(o.voto)}</td>
    </tr>`).join("");
  return `<div class="dettaglio">
    <h4>${nomeGiorno(giorno.data)}, ${f.frase}</h4>
    ${segnali.length ? `<ul class="segnali">${segnali.map((s) => `<li>${maiuscola(s)}.</li>`).join("")}</ul>` : ""}
    <table class="ore">
      <thead><tr><th>Ora</th><th>Onda</th><th>Da</th><th>Vento km/h</th><th>Voto</th></tr></thead>
      <tbody>${righe}</tbody>
    </table>
  </div>`;
}

function disegnaLegenda() {
  const guida = GUIDE.vento ? ` <a href="${GUIDE.vento}">Perché?</a>` : "";
  return `<section class="legenda">
    <p>La bandierina a sinistra di ogni casella è il colore del vento, come nelle guide.${guida}</p>
    <ul>
      <li><span class="pallino vento-verde"></span>Verde: da Est e Nord-Est, viene da terra.</li>
      <li><span class="pallino vento-giallo"></span>Giallo: da Sud-Est e Nord-Ovest, di lato.</li>
      <li><span class="pallino vento-rosso"></span>Rosso: da Sud, Sud-Ovest e Ovest, viene dal mare.</li>
      <li><span class="pallino vento-grigio"></span>Grigio: da Nord, la tramontana spiana il mare.</li>
    </ul>
    <p>Più il blu è scuro, più il voto è alto.</p>
    <div class="scala" aria-hidden="true">0 <span style="background:var(--v0)"></span><span style="background:var(--v1)"></span><span style="background:var(--v2)"></span><span style="background:var(--v3)"></span><span style="background:var(--v4)"></span><span style="background:var(--v5)"></span> 5</div>
    <p>S indica la scaduta, ? che i modelli non sono d'accordo. I giorni più chiari sono una tendenza.</p>
  </section>`;
}

function disegnaPiede() {
  const d = stato.dati;
  const spot = d.spot[stato.spot];
  const aggiornato = comeData(d.aggiornato);
  const ore = (Date.now() - aggiornato.getTime()) / 36e5;
  const quando = new Intl.DateTimeFormat("it-IT", { weekday: "long", hour: "2-digit", minute: "2-digit" }).format(aggiornato);
  const avvisi = [];
  if (stato.offline) avvisi.push("Senza rete: stai vedendo l'ultima previsione salvata.");
  if (ore > ORE_VECCHIE) avvisi.push(`Questi dati hanno più di ${ORE_VECCHIE} ore: l'aggiornamento automatico potrebbe essersi fermato.`);
  $("#piede").innerHTML = `
    ${avvisi.map((a) => `<p class="avviso-dati">${a}</p>`).join("")}
    <p>Previsione aggiornata ${quando}. Si aggiorna da sola ogni 3 ore.</p>
    <p><a class="scarica" href="data/settimana_${spot.id}.csv" download>Scarica la settimana di ${spot.nome.split("–")[0].trim()} (CSV)</a></p>
    ${spot.confronto ? `<p>Per un confronto: <a href="${spot.confronto}" target="_blank" rel="noopener">Surfnerd</a>.</p>` : ""}
    ${d.crediti.map((c) => `<p>${c}</p>`).join("")}`;
}

function disegna() {
  const spot = stato.dati.spot[stato.spot];
  disegnaScelta();
  $("#contenuto").innerHTML = disegnaRisposta(spot) + disegnaGriglia(spot) + disegnaAdesso(spot) + disegnaLegenda();
  document.querySelectorAll(".cella").forEach((c) => c.addEventListener("click", () => {
    stato.aperta = stato.aperta === c.dataset.cella ? null : c.dataset.cella;
    disegna();
    const di_nuovo = document.querySelector(`[data-cella="${c.dataset.cella}"]`);
    if (di_nuovo) di_nuovo.focus();
  }));
  disegnaPiede();
}

/* ------------------------------------------------------------- avvio */

(async function avvio() {
  try {
    const { dati, offline } = await caricaDati();
    stato.dati = dati;
    stato.offline = offline;
    let salvato = 0;
    try { salvato = Number(localStorage.getItem(CHIAVE_SPOT)) || 0; } catch (e) { /* niente */ }
    stato.spot = Math.min(salvato, dati.spot.length - 1);
    disegna();
  } catch (errore) {
    $("#contenuto").innerHTML = `<p class="errore">Non riesco a scaricare le previsioni (${errore.message}).
      Controlla la connessione e ricarica la pagina.</p>`;
  }
})();
