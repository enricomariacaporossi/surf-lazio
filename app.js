/* Surf Lazio: disegna la pagina da data/forecast.json.
   Tutti i calcoli li fa lo script su GitHub; qui si mostrano e basta. */

const DATI = "data/forecast.json";
const VERIFICA = "data/verifica.json";
const SCHEDE = "spots.json";
const CHIAVE_CACHE = "surf-lazio-dati";
const CHIAVE_SPOT = "surf-lazio-spot";
const ORE_VECCHIE = 6; // oltre, l'aggiornamento automatico potrebbe essersi fermato

// le due guide su Drive (solo il link: i PDF non stanno nel repository)
const GUIDE = {
  // «Il vento che gira»: il fronte in sette tappe e la scaduta
  scaduta: "https://drive.google.com/file/d/1MxhQhE-90VRALpSBZWDvUOhlcXNARecj/view",
  // «Il mare e il vento»: i colori del vento e «più modelli, più fiducia»
  vento: "https://drive.google.com/file/d/1yXNYr8wQukbfKD-qW1NKsIPhkxSM0euj/view",
};
const perche = (url) => url ? ` <a href="${url}" target="_blank" rel="noopener">Perché?</a>` : "";

// le sette tappe del passaggio di un fronte, come nella seconda guida
const TAPPE = ["", "prima", "avvicinamento", "pre-frontale", "fronte", "dopo il fronte", "scaduta", "bel tempo"];

// il tempo da codice meteo (WMO) e pioggia: una parola e un'icona
function cielo(codice, pioggia = 0) {
  const c = Number(codice) || 0;
  if (c >= 95) return "temporale";
  if ((c >= 71 && c <= 77) || c === 85 || c === 86) return "neve";
  if ((c >= 51 && c <= 67) || (c >= 80 && c <= 82) || pioggia >= 0.3) return "pioggia";
  if (c === 45 || c === 48) return "nebbia";
  if (c === 3) return "coperto";
  if (c === 1 || c === 2) return "variabile";
  return "sereno";
}
const NUVOLA = "M4.5 12.5h7a2.5 2.5 0 0 0 .2-5 3.6 3.6 0 0 0-6.9-.6A2.8 2.8 0 0 0 4.5 12.5z";
const ICONE = {
  sereno: `<circle cx="8" cy="8" r="3"/><path d="M8 1.5v1.8M8 12.7v1.8M1.5 8h1.8M12.7 8h1.8M3.4 3.4l1.3 1.3M11.3 11.3l1.3 1.3M3.4 12.6l1.3-1.3M11.3 4.7l1.3-1.3"/>`,
  variabile: `<circle cx="5.5" cy="5.5" r="2.3"/><path d="M5.5 1v1M1 5.5h1M2.3 2.3l.7.7M8.7 2.3l-.7.7"/><path d="M6 13.5h6a2.2 2.2 0 0 0 .2-4.4 3 3 0 0 0-5.8-.4A2.4 2.4 0 0 0 6 13.5z" fill="var(--sale)"/>`,
  coperto: `<path d="${NUVOLA}"/>`,
  nebbia: `<path d="M2.5 6h11M2 9h12M3.5 12h9"/>`,
  pioggia: `<path d="M4.5 9.5h7a2.5 2.5 0 0 0 .2-5 3.6 3.6 0 0 0-6.9-.6A2.8 2.8 0 0 0 4.5 9.5z"/><path d="M5.5 11.5l-.8 2M8.5 11.5l-.8 2M11.3 11.5l-.8 2" class="gocce"/>`,
  temporale: `<path d="M4.5 9.5h7a2.5 2.5 0 0 0 .2-5 3.6 3.6 0 0 0-6.9-.6A2.8 2.8 0 0 0 4.5 9.5z"/><path d="M8.6 9.5l-1.8 2.7h2.2l-1.6 2.6" class="fulmine"/>`,
  neve: `<path d="M4.5 9.5h7a2.5 2.5 0 0 0 .2-5 3.6 3.6 0 0 0-6.9-.6A2.8 2.8 0 0 0 4.5 9.5z"/><path d="M5.5 12.5h.01M8 13.5h.01M10.5 12.5h.01" stroke-width="2.2"/>`,
};
function icona(tipo, lato = 16) {
  return `<svg class="icona-meteo icona-${tipo}" width="${lato}" height="${lato}" viewBox="0 0 16 16" aria-hidden="true">${ICONE[tipo] || ""}</svg>`;
}
function iconaSvg(tipo, x, y, lato = 13) {
  // la stessa icona dentro il grafico
  return `<svg x="${x - lato / 2}" y="${y}" width="${lato}" height="${lato}" viewBox="0 0 16 16" class="icona-meteo icona-${tipo}">${ICONE[tipo] || ""}</svg>`;
}

// indice UV: le categorie dell'Organizzazione mondiale della sanità
const UV = [
  { fino: 2, nome: "basso", colore: "var(--uv1)" },
  { fino: 5, nome: "moderato", colore: "var(--uv2)" },
  { fino: 7, nome: "alto", colore: "var(--uv3)" },
  { fino: 10, nome: "molto alto", colore: "var(--uv4)" },
  { fino: 99, nome: "estremo", colore: "var(--uv5)" },
];
const categoriaUV = (x) => UV.find((c) => Math.round(x) <= c.fino);

// muta consigliata secondo la temperatura dell'acqua (indicativa)
function muta(gradi) {
  if (gradi >= 23) return "basta il costume o la lycra";
  if (gradi >= 20) return "muta corta o 2 mm";
  if (gradi >= 17) return "muta 3/2";
  if (gradi >= 14) return "muta 4/3";
  if (gradi >= 12) return "muta 5/4 e calzari";
  return "muta 5/4 o 6/5, calzari, guanti e cappuccio";
}

const FASCE = {
  "alba-10": { nome: "alba–10", da: 0, a: 10, frase: "dall'alba alle 10" },
  "10-13": { nome: "10–13", da: 10, a: 13, frase: "dalle 10 alle 13" },
  "13-16": { nome: "13–16", da: 13, a: 16, frase: "dalle 13 alle 16" },
  "16-tramonto": { nome: "16–tramonto", da: 16, a: 24, frase: "dalle 16 al tramonto" },
};
const CARDINALI = ["Nord", "Nord-Est", "Est", "Sud-Est", "Sud", "Sud-Ovest", "Ovest", "Nord-Ovest"];
const CARDINALI_BREVI = ["N", "NE", "E", "SE", "S", "SO", "O", "NO"];
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

let stato = { dati: null, offline: false, spot: 0, aperta: null, verifica: null, chiudiGrafico: null };

/* ------------------------------------------------------------- strumenti */

const $ = (sel) => document.querySelector(sel);

function cardinale(gradi, breve = false) {
  const i = Math.floor((((gradi % 360) + 360) % 360 + 22.5) / 45) % 8;
  return (breve ? CARDINALI_BREVI : CARDINALI)[i];
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
    await unisciSchede(dati);
    try { localStorage.setItem(CHIAVE_CACHE, JSON.stringify(dati)); } catch (e) { /* spazio pieno o privato */ }
    return { dati, offline: false };
  } catch (errore) {
    let copia = null;
    try { copia = JSON.parse(localStorage.getItem(CHIAVE_CACHE)); } catch (e) { /* niente copia */ }
    if (copia) return { dati: copia, offline: true };
    throw errore;
  }
}

async function unisciSchede(dati) {
  // webcam, confronti e scheda dello spot si leggono da spots.json:
  // cambiano subito quando si modifica il file, senza aspettare il prossimo aggiornamento
  try {
    const risposta = await fetch(`${SCHEDE}?t=${Date.now()}`, { cache: "no-store" });
    if (!risposta.ok) return;
    const schede = await risposta.json();
    dati.spot.forEach((s) => {
      const scheda = schede.find((x) => x.id === s.id);
      if (!scheda) return;
      ["webcam", "confronto", "scheda", "avviso", "altezzaVoto"].forEach((k) => { if (k in scheda) s[k] = scheda[k]; });
    });
  } catch (e) { /* si usano i dati di forecast.json */ }
}

function testoDaCondividere(spot, data, chiave) {
  const g = spot.giorni.find((x) => x.data === data);
  const f = g && g.fasce.find((x) => x.fascia === chiave);
  if (!f) return null;
  const o = oraDelGiorno(spot, data, f.ora);
  const [paese, posto] = spot.nome.split(" – ");
  const luogo = posto ? `${paese} (${posto})` : paese;
  const livello = LIVELLO_BREVE[f.livello] || f.livello;
  const extra = [];
  if (f.segnali.some((x) => x.startsWith("scaduta:"))) extra.push("Scaduta: il meglio dall'alba alle 10, poi l'onda cala.");
  if (g.fiducia === "tendenza") extra.push("È una tendenza: può cambiare.");
  const quando = new Intl.DateTimeFormat("it-IT", { weekday: "long", hour: "2-digit", minute: "2-digit" })
    .format(comeData(stato.dati.aggiornato));
  const link = `${location.origin}${location.pathname}#${spot.id}/${data}/${chiave}`;
  const testo = [`${luogo}, ${nomeGiorno(data).toLowerCase()} ${FASCE[chiave].frase}: ${voto(f.voto)} su 5, ${livello}.`,
    fraseOra(o), ...extra, `Previsione di ${quando}.`].filter(Boolean).join(" ");
  return { testo, link };
}

async function condividi(bottone) {
  const [data, chiave] = bottone.dataset.condividi.split("|");
  const c = testoDaCondividere(stato.dati.spot[stato.spot], data, chiave);
  if (!c) return;
  const conferma = (scritta) => {
    const prima = bottone.textContent;
    bottone.textContent = scritta;
    setTimeout(() => { bottone.textContent = prima; }, 2000);
  };
  if (navigator.share) {
    try { await navigator.share({ text: c.testo, url: c.link }); } catch (e) { /* annullato */ }
    return;
  }
  try {
    await navigator.clipboard.writeText(`${c.testo}\n${c.link}`);
    conferma("Copiato");
  } catch (e) {
    conferma("Non riesco a copiare");
  }
}

// un link come #santa-severa/2026-11-24/alba-10 apre quello spot e quella fascia
function leggiIndirizzo() {
  const [id, data, chiave] = decodeURIComponent(location.hash.slice(1)).split("/");
  const i = stato.dati.spot.findIndex((s) => s.id === id);
  if (i < 0) return false;
  stato.spot = i;
  const g = stato.dati.spot[i].giorni.find((x) => x.data === data);
  stato.aperta = g && g.fasce.some((x) => x.fascia === chiave) ? `${data}|${chiave}` : null;
  return Boolean(stato.aperta);
}

function idMigliore(spot) {
  const m = spot.finestra_migliore;
  return m ? `${m.data}|${m.fascia}` : null;
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
  // detto una volta sola, qui, e solo se la finestra migliore cade nei 2 giorni dopo una mareggiata
  const fondale = m.dopo_mareggiata ? "<li>Dopo la mareggiata il fondale può essere cambiato: i picchi vanno ritrovati.</li>" : "";
  const avviso = (spot.avviso ? `<li class="attenzione">${spot.avviso}</li>` : "") + fondale;
  const link = (testo) => testo.startsWith("scaduta") ? perche(GUIDE.scaduta)
    : testo.startsWith("incerto") ? perche(GUIDE.vento) : "";
  return `<section class="risposta">
    <h2>${nomeGiorno(m.data)}, ${fascia.frase}.</h2>
    <div class="onde-voto" aria-label="Voto ${numero(m.voto)} su 5">${ondeVoto(m.voto)}
      <span class="numero">${voto(m.voto)} su 5, ${LIVELLO_BREVE[m.livello] || m.livello}</span></div>
    <p class="perche">${fraseOra(o)} Onda totale ${numero(m.onda_m)} m. ${m.fiducia === "tendenza" ? "È una tendenza: ricontrolla nei prossimi giorni." : ""}</p>
    <div class="azioni">
      <button type="button" class="vedi" data-vai="${m.data}|${m.fascia}">Vedi ora per ora</button>
      <button type="button" class="condividi" data-condividi="${m.data}|${m.fascia}">Condividi</button>
    </div>
    ${segnali.length || avviso ? `<ul class="segnali">${avviso}${segnali.map((s) =>
      `<li class="${s.startsWith("scaduta") ? "scaduta" : ""}">${maiuscola(s)}.${link(s)}</li>`).join("")}</ul>` : ""}
  </section>`;
}

// i valori dell'ora in cui apri la pagina (non di quando e' girato l'aggiornamento)
function oraAttuale(spot) {
  const d = new Date();
  const due = (n) => String(n).padStart(2, "0");
  const chiave = `${d.getFullYear()}-${due(d.getMonth() + 1)}-${due(d.getDate())}T${due(d.getHours())}:00`;
  const p = (spot.serie || []).find((x) => x.ora === chiave);
  return p ? { ...spot.adesso, ...p } : spot.adesso;
}

function disegnaAdesso(spot) {
  const a = oraAttuale(spot);
  const webcam = (spot.webcam || []).map((w) =>
    `<li><a href="${w.url}" target="_blank" rel="noopener">${w.nome}</a></li>`).join("");
  const righe = [];
  if (a) {
    righe.push(["Vento", `<span class="pallino" style="background:${COLORI_VENTO[a.colore] || "var(--grigio)"}"></span>${Math.round(a.vento_kmh)} km/h da ${cardinale(a.direzione_vento)} <small>(${nodi(a.vento_kmh)} nodi), ${VENTO_A_PAROLE[a.colore]}</small>`]);
    righe.push(["Onda", `${numero(a.onda_m)} m`]);
    if (a.codice_meteo != null) {
      const tipo = cielo(a.codice_meteo, a.pioggia_mm || 0);
      const pioggia = [a.pioggia_mm >= 0.2 ? `${numero(a.pioggia_mm)} mm in un'ora` : "",
        a.prob_pioggia >= 10 ? `probabilità di pioggia ${Math.round(a.prob_pioggia)}%` : ""]
        .filter(Boolean).map((x) => ` <small>${x}</small>`).join("");
      righe.push(["Cielo", `${icona(tipo)} ${tipo}${pioggia}`]);
    }
    if (a.aria_c != null) righe.push(["Aria", `${Math.round(a.aria_c)} °C`]);
    if (a.acqua_c != null) righe.push(["Acqua", `${Math.round(a.acqua_c)} °C <small>${muta(Math.round(a.acqua_c))}</small>`]);
  }
  return `<section class="adesso">
    <h3>Adesso</h3>
    ${righe.length ? `<dl class="adesso-dati">${righe.map(([k, v]) => `<dt>${k}</dt><dd>${v}</dd>`).join("")}</dl>` : ""}
    ${webcam ? `<p class="etichetta-webcam">Webcam</p><ul class="webcam" aria-label="Webcam vicine">${webcam}</ul>` : ""}
    <p class="mare-dal-vivo">Il modello non è la riva: guarda il mare 10 minuti prima di entrare e non entrare da solo. Emergenza 112.</p>
  </section>`;
}

function disegnaUV(spot) {
  const giorni = (spot.giorni || []).filter((g) => g.uv_max != null);
  if (!giorni.length) return "";
  const oggi = giorni[0];
  const c = categoriaUV(oggi.uv_max);
  const valore = Math.round(oggi.uv_max);
  // la scala va da 0 a 11+: ogni categoria occupa i suoi numeri
  const segmenti = [[0, 3], [3, 6], [6, 8], [8, 11], [11, 12]].map(([da, a], i) =>
    `<span style="flex:${a - da};background:${UV[i].colore}"></span>`).join("");
  // il segno sta a meta' della casella del suo numero: 8 cade nel rosso, non sul bordo
  const posizione = (Math.min(valore, 11) + 0.5) / 12 * 100;
  const prossimi = giorni.slice(1, 7).map((g) => {
    const k = categoriaUV(g.uv_max);
    const breve = new Intl.DateTimeFormat("it-IT", { weekday: "short", day: "numeric" }).format(comeData(g.data));
    return `<li><span class="uv-giorno">${maiuscola(breve)}</span>
      <span class="uv-valore"><i style="background:${k.colore}"></i>${Math.round(g.uv_max)}</span></li>`;
  }).join("");
  return `<section class="uv" aria-label="Raggi UV">
    <h3>Raggi UV</h3>
    <div class="uv-oggi">
      <span class="uv-numero">${valore}</span>
      <p><strong>${maiuscola(c.nome)}</strong><br><small>${oggi.giorno === 1 ? "oggi" : nomeGiorno(oggi.data).toLowerCase()}, il massimo verso le ${Number(oggi.uv_ora.slice(0, 2))}</small></p>
    </div>
    <div class="uv-scala" aria-hidden="true">${segmenti}<b style="left:${posizione}%"></b></div>
    <div class="uv-numeri" aria-hidden="true"><span>0</span><span>3</span><span>6</span><span>8</span><span>11+</span></div>
    ${prossimi ? `<ul class="uv-prossimi" aria-label="I prossimi giorni">${prossimi}</ul>` : ""}
  </section>`;
}

function disegnaFronte(spot) {
  if (!spot.fronte) return "";
  // la tappa dell'ora attuale, se la serie ce l'ha
  const qui = oraAttuale(spot);
  const f = { ...spot.fronte };
  if (qui && qui.tappa != null && f.descrizioni) {
    f.tappa = qui.tappa;
    f.nome = TAPPE[qui.tappa] || null;
    f.spiaggia = f.descrizioni[String(qui.tappa)] || null;
  }
  const passaggi = (f.passaggi || []).map((p) => {
    const quando = `${nomeGiorno(p.ora.slice(0, 10)).toLowerCase()} verso le ${Number(ora(p.ora).slice(0, 2))}`;
    const verbo = comeData(p.ora) < new Date() ? "è passato" : "passa";
    const dopo = p.scaduta ? `, poi la scaduta ${nomeGiorno(p.scaduta.slice(0, 10)).toLowerCase()} dall'alba alle 10` : "";
    return `Il fronte ${verbo} ${quando}${dopo}.`;
  });
  if (!f.tappa && !passaggi.length) {
    return `<section class="fronte">
      <h3>Il fronte</h3>
      <p>Nessun fronte in vista nei prossimi giorni.${perche(GUIDE.scaduta)}</p>
    </section>`;
  }
  const strada = TAPPE.slice(1).map((nome, i) => {
    const n = i + 1;
    return `<li class="${n === f.tappa ? "qui" : ""}${n === 4 ? " passaggio" : ""}" title="${n}. ${nome}"><span>${n}</span></li>`;
  }).join("");
  const titolo = f.tappa ? `Il fronte: tappa ${f.tappa} di 7, ${f.nome}` : "Il fronte";
  return `<section class="fronte">
    <h3>${titolo}</h3>
    <ol class="tappe" aria-label="Le sette tappe del passaggio di un fronte">${strada}</ol>
    ${f.tappa ? `<p>${f.spiaggia}</p>` : ""}
    ${passaggi.length ? `<p>${passaggi.join(" ")}${perche(GUIDE.scaduta)}</p>` : ""}
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
    const bagnato = ["pioggia", "temporale"].includes(g.cielo) && g.prob_pioggia_max != null;
    const accanto = bagnato ? ` ${Math.round(g.prob_pioggia_max)}%` : (g.aria_max != null ? ` ${Math.round(g.aria_max)}°` : "");
    const titolo = [g.cielo, g.aria_max != null ? `massima ${Math.round(g.aria_max)} °C` : "",
      g.prob_pioggia_max != null ? `pioggia ${Math.round(g.prob_pioggia_max)}%` : ""].filter(Boolean).join(", ");
    const meteo = g.cielo ? `<span class="meteo-giorno${bagnato ? " bagnato" : ""}" title="${titolo}">${icona(g.cielo, 15)}${accanto}</span>` : "";
    const nota = meteo + (g.fiducia === "tendenza" ? "<small>tendenza</small>" : "");
    const riga = `<tr class="${g.fiducia}"><th scope="row" class="giorno">${nomeGiorno(g.data, false)}${nota}</th>${celle}</tr>`;
    const aperta = stato.aperta && stato.aperta.startsWith(g.data + "|")
      ? `<tr><td colspan="5">${disegnaDettaglio(spot, g, stato.aperta.split("|")[1])}</td></tr>` : "";
    return riga + aperta;
  }).join("");
  return `<section class="settimana">
    <h3>I prossimi giorni</h3>
    <p class="istruzione">Tocca una casella per vedere il dettaglio ora per ora.</p>
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
      <td>${ora(o.ora)}${o.codice_meteo != null ? `<br><span class="meteo-ora">${icona(cielo(o.codice_meteo, o.pioggia_mm || 0), 14)}${o.aria_c != null ? ` ${Math.round(o.aria_c)}°` : ""}</span>${o.pioggia_mm >= 0.1 || o.prob_pioggia >= 20 ? `<small class="mm">${[o.pioggia_mm >= 0.1 ? `${numero(o.pioggia_mm)} mm` : "", o.prob_pioggia >= 20 ? `${Math.round(o.prob_pioggia)}%` : ""].filter(Boolean).join(", ")}</small>` : ""}` : ""}</td>
      <td>${numero(o.onda_m)} m<br><small>${o.parte}, ${numero(o.periodo_s, 0)} s</small></td>
      <td>${freccia(o.direzione_onda)} ${cardinale(o.direzione_onda, true)}</td>
      <td class="vento-${o.colore}"><span class="pallino"></span>${freccia(o.direzione_vento)} ${Math.round(o.vento_kmh)} <small>(${nodi(o.vento_kmh)} kn)</small><br><small>da ${cardinale(o.direzione_vento, true)}, raffiche ${Math.round(o.raffiche_kmh)}</small></td>
      <td class="voto-ora">${voto(o.voto)}</td>
    </tr>`).join("");
  return `<div class="dettaglio" id="dettaglio">
    <div class="dettaglio-testa">
      <h4>${nomeGiorno(giorno.data)}, ${f.frase}<small>${spot.nome.split("–").pop().trim()}${giorno.acqua_c != null ? `, acqua ${Math.round(giorno.acqua_c)} °C` : ""}</small></h4>
      <div class="azioni-dettaglio">
        <button type="button" class="chiudi condividi-piccolo" data-condividi="${giorno.data}|${chiave}">Condividi</button>
        <button type="button" class="chiudi" aria-label="Chiudi il dettaglio">Chiudi</button>
      </div>
    </div>
    ${segnali.length ? `<ul class="segnali">${segnali.map((s) => `<li>${maiuscola(s)}.</li>`).join("")}</ul>` : ""}
    <table class="ore">
      <thead><tr><th>Ora</th><th>Onda</th><th>Da</th><th>Vento km/h</th><th>Voto</th></tr></thead>
      <tbody>${righe}</tbody>
    </table>
  </div>`;
}


/* ------------------------------------------------------------- grafico */
// Come i grafici dei siti di surf: in alto il voto, poi l'onda, poi il vento,
// ora per ora, uno sotto l'altro sulla stessa linea del tempo (mai due scale insieme).

const COLORI_VENTO = { verde: "var(--verde)", giallo: "var(--giallo)", rosso: "var(--rosso)", grigio: "var(--grigio)" };
const COLORI_VOTO = ["var(--v0)", "var(--v1)", "var(--v2)", "var(--v3)", "var(--v4)", "var(--v5)"];

function barraArrotondata(x, y, w, h, r = 3) {
  // barra con gli angoli in alto arrotondati, appoggiata alla base
  if (h <= 0) return "";
  r = Math.min(r, w / 2, h);
  return `M${x},${y + h}V${y + r}Q${x},${y} ${x + r},${y}H${x + w - r}Q${x + w},${y} ${x + w},${y + r}V${y + h}Z`;
}

function frecciaSvg(cx, cy, direzione, colore = "var(--fondale)") {
  const verso = (direzione + 180) % 360;
  return `<path d="M0,-6L4,2H1V6H-1V2H-4Z" fill="${colore}" transform="translate(${cx},${cy}) rotate(${verso})"/>`;
}

function disegnaGrafico(spot) {
  const punti = (spot.serie && spot.serie.length ? spot.serie : spot.ore) || [];
  if (!punti.length) return "";
  const L = 12;                    // larghezza di un'ora
  const largh = punti.length * L;
  const zero = (spot.altezzaVoto && spot.altezzaVoto.zero) || 2;
  const maxOnda = Math.max(zero + 0.3, ...punti.map((p) => p.onda_m || 0));
  const maxVento = Math.max(40, ...punti.map((p) => p.raffiche_kmh || 0));

  // posizioni verticali dei tre pannelli
  const yGiorni = 14, yVoto = 22, hVoto = 12;
  const yMeteo = 37;               // icone del tempo
  const yOnda = 70, hOnda = 96;
  const yFrecceOnda = yOnda + hOnda + 12;
  const yVento = yFrecceOnda + 30, hVento = 76;
  const yFrecceVento = yVento + hVento + 12;
  const alto = yFrecceVento + 12;
  const yH = (h) => yOnda + hOnda - (h / maxOnda) * hOnda;
  const yV = (v) => yVento + hVento - (v / maxVento) * hVento;

  let notte = "", giorni = "", voto = "", onda = "", vento = "", frecce = "", valori = "", zone = "", fronti = "";
  let giornoPrima = null, massimo = null, etichettaFatta = true;

  const chiudiGiorno = () => {
    if (massimo) {
      const x = massimo.i * L + L / 2;
      valori += `<text class="valore" x="${x}" y="${yH(massimo.p.onda_m) - 4}" text-anchor="middle">${numero(massimo.p.onda_m)}</text>`;
    }
  };

  punti.forEach((p, i) => {
    const x = i * L;
    const data = p.ora.slice(0, 10);
    if (data !== giornoPrima) {
      chiudiGiorno();
      massimo = null;
      if (i > 0) giorni += `<line x1="${x}" x2="${x}" y1="0" y2="${alto}" stroke="var(--riga)" stroke-width="1"/>`;
      giornoPrima = data; etichettaFatta = false;
    }
    // il nome del giorno va dove comincia la luce, cioe' dove si guarda
    if (!etichettaFatta && p.di_giorno !== false) {
      giorni += `<text class="etichetta-giorno" x="${x + 2}" y="${yGiorni}">${nomeGiorno(data, false)}</text>`;
      etichettaFatta = true;
    }
    if (p.di_giorno === false) notte += `<rect x="${x}" y="${yVoto}" width="${L}" height="${alto - yVoto}" fill="var(--riga)" fill-opacity="0.45"/>`;
    if (p.di_giorno !== false && (!massimo || p.onda_m > massimo.p.onda_m)) massimo = { p, i };

    // voto: una casella per ora, blu piu' scuro = voto piu' alto (solo con la luce)
    const v = p.di_giorno === false ? 0 : Math.max(0, Math.min(5, Math.floor(p.voto || 0)));
    voto += `<rect x="${x + 1}" y="${yVoto}" width="${L - 2}" height="${hVoto}" rx="2" fill="${COLORI_VOTO[v]}"/>`;

    // onda totale
    onda += `<path d="${barraArrotondata(x + 2, yH(p.onda_m), L - 4, yOnda + hOnda - yH(p.onda_m))}" fill="var(--v4)"/>`;

    // vento: barra del colore della guida, raffica come trattino
    vento += `<path d="${barraArrotondata(x + 2, yV(p.vento_kmh), L - 4, yVento + hVento - yV(p.vento_kmh))}" fill="${COLORI_VENTO[p.colore] || "var(--grigio)"}"/>`;
    if (p.raffiche_kmh > p.vento_kmh) vento += `<line x1="${x + 2}" x2="${x + L - 2}" y1="${yV(p.raffiche_kmh)}" y2="${yV(p.raffiche_kmh)}" stroke="var(--inchiostro)" stroke-opacity="0.45" stroke-width="2" stroke-linecap="round"/>`;

    // frecce e tempo ogni 3 ore; di notte il tempo solo se piove
    if (Number(p.ora.slice(11, 13)) % 3 === 0) {
      const tipo = p.codice_meteo != null ? cielo(p.codice_meteo, p.pioggia_mm || 0) : null;
      if (tipo && (p.di_giorno !== false || ["pioggia", "temporale", "neve"].includes(tipo))) {
        frecce += iconaSvg(tipo, x + L / 2, yMeteo);
      }
      frecce += frecciaSvg(x + L / 2, yFrecceOnda, p.direzione_onda);
      frecce += frecciaSvg(x + L / 2, yFrecceVento, p.direzione_vento);
    }
    // il passaggio del fronte: linea tratteggiata blu, come nella seconda guida
    if (p.fronte) {
      fronti += `<line x1="${x + L / 2}" x2="${x + L / 2}" y1="${yVoto}" y2="${alto}" class="linea-fronte"/>
        <text class="etichetta-fronte" x="${x + L / 2 + 3}" y="${yGiorni}">fronte</text>`;
    }
    zone += `<rect class="zona" data-i="${i}" x="${x}" y="0" width="${L}" height="${alto}" fill="transparent"/>`;
  });
  chiudiGiorno();

  // griglie leggere: il limite dello spot per l'onda, le fasce della prima guida per il vento
  const griglia = `
    <line x1="0" x2="${largh}" y1="${yH(zero)}" y2="${yH(zero)}" stroke="var(--rosso)" stroke-width="1" stroke-dasharray="4 4"/>
    ${[10, 20, 30].map((k) => `<line x1="0" x2="${largh}" y1="${yV(k)}" y2="${yV(k)}" stroke="var(--riga)" stroke-width="1"/>`).join("")}`;

  // le scritte degli assi restano ferme a sinistra mentre il grafico scorre
  const fissa = (y, testo, classe = "") => `<span class="${classe}" style="top:${Math.round(y)}px">${testo}</span>`;
  const fisse = [
    fissa(yOnda - 17, "Onda, metri"),
    fissa(yH(zero) - 16, `${numero(zero)} m: oltre non si esce`, "limite"),
    fissa(yVento - 19, "Vento, km/h; il trattino sono le raffiche"),
    // con raffiche forti la scala si comprime: allora si scrive solo 10 e 30
    ...(hVento * 10 / maxVento < 15 ? [10, 30] : [10, 20, 30]).map((k) => fissa(yV(k) - 7, k, "tacca")),
  ].join("");

  return `<section class="grafico">
    <h3>Il grafico della settimana</h3>
    <p class="istruzione">Scorri di lato; tocca un'ora per leggere i valori. Le zone grigie sono la notte.</p>
    <div class="area-grafico">
    <div class="scorri" id="scorri-grafico">
      <svg width="${largh}" height="${alto}" viewBox="0 0 ${largh} ${alto}" role="img" aria-label="Onda e vento ora per ora nei prossimi 7 giorni">
        ${notte}<rect id="fascia-scelta" class="fascia-scelta" x="-100" y="${yVoto}" width="0" height="${alto - yVoto}"/>${giorni}${griglia}${voto}${onda}${vento}${frecce}${valori}${fronti}
        <rect id="ora-attiva" class="ora-attiva" x="-20" y="0" width="${L}" height="${alto}"/>
        ${zone}
      </svg>
      <div class="suggerimento" id="suggerimento" hidden></div>
    </div>
    <div class="fisse" aria-hidden="true">${fisse}</div>
    </div>
    <div class="legenda-grafico">
      <span>La striscia in alto è il voto: blu più scuro, meglio.</span>
      <span>Le icone in alto sono il tempo, ogni 3 ore.</span>
      <span>Le frecce indicano dove vanno onda e vento.</span>
      ${punti.some((p) => p.fronte) ? "<span>La linea blu tratteggiata è il passaggio del fronte.</span>" : ""}
    </div>
  </section>`;
}

function attivaGrafico(spot) {
  const contenitore = document.getElementById("scorri-grafico");
  if (!contenitore) return;
  const punti = (spot.serie && spot.serie.length ? spot.serie : spot.ore) || [];
  const box = document.getElementById("suggerimento");
  const evidenza = document.getElementById("ora-attiva");
  const mostra = (i) => {
    const p = punti[i];
    if (!p) return;
    const x = i * 12;
    evidenza.setAttribute("x", x);
    box.hidden = false;
    box.innerHTML = `<strong>${nomeGiorno(p.ora.slice(0, 10), false)}, ore ${ora(p.ora)}</strong><br>
      Onda ${numero(p.onda_m)} m, ${numero(p.periodo_s, 0)} s, da ${cardinale(p.direzione_onda)}<br>
      Vento ${Math.round(p.vento_kmh)} km/h (${nodi(p.vento_kmh)} nodi) da ${cardinale(p.direzione_vento)}<br>
      <span class="pallino" style="background:${COLORI_VENTO[p.colore] || "var(--grigio)"}"></span> ${p.colore}, raffiche ${Math.round(p.raffiche_kmh)} km/h<br>
      ${p.codice_meteo != null ? `${icona(cielo(p.codice_meteo, p.pioggia_mm || 0), 14)} ${cielo(p.codice_meteo, p.pioggia_mm || 0)}${p.pioggia_mm >= 0.1 ? ` ${numero(p.pioggia_mm)} mm` : ""}${p.aria_c != null ? `, aria ${Math.round(p.aria_c)} °C` : ""}${p.prob_pioggia >= 10 ? `<br>Probabilità di pioggia ${Math.round(p.prob_pioggia)}%` : ""}<br>` : ""}
      ${p.di_giorno === false ? "Notte" : `Voto ${voto(p.voto)}`}${p.tappa ? `<br>Tappa ${p.tappa} di 7: ${TAPPE[p.tappa]}` : ""}`;
    const sinistra = Math.min(Math.max(x + 16 - contenitore.scrollLeft, 8), contenitore.clientWidth - box.offsetWidth - 8);
    box.style.left = `${sinistra + contenitore.scrollLeft}px`;
  };
  let aperta = null;
  const nascondi = () => { box.hidden = true; evidenza.setAttribute("x", -20); aperta = null; };
  contenitore.querySelectorAll(".zona").forEach((z) => {
    const i = Number(z.dataset.i);
    // col mouse basta passarci sopra; col dito no, se no si apre a ogni sfioro
    z.addEventListener("pointerenter", (e) => { if (e.pointerType === "mouse") { mostra(i); aperta = i; } });
    // il click arriva solo da un tocco vero, non quando si scorre
    z.addEventListener("click", (e) => {
      e.stopPropagation();
      if (aperta === i && e.pointerType !== "mouse") nascondi();
      else { mostra(i); aperta = i; }
    });
  });
  contenitore.addEventListener("pointerleave", (e) => { if (e.pointerType === "mouse") nascondi(); });
  contenitore.addEventListener("scroll", () => { if (aperta !== null && !box.hidden) nascondi(); }, { passive: true });
  stato.chiudiGrafico = nascondi;
  // se hai toccato una casella dei prossimi giorni, il grafico va alla stessa fascia
  // e la evidenzia; altrimenti parte dalla prima luce di oggi
  if (stato.aperta) {
    const [data, chiave] = stato.aperta.split("|");
    const f = FASCE[chiave];
    const dentro = punti.map((p, i) => [p, i]).filter(([p]) => {
      const h = Number(ora(p.ora).slice(0, 2));
      return p.ora.startsWith(data) && p.di_giorno !== false && h >= f.da && h < f.a;
    }).map(([, i]) => i);
    if (dentro.length) {
      const da = dentro[0], a = dentro[dentro.length - 1] + 1;
      const fascia = document.getElementById("fascia-scelta");
      fascia.setAttribute("x", da * 12);
      fascia.setAttribute("width", (a - da) * 12);
      contenitore.scrollLeft = Math.max(0, ((da + a) / 2) * 12 + 16 - contenitore.clientWidth / 2);
      return;
    }
  }
  const primaLuce = punti.findIndex((p) => p.di_giorno !== false);
  if (primaLuce > 0) contenitore.scrollLeft = Math.max(0, primaLuce * 12 - 24);
}

function disegnaScheda(spot) {
  if (!spot.scheda || !spot.scheda.length) return "";
  const righe = spot.scheda.map(([voce, testo]) => `<dt>${voce}</dt><dd>${testo}</dd>`).join("");
  return `<details class="apribile scheda">
    <summary>Com'è lo spot</summary>
    <dl>${righe}</dl>
  </details>`;
}

// la verifica arriva da un file a parte: se manca, la pagina va avanti senza
async function caricaVerifica() {
  try {
    const r = await fetch(`${VERIFICA}?t=${Date.now()}`, { cache: "no-store" });
    if (r.ok) stato.verifica = await r.json();
  } catch (e) { /* senza rete o non ancora creata */ }
}

function disegnaVerifica(spot) {
  const tutto = stato.verifica;
  const v = tutto && tutto.spot.find((x) => x.id === spot.id);
  if (!v) return "";
  const nota = "<p class=\"nota\">È un modello al largo: dice quanto cambiano le previsioni, non com'è la riva.</p>";
  const r = v.riscontri;
  const pulsanti = r ? `<p>Dai pulsanti di Telegram: ${r.meglio} volte meglio, ${r.come} come previsto, ${r.peggio} peggio.${r.giudizio ? ` ${r.giudizio}` : ""}</p>` : "";
  if (!v.pronta) {
    const n = v.giorni_storico;
    const mancano = tutto.giorni_minimi - n;
    const dal = v.dal ? `, dal ${new Intl.DateTimeFormat("it-IT", { day: "numeric", month: "long" }).format(comeData(v.dal))}` : "";
    const finora = n === 1 ? "c'è 1 giorno" : `ci sono ${n} giorni`;
    return `<details class="apribile verifica">
      <summary>Quanto ci prende <small>dal ${new Intl.DateTimeFormat("it-IT", { day: "numeric", month: "long" }).format(new Date(Date.now() + mancano * 864e5))}</small></summary>
      <p>La verifica parte quando lo storico copre ${tutto.giorni_minimi} giorni: per ora ${finora}${dal}. ${mancano === 1 ? "Manca 1 giorno" : `Ne mancano ${mancano}`}.</p>
      ${pulsanti}
    </details>`;
  }
  const verso = (x, sopra, sotto, soglia) => Math.abs(x) >= soglia
    ? `<small>di solito ${x > 0 ? sopra : sotto}</small>` : "";
  const righe = (v.anticipi || []).map((a) => `<tr>
      <th scope="row">${a.giorni === 1 ? "1 giorno prima" : `${a.giorni} giorni prima`}</th>
      <td>± ${numero(a.onda_errore_m, 2)} m ${verso(a.onda_scarto_m, "più alta", "più bassa", 0.1)}</td>
      <td>± ${Math.round(a.vento_errore_kmh)} km/h ${verso(a.vento_scarto_kmh, "più forte", "più debole", 3)}</td>
    </tr>`).join("");
  const proposte = (v.proposte || []).map((x) => `<li>${x}</li>`).join("");
  return `<details class="apribile verifica">
    <summary>Quanto ci prende</summary>
    <p>Negli ultimi ${tutto.finestra_giorni} giorni, di quanto ha sbagliato in media la previsione fatta:</p>
    <table class="tabella-verifica">
      <thead><tr><th></th><th scope="col">Onda</th><th scope="col">Vento</th></tr></thead>
      <tbody>${righe}</tbody>
    </table>
    ${proposte ? `<p class="titoletto">Da valutare:</p><ul class="segnali">${proposte}</ul>` : ""}
    ${pulsanti}
    ${nota}
  </details>`;
}

function disegnaLegenda() {
  const guida = perche(GUIDE.vento);
  return `<details class="apribile legenda">
    <summary>Come si legge</summary>
    <p>La bandierina a sinistra di ogni casella è il colore del vento, come nelle guide.${guida}</p>
    <ul>
      <li><span class="pallino vento-verde"></span>Verde: da Est e Nord-Est, viene da terra.</li>
      <li><span class="pallino vento-giallo"></span>Giallo: da Sud-Est e Nord-Ovest, di lato.</li>
      <li><span class="pallino vento-rosso"></span>Rosso: da Sud, Sud-Ovest e Ovest, viene dal mare.</li>
      <li><span class="pallino vento-grigio"></span>Grigio: da Nord, la tramontana spiana il mare.</li>
    </ul>
    <p>Più il blu è scuro, più il voto è alto.</p>
    <div class="scala" aria-hidden="true">0 <span style="background:var(--v0)"></span><span style="background:var(--v1)"></span><span style="background:var(--v2)"></span><span style="background:var(--v3)"></span><span style="background:var(--v4)"></span><span style="background:var(--v5)"></span> 5</div>
    <p class="icone-legenda">${["sereno", "variabile", "coperto", "pioggia", "temporale", "nebbia"].map((t) => `<span>${icona(t)} ${t}</span>`).join("")}</p>
    <p>Sotto ogni giorno: il tempo e la temperatura massima dell'aria nelle ore di luce; nei giorni di pioggia, al posto della temperatura, la probabilità di pioggia.</p>
    <p>S indica la scaduta, ? che i modelli non sono d'accordo sull'onda o sul vento. I giorni più chiari sono una tendenza.</p>
  </details>`;
}

function confronti(spot) {
  let elenco = spot.confronto || [];
  if (typeof elenco === "string") elenco = [{ nome: "Surfnerd", url: elenco }];
  if (!elenco.length) return "";
  return `<p>Per un confronto: ${elenco.map((c) =>
    `<a href="${c.url}" target="_blank" rel="noopener">${c.nome}</a>`).join(", ")}.</p>`;
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
    ${confronti(spot)}
    <p>Le guide: <a href="${GUIDE.vento}" target="_blank" rel="noopener">Il mare e il vento</a> e <a href="${GUIDE.scaduta}" target="_blank" rel="noopener">Il vento che gira</a>.</p>
    ${d.crediti.map((c) => `<p>${c}</p>`).join("")}`;
}

function disegna() {
  const spot = stato.dati.spot[stato.spot];
  disegnaScelta();
  $("#contenuto").innerHTML = disegnaRisposta(spot) + disegnaAdesso(spot) + disegnaUV(spot) + disegnaGriglia(spot) + disegnaGrafico(spot) + disegnaFronte(spot)
    + `<div class="consulta">${disegnaScheda(spot)}${disegnaLegenda()}${disegnaVerifica(spot)}</div>`;
  document.querySelectorAll(".cella").forEach((c) => c.addEventListener("click", () => {
    stato.aperta = stato.aperta === c.dataset.cella ? null : c.dataset.cella;
    disegna();
    const di_nuovo = document.querySelector(`[data-cella="${c.dataset.cella}"]`);
    if (di_nuovo) di_nuovo.focus();
  }));
  const vedi = document.querySelector(".vedi");
  if (vedi) vedi.addEventListener("click", () => {
    stato.aperta = vedi.dataset.vai;
    disegna();
    const d = document.getElementById("dettaglio");
    if (d) d.scrollIntoView({ behavior: "smooth", block: "start" });
  });
  const chiudi = document.querySelector('.chiudi[aria-label="Chiudi il dettaglio"]');
  if (chiudi) chiudi.addEventListener("click", () => { stato.aperta = null; disegna(); });
  document.querySelectorAll("[data-condividi]").forEach((b) =>
    b.addEventListener("click", () => condividi(b)));
  attivaGrafico(spot);
  disegnaPiede();
}

/* ------------------------------------------------------------- avvio */

// un link condiviso aperto con la pagina gia' aperta: si va li' senza ricaricare
window.addEventListener("hashchange", () => {
  if (!stato.dati || !leggiIndirizzo()) return;
  disegna();
  const d = document.getElementById("dettaglio");
  if (d) d.scrollIntoView({ block: "start" });
  history.replaceState(null, "", location.pathname);
});

document.addEventListener("click", (e) => {
  if (stato.chiudiGrafico && !e.target.closest("#scorri-grafico")) stato.chiudiGrafico();
});

(async function avvio() {
  try {
    const { dati, offline } = await caricaDati();
    stato.dati = dati;
    stato.offline = offline;
    let salvato = 0;
    try { salvato = Number(localStorage.getItem(CHIAVE_SPOT)) || 0; } catch (e) { /* niente */ }
    stato.spot = Math.min(salvato, dati.spot.length - 1);
    stato.aperta = null;
    const daLink = leggiIndirizzo();
    disegna();
    if (daLink) {
      const d = document.getElementById("dettaglio");
      if (d) d.scrollIntoView({ block: "start" });
      history.replaceState(null, "", location.pathname);  // ricaricando si riparte normale
    }
    caricaVerifica().then(() => { if (stato.verifica) disegna(); });
  } catch (errore) {
    $("#contenuto").innerHTML = `<p class="errore">Non riesco a scaricare le previsioni (${errore.message}).
      Controlla la connessione e ricarica la pagina.</p>`;
  }
})();
