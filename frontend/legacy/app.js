// ================================================================
// JobMatcher — frontend
// SPA leggera: fetch dell'API + rendering vanilla JS.
// Stato in localStorage per persistere user_id e session_id attivi.
// ================================================================
import { ROLE_CATALOG } from "./roles.js";

const API = "/api";

const state = {
  userId: localStorage.getItem("jm.userId") || null,
  sessionId: localStorage.getItem("jm.sessionId") || null,
  view: "profile",
  softCatalog: [],
  softSelected: new Set(),
  userLanguages: [], 
  currentCompanySuggestions: [],
  targetCompanies: [],
  // I pannelli in cima a "Ricerche" definiscono una ricerca che ANCORA NON
  // ESISTE: competenze e aziende vivono qui finche' non si preme "Crea
  // ricerca", e partono tutte insieme nello stesso payload. Prima
  // comparivano solo a sessione gia' creata, il che diceva all'utente che
  // non facessero parte della definizione della ricerca. Non era vero, e
  // nemmeno tecnicamente necessario: gli endpoint di scoperta ignorano la
  // sessione.

  draftSkills: [],
  draftCompanies: [],
  preferredCompanies: [],
  suggestedRoleSkills: [],
  matchStatusFilter: "",
  pollTimer: null,
  resultsItems: [],       // merge di listings + matches (RF... layout a 3 zone)
  selectedResultItem: null,
};

// ---------- HTTP ----------
async function api(method, path, body) {
  const opt = { 
    method, 
    headers: { 
      "Content-Type": "application/json",
      "X-API-Token": "local-dev-token-2026", 
    } 
  };
  if (body !== undefined) opt.body = JSON.stringify(body);
  const r = await fetch(API + path, opt);
  if (!r.ok) {
    let msg = `${r.status} ${r.statusText}`;
    try { const j = await r.json(); if (j.detail) msg = j.detail; } catch {}
    throw new Error(msg);
  }
  if (r.status === 204) return null;
  return r.json();
}
const get   = (p)     => api("GET",    p);
const post  = (p, b)  => api("POST",   p, b);
const patch = (p, b)  => api("PATCH",  p, b);
const del   = (p)     => api("DELETE", p);

// ---------- Toast ----------
const toastEl = document.getElementById("toast");
let toastTimer;
function toast(msg, kind = "") {
  toastEl.textContent = msg;
  toastEl.className = `toast is-up ${kind}`;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => toastEl.classList.remove("is-up"), 3200);
}

// ---------- Utility ----------
const $ = (id) => document.getElementById(id);
function fmtPct(n) { return `${Math.round((n || 0) * 100)}%`; }
function scoreClass(s) { return s >= 0.7 ? "hi" : s >= 0.5 ? "mid" : "lo"; }
function parseJSON(s, fb) { try { return JSON.parse(s || ""); } catch { return fb; } }
// I nomi di aziende e settori arrivano da un LLM e da Places, e finiscono
// dentro innerHTML: vanno neutralizzati prima, non dopo.
function escapeHtml(s) {
  return String(s ?? "").replace(/[&<>"']/g, c => (
    { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]
  ));
}
function el(tag, cls, txt) {
  const e = document.createElement(tag);
  if (cls) e.className = cls;
  if (txt !== undefined) e.textContent = txt;
  return e;
}

// ---------- Autocomplete generico (catalogo statico, filtro locale) ----------
// Match case-insensitive ovunque nella stringa, non solo a inizio parola —
// max 8 risultati, navigazione da tastiera (frecce/invio/esc).
function attachAutocomplete(inputEl, listEl, catalog, { maxResults = 8 } = {}) {
  let activeIndex = -1;
  let currentMatches = [];

  function render() {
    listEl.innerHTML = "";
    currentMatches.forEach((m, i) => {
      const li = el("li", i === activeIndex ? "is-active" : "", m);
      // mousedown (non click) così scatta PRIMA del blur dell'input
      li.addEventListener("mousedown", (e) => { e.preventDefault(); select(m); });
      listEl.appendChild(li);
    });
  }

  function open(matches) {
    currentMatches = matches;
    activeIndex = -1;
    if (!matches.length) { close(); return; }
    render();
    listEl.classList.add("is-open");
  }

  function close() {
    listEl.classList.remove("is-open");
    listEl.innerHTML = "";
    currentMatches = [];
    activeIndex = -1;
  }

  function select(value) {
    inputEl.value = value;
    close();
  }

  inputEl.addEventListener("input", () => {
    const q = inputEl.value.trim().toLowerCase();
    if (!q) { close(); return; }
    open(catalog.filter(v => v.toLowerCase().includes(q)).slice(0, maxResults));
  });

  inputEl.addEventListener("keydown", (e) => {
    if (!currentMatches.length) return;
    if (e.key === "ArrowDown") {
      e.preventDefault();
      activeIndex = (activeIndex + 1) % currentMatches.length;
      render();
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      activeIndex = (activeIndex - 1 + currentMatches.length) % currentMatches.length;
      render();
    } else if (e.key === "Enter" && activeIndex >= 0) {
      e.preventDefault();
      select(currentMatches[activeIndex]);
    } else if (e.key === "Escape") {
      close();
    }
  });

  // piccolo delay: lascia il tempo al mousedown sulla lista di registrarsi
  // prima che il blur dell'input la chiuda
  inputEl.addEventListener("blur", () => setTimeout(close, 100));
}

// ---------- Navigation ----------
document.querySelectorAll(".rail-item").forEach(btn => {
  btn.addEventListener("click", () => switchView(btn.dataset.view));
});
function switchView(name) {
  state.view = name;
  document.querySelectorAll(".rail-item").forEach(b => b.classList.toggle("is-active", b.dataset.view === name));
  document.querySelectorAll(".view").forEach(v => v.classList.toggle("is-visible", v.id === `view-${name}`));
  if (name === "intelligence" && state.sessionId) refreshIntelligence();
  if (name === "sessions" && state.userId) refreshSessions();
  if (name === "collections" && state.userId) { loadCollections(); loadThemes(); }
  updateSaveBarVisibility();
}

// ---------- Barra sticky "Salva profilo" ----------
const saveBarEl = $("saveBar");
const saveBarTextEl = $("saveBarText");
let saveBarHideTimer = null;

function showSaveBar() {
  clearTimeout(saveBarHideTimer);
  saveBarEl.classList.add("is-visible");
}
function hideSaveBar() {
  saveBarEl.classList.remove("is-visible");
}

function updateSaveBarVisibility() {
  // fuori dalla view Profilo la barra non ha senso, si nasconde sempre.
  // dentro Profilo resta visibile solo se ci sono modifiche non salvate:
  // lo stato "saved" si nasconde da solo dopo un breve momento (sotto) e
  // non deve ricomparire solo perché l'utente rientra nella view.
  if (state.view !== "profile") { hideSaveBar(); return; }
  if (saveBarEl.classList.contains("is-dirty")) showSaveBar();
}

function setSaveBarState(kind) {
  // kind: 'dirty' (modifiche non salvate) | 'saved' (allineato al DB)
  saveBarEl.classList.remove("is-dirty", "is-saved");
  saveBarEl.classList.add(kind === "saved" ? "is-saved" : "is-dirty");
  if (kind === "saved") {
    saveBarTextEl.textContent = "Tutto salvato";
    $("btnSaveProfile").textContent = "Profilo salvato ✓";
    showSaveBar();
    // stato di riposo: si mostra brevemente poi sparisce da sola, non
    // resta appesa in fondo alla pagina come una notifica bloccata
    saveBarHideTimer = setTimeout(hideSaveBar, 2500);
  } else {
    saveBarTextEl.textContent = "Modifiche non salvate";
    $("btnSaveProfile").textContent = "Salva profilo";
    showSaveBar();
  }
}

["pfName", "pfEmail", "pfPhone", "pfLocation"].forEach(id => {
  const el = $(id);
  if (el) el.addEventListener("input", () => setSaveBarState("dirty"));
});

setSaveBarState("dirty");
updateSaveBarVisibility();


$("btnAnalyzeUrl").addEventListener("click", async () => {
  const url = $("customUrl").value.trim();
  if (!url) { toast("Incolla l'URL dell'annuncio", "bad"); return; }
  if (!state.userId) { toast("Crea prima il profilo", "bad"); return; }

  toast("Analizzo l'annuncio...", "");
  try {
    const r = await post(`/users/${state.userId}/custom-cv`, { url });

    const box = $("customResult");
    box.innerHTML = "";

    if (r.score !== undefined) {
      const scorePanel = el("div", "panel");
      scorePanel.appendChild(el("div", "eyebrow", "Compatibilità"));
      const scoreDiv = el("div", `detail-score ${scoreClass(r.score)}`, fmtPct(r.score));
      scorePanel.appendChild(scoreDiv);
      if (r.gap_analysis) {
        scorePanel.appendChild(el("div", "match-gap", r.gap_analysis));
      }
      box.appendChild(scorePanel);
    }

    if (r.documents) {
      const docsPanel = el("div", "panel");
      docsPanel.appendChild(el("div", "eyebrow", "Documenti generati"));

      const labels = { cv: "CV", cover_letter: "Lettera", email: "Email" };

      ["cv", "cover_letter", "email"].forEach(docType => {
        const content = r.documents[docType];
        if (!content) return;

        const btn = el("button", "btn btn-ghost", `📄 ${labels[docType] || docType}`);
        btn.style.marginRight = "0.5rem";
        btn.addEventListener("click", () => {
          // Genera un ID temporaneo per i documenti da URL
          const tempId = `temp_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
          currentDoc = { 
            id: tempId,           
            content: content, 
            doc_type: docType,
            is_temp: true         
          };
          $("docTitle").textContent = `${labels[docType]} — ${r.listing?.title || "Annuncio"}`;
          $("docBody").textContent = content;
          $("docSheet").classList.add("is-open");
        });
        docsPanel.appendChild(btn);
      });

      box.appendChild(docsPanel);
    }

    toast("Analisi completata!", "ok");
  } catch (e) {
    toast("Errore: " + e.message, "bad");
  }
});


// ---------- Health / boot ----------
// ---------- Health / boot ----------
async function boot() {
  try {
    const h = await get("/health");
    const dot = $("railStatus").querySelector(".dot");
    dot.classList.add("ok");
    $("railStatusText").textContent = `LLM: ${h.llm_primary}`;
  } catch {
    $("railStatus").querySelector(".dot").classList.add("bad");
    $("railStatusText").textContent = "Backend non raggiungibile";
    return;
  }

  await loadSoftCatalog();
  await loadGeo();
  renderDraftSkills();
  renderDraftCompanies();

  // Se non c'è userId in localStorage, prova a recuperare gli utenti dal DB
  if (!state.userId) {
    try {
      const allUsers = await get("/users");
      if (allUsers && allUsers.length > 0) {
        state.userId = allUsers[0].id;
        localStorage.setItem("jm.userId", state.userId);
      }
    } catch (e) {
      console.warn("Impossibile recuperare la lista utenti iniziale:", e);
    }
  }

  // Caricamento profilo ed elementi collegati
  if (state.userId) {
    try {
      await loadUser();
      unlockProfilePanels();
      await refreshSessions();
      await loadPreferredCompanies();
    } catch (e) {
      console.warn("Utente salvato non valido o non trovato:", e);
      localStorage.removeItem("jm.userId");
      state.userId = null;
      
      // Fallback: riprova a prendere il primo utente dal DB se l'ID salvato non esiste più
      try {
        const allUsers = await get("/users");
        if (allUsers && allUsers.length > 0) {
          state.userId = allUsers[0].id;
          localStorage.setItem("jm.userId", state.userId);
          await loadUser();
          unlockProfilePanels();
          await refreshSessions();
          await loadPreferredCompanies();
        }
      } catch (err) {
        console.warn("Nessun utente disponibile al fallback:", err);
      }
    }
  }
}


// ================================================================
// PROFILO
// ================================================================
$("btnSaveProfile").addEventListener("click", async () => {
  const payload = {
    name: $("pfName").value.trim(),
    email: $("pfEmail").value.trim(),
    location: $("pfLocation").value.trim() || null,
    phone: $("pfPhone").value.trim() || null,
    bio: $("pfBio").value.trim() || null,
    personal_phrase: $("pfPhrase").value.trim() || null,
  };
  if (!payload.name || !payload.email) {
    toast("Nome ed email sono obbligatori", "bad");
    return;
  }
  try {
    let user;
    if (state.userId) {
      user = await patch(`/users/${state.userId}`, payload);
    } else {
      user = await post("/users", payload);
      state.userId = user.id;
    }
    localStorage.setItem("jm.userId", user.id);
    const railUserEl = $("railUser");
    if (railUserEl) railUserEl.textContent = user.name;
    
    const profileHintEl = $("profileHint");
    if (profileHintEl) {
      profileHintEl.textContent = "Salvato";
      profileHintEl.className = "hint ok";
    }

    unlockProfilePanels();
    await loadAllProfileSections();
    await refreshSessions();
    setSaveBarState("saved");
    toast("Profilo salvato", "ok");
  } catch (e) {
    toast("Errore: " + e.message, "bad");
  }
});


function unlockProfilePanels() {
  ["panelSoft", "panelLanguages", "panelHard", "panelExp", "panelEdu", "panelSessions"].forEach(id => {
    $(id).removeAttribute("data-locked");
  });
}

async function loadUser() {
  const u = await get(`/users/${state.userId}`);
  $("pfName").value = u.name || "";
  $("pfEmail").value = u.email || "";
  $("pfLocation").value = u.location || "";
  $("pfPhone").value = u.phone || "";
  $("pfBio").value = u.bio || "";
  $("railUser").textContent = u.name;
  $("pfPhrase").value = u.personal_phrase || "";
  unlockProfilePanels();
  await loadAllProfileSections();  
  setSaveBarState("saved");
}


async function loadAllProfileSections() {
  await Promise.all([
    loadSoftSkills(), 
    loadLanguages(),  
    loadHardSkills(), 
    loadExperiences(), 
    loadEducation()
  ]);
}
// ---------- Soft skill ----------
async function loadSoftCatalog() {
  state.softCatalog = await get("/skills/soft");
  renderSoftCatalog();
}

function renderSoftCatalog() {
  const box = $("softCatalog");
  box.innerHTML = "";
  state.softCatalog.forEach(s => {
    const chip = el("button", "chip", s.name);
    chip.type = "button";
    if (state.softSelected.has(s.name)) chip.classList.add("is-on");
    chip.addEventListener("click", () => toggleSoftSkill(s.name, chip));
    box.appendChild(chip);
  });
}

async function toggleSoftSkill(name, chipEl) {
  if (!state.userId) { toast("Salva prima il profilo", "bad"); return; }
  const isOn = state.softSelected.has(name);
  try {
    if (isOn) {
      const list = await get(`/users/${state.userId}/soft-skills`);
      const found = list.find(x => x.name === name);
      if (found) await del(`/users/${state.userId}/soft-skills/${found.id}`);
      state.softSelected.delete(name);
      chipEl.classList.remove("is-on");
    } else {
      await post(`/users/${state.userId}/soft-skills`, { name });
      state.softSelected.add(name);
      chipEl.classList.add("is-on");
    }
    showSimilarSoftSkills(name);
  } catch (e) {
     toast(e.message, "bad"); }
}


async function showSimilarSoftSkills(skillName) {
  const box = $("softSimilarBox");
  const chips = $("softSimilarChips");
  if (!box || !chips) return;

  try {
    const simili = await get(`/skills/soft/${encodeURIComponent(skillName)}/similar?limit=5`);
    if (!simili || !simili.length) {
      box.classList.add("hidden");
      return;
    }

    $("softSimilarName").textContent = skillName;
    chips.innerHTML = "";

    simili.forEach(s => {
      const chip = el("button", "chip", s.name);
      chip.type = "button";
      chip.title = s.reason || "";
      chip.addEventListener("click", () => toggleSoftSkill(s.name, chip));
      chips.appendChild(chip);
    });

    box.classList.remove("hidden");
  } catch (e) {
    console.warn("Simili soft skill non disponibili:", e);
    box.classList.add("hidden");
  }
}


async function loadSoftSkills() {
  const list = await get(`/users/${state.userId}/soft-skills`);
  state.softSelected = new Set(list.map(s => s.name));
  renderSoftCatalog();
}
// ---------- Lingue conosciute ----------
$("btnAddLang").addEventListener("click", async () => {
  const language = $("langName").value;
  const level = $("langLevel").value;
  
  if (!language) { toast("Seleziona una lingua", "bad"); return; }
  if (!state.userId) { toast("Salva prima il profilo", "bad"); return; }
  
  try {
    await post(`/users/${state.userId}/languages`, {
      language: language,
      level: level,
      is_native: level === "madrelingua",
    });
    await loadLanguages();
    toast("Lingua aggiunta", "ok");
  } catch (e) {
    toast(e.message, "bad");
  }
});

async function loadLanguages() {
  if (!state.userId) return;
  
  try {
    const list = await get(`/users/${state.userId}/languages`);
    const ul = $("langList");
    ul.innerHTML = "";
    
    if (!list.length) {
      ul.innerHTML = '<li class="stack-empty">Nessuna lingua aggiunta</li>';
      return;
    }
    
    const langLabels = {
      "italian": "🇮🇹 Italiano",
      "english": "🇬🇧 Inglese",
      "german": "🇩🇪 Tedesco",
      "french": "🇫🇷 Francese",
      "spanish": "🇪🇸 Spagnolo",
      "portuguese": "🇵🇹 Portoghese",
      "dutch": "🇳🇱 Olandese",
    };
    
    const levelLabels = {
      "madrelingua": "Madrelingua",
      "A1": "A1 - Base",
      "A2": "A2 - Elementare",
      "B1": "B1 - Intermedio",
      "B2": "B2 - Intermedio-alto",
      "C1": "C1 - Avanzato",
      "C2": "C2 - Padronanza",
    };
    
    list.forEach(lang => {
      const li = el("li");
      const main = el("div", "stack-main");
      main.appendChild(el("div", "stack-title", 
        langLabels[lang.language] || lang.language));
      main.appendChild(el("div", "stack-sub", 
        levelLabels[lang.level] || lang.level));
      
      const btn = el("button", "btn btn-danger", "Rimuovi");
      btn.addEventListener("click", async () => {
        await del(`/users/${state.userId}/languages/${lang.id}`);
        loadLanguages();
      });
      
      li.appendChild(main);
      li.appendChild(btn);
      ul.appendChild(li);
    });
  } catch (e) {
    console.warn("Errore caricamento lingue:", e);
  }
}

// ---------- Hard skill ----------
$("btnAddHard").addEventListener("click", async () => {
  const name = $("hsName").value.trim();
  if (!name) return;
  try {
    await post(`/users/${state.userId}/hard-skills`, {
      name,
      level: $("hsLevel").value,
      years_exp: parseInt($("hsYears").value || 0, 10),
      acquired_via: $("hsVia").value,
    });
    $("hsName").value = "";
    await loadHardSkills();
  } catch (e) { toast(e.message, "bad"); }
});

async function loadHardSkills() {
  const list = await get(`/users/${state.userId}/hard-skills`);
  const ul = $("hardList");
  ul.innerHTML = "";
  if (!list.length) {
    ul.innerHTML = '<li class="stack-empty">Nessuna competenza ancora</li>';
    return;
  }
  list.forEach(s => {
    const li = el("li");
    const main = el("div", "stack-main");
    main.appendChild(el("div", "stack-title", s.name));
    main.appendChild(el("div", "stack-sub",
      `${s.level} · ${s.years_exp} anni · ${s.acquired_via || "n/d"}`));
    const btn = el("button", "btn btn-danger", "Rimuovi");
    btn.addEventListener("click", async () => {
      await del(`/users/${state.userId}/hard-skills/${s.id}`);
      loadHardSkills();
    });
    li.appendChild(main); li.appendChild(btn);
    ul.appendChild(li);
  });
}

// ---------- Esperienze ----------
$("btnAddExp").addEventListener("click", async () => {
  const payload = {
    company: $("exCompany").value.trim(),
    role: $("exRole").value.trim(),
    start_date: $("exStart").value.trim() || null,
    end_date: $("exEnd").value.trim() || null,
    description: $("exDesc").value.trim() || null,
    skills_used: $("exSkills").value.trim() || null,
  };
  if (!payload.company || !payload.role) { toast("Azienda e ruolo richiesti", "bad"); return; }
  try {
    await post(`/users/${state.userId}/experiences`, payload);
    ["exCompany","exRole","exStart","exEnd","exDesc","exSkills"].forEach(id => $(id).value = "");
    loadExperiences();
  } catch (e) { toast(e.message, "bad"); }
});

async function loadExperiences() {
  const list = await get(`/users/${state.userId}/experiences`);
  const ul = $("expList");
  ul.innerHTML = "";
  if (!list.length) { ul.innerHTML = '<li class="stack-empty">Nessuna esperienza ancora</li>'; return; }
  list.forEach(e => {
    const li = el("li");
    const main = el("div", "stack-main");
    main.appendChild(el("div", "stack-title", `${e.role} — ${e.company}`));
    const sub = `${e.start_date || "?"} – ${e.end_date || "in corso"}${e.description ? " · " + e.description : ""}`;
    main.appendChild(el("div", "stack-sub", sub));
    const btn = el("button", "btn btn-danger", "Rimuovi");
    btn.addEventListener("click", async () => {
      await del(`/users/${state.userId}/experiences/${e.id}`);
      loadExperiences();
    });
    li.appendChild(main); li.appendChild(btn);
    ul.appendChild(li);
  });
}

// ---------- Formazione ----------
$("btnAddEdu").addEventListener("click", async () => {
  const payload = {
    institution: $("edInst").value.trim(),
    degree: $("edDeg").value.trim() || null,
    field: $("edField").value.trim() || null,
    year: $("edYear").value.trim() || null,
  };
  if (!payload.institution) { toast("Istituto richiesto", "bad"); return; }
  try {
    await post(`/users/${state.userId}/education`, payload);
    ["edInst","edDeg","edField","edYear"].forEach(id => $(id).value = "");
    loadEducation();
  } catch (e) { toast(e.message, "bad"); }
});

async function loadEducation() {
  const list = await get(`/users/${state.userId}/education`);
  const ul = $("eduList");
  ul.innerHTML = "";
  if (!list.length) { ul.innerHTML = '<li class="stack-empty">Nessun titolo ancora</li>'; return; }
  list.forEach(e => {
    const li = el("li");
    const main = el("div", "stack-main");
    main.appendChild(el("div", "stack-title", `${e.degree || "Titolo"} in ${e.field || "—"}`));
    main.appendChild(el("div", "stack-sub", `${e.institution} · ${e.year || ""}`));
    const btn = el("button", "btn btn-danger", "Rimuovi");
    btn.addEventListener("click", async () => {
      await del(`/users/${state.userId}/education/${e.id}`);
      loadEducation();
    });
    li.appendChild(main); li.appendChild(btn);
    ul.appendChild(li);
  });
}

// ================================================================
// IMPORT CV — upload PDF, pre-compilazione con conferma dell'utente
// ================================================================
let cvExtracted = null; // ultimo risultato di /cv/parse in attesa di conferma

$("btnUploadCV").addEventListener("click", () => {
  if (!state.userId) { toast("Salva prima il profilo", "bad"); return; }
  $("cvFileInput").click();
});

$("cvFileInput").addEventListener("change", async () => {
  const file = $("cvFileInput").files[0];
  $("cvFileInput").value = ""; // permette di ricaricare lo stesso file una seconda volta
  if (!file) return;
  if (file.type !== "application/pdf" && !file.name.toLowerCase().endsWith(".pdf")) {
    toast("Carica un file PDF", "bad");
    return;
  }

  toast("Sto leggendo il CV...", "");
  const form = new FormData();
  form.append("file", file);

  try {
    const r = await fetch(`${API}/users/${state.userId}/cv/parse`, { 
      method: "POST", 
      headers: {
        "X-API-Token": "local-dev-token-2026",  
      },
      body: form 
    });
    if (!r.ok) {
      let msg = `${r.status} ${r.statusText}`;
      try { const j = await r.json(); if (j.detail) msg = j.detail; } catch {}
      throw new Error(msg);
    }
    cvExtracted = await r.json();
    await openCvReview();
  } catch (e) {
    toast("Errore: " + e.message, "bad");
  }
});

function buildCheckRow({ checked, label, value, current, type, payload }) {
  const row = el("label", "cv-check-row");
  const cb = document.createElement("input");
  cb.type = "checkbox";
  cb.checked = checked;
  cb.dataset.type = type;
  cb.dataset.payload = JSON.stringify(payload);
  row.appendChild(cb);

  const main = el("div", "cv-check-main");
  main.appendChild(el("span", "cv-check-label", label));
  
  // Per le lingue e le skill, rendi il valore modificabile
  if (type === "language" || type === "hard_skill" || type === "soft_skill") {
    const input = document.createElement("input");
    input.type = "text";
    input.value = value || "";
    input.className = "cv-check-input";
    input.addEventListener("input", (e) => {
      payload.name = e.target.value;  // Aggiorna il payload
      cb.dataset.payload = JSON.stringify(payload);
    });
    main.appendChild(input);
  } else {
    if (value) main.appendChild(el("span", "cv-check-value", value));
  }
  
  if (current) main.appendChild(el("span", "cv-check-current", `Attuale: ${current}`));
  row.appendChild(main);
  return row;
}

function appendListSection(body, title, items, rowBuilder) {
  if (!items.length) return;
  const sec = el("div", "cv-section");
  sec.appendChild(el("h4", "", `${title} (${items.length} nuove)`));
  items.forEach(item => sec.appendChild(rowBuilder(item)));
  body.appendChild(sec);
}

async function openCvReview() {
  const [curHard, curSoft, curExp, curEdu, curLangs] = await Promise.all([
    get(`/users/${state.userId}/hard-skills`),
    get(`/users/${state.userId}/soft-skills`),
    get(`/users/${state.userId}/experiences`),
    get(`/users/${state.userId}/education`),
    get(`/users/${state.userId}/languages`),  // ← AGGIUNTO: lingue esistenti
  ]);

  const body = $("cvReviewBody");
  body.innerHTML = "";
  const p = cvExtracted.profile;

  // ---- Anagrafica (come prima) ----
  const fieldMap = [
    ["name", "Nome e cognome", $("pfName").value],
    ["phone", "Telefono", $("pfPhone").value],
    ["location", "Dove vivi", $("pfLocation").value],
    ["bio", "Chi sei professionalmente", $("pfBio").value],
  ];
  const norm = (s) => (s || "").trim().toLowerCase().replace(/\s+/g, " ");
    const fieldRows = fieldMap.filter(([key, , current]) => {
    const extracted = (p[key] || "").trim();
    return extracted && norm(extracted) !== norm(current);
});

  if (fieldRows.length) {
    const sec = el("div", "cv-section");
    sec.appendChild(el("h4", "", "Anagrafica"));
    fieldRows.forEach(([key, label, current]) => {
      sec.appendChild(buildCheckRow({
        checked: !current,
        label,
        value: p[key],
        current: current || null,
        type: "field",
        payload: { key, value: p[key] },
      }));
    });
    body.appendChild(sec);
  }

  // ---- Hard skill non già presenti ----
  const curHardNames = new Set(curHard.map(s => s.name.toLowerCase()));
  const newHard = (p.hard_skills || []).filter(s => !curHardNames.has(s.toLowerCase()));
  appendListSection(body, "Competenze tecniche", newHard, (name) => buildCheckRow({
    checked: true, label: name, type: "hard_skill",
    payload: { name, level: "intermediate", years_exp: 0, acquired_via: null },
  }));

  // ---- Soft skill non già presenti ----
  const curSoftNames = new Set(curSoft.map(s => s.name.toLowerCase()));
  const newSoft = (p.soft_skills || []).filter(s => !curSoftNames.has(s.toLowerCase()));
  appendListSection(body, "Soft skill", newSoft, (name) => buildCheckRow({
    checked: true, label: name, type: "soft_skill", payload: { name },
  }));

  // ---- Lingue non già presenti (NUOVO) ----
  const curLangNames = new Set(
    curLangs.map(l => (l.language || "").toLowerCase())
  );
  const newLangs = (p.languages || []).filter(l => {
    const langName = (l.language || "").toLowerCase();
    return langName && !curLangNames.has(langName);
  });
  
  appendListSection(body, "Lingue", newLangs, (lang) => {
    // Normalizza il formato della lingua
    const langPayload = {
      language: (lang.language || "").toLowerCase(),
      level: lang.level || "B1",
      is_native: (lang.level || "").toLowerCase() === "madrelingua",
    };
    
    return buildCheckRow({
      checked: true,
      label: `${lang.language} - ${lang.level || "non specificato"}`,
      type: "language",
      payload: langPayload,
    });
  });

  // ---- Esperienze non già presenti ----
  const curExpKeys = new Set(curExp.map(e => `${(e.company || "").toLowerCase()}|${(e.role || "").toLowerCase()}`));
  const newExp = (p.experiences || []).filter(e =>
    e.company && e.role && !curExpKeys.has(`${e.company.toLowerCase()}|${e.role.toLowerCase()}`)
  );
  appendListSection(body, "Esperienze", newExp, (e) => buildCheckRow({
    checked: true,
    label: `${e.role} — ${e.company}`,
    value: `${e.start_date || "?"} – ${e.end_date || "in corso"}${e.description ? " · " + e.description : ""}`,
    type: "experience", payload: e,
  }));

  // ---- Formazione non già presente ----
  const curEduKeys = new Set(curEdu.map(e => `${(e.institution || "").toLowerCase()}|${(e.degree || "").toLowerCase()}`));
  const newEdu = (p.education || []).filter(e =>
    e.institution && !curEduKeys.has(`${e.institution.toLowerCase()}|${(e.degree || "").toLowerCase()}`)
  );
  appendListSection(body, "Formazione", newEdu, (e) => buildCheckRow({
    checked: true,
    label: `${e.degree || "Titolo"} in ${e.field || "—"}`,
    value: `${e.institution} · ${e.year || ""}`,
    type: "education", payload: e,
  }));

  // ---- Controllo se non c'è nulla di nuovo ----
  if (!fieldRows.length && !newHard.length && !newSoft.length && 
      !newLangs.length && !newExp.length && !newEdu.length) {
    body.appendChild(el("div", "cv-empty",
      "Non ho trovato dati nuovi da aggiungere: quello che ho letto dal CV coincide già con il tuo profilo."));
  }

  // ---- Critica del CV ----
  if (cvExtracted.critique) {
    const sec = el("div", "cv-section cv-critique");
    sec.appendChild(el("h4", "", "Critica del CV (solo informativa)"));
    const txt = el("div", "cv-critique-text", cvExtracted.critique);
    sec.appendChild(txt);
    body.appendChild(sec);
  }

  $("cvApplyHint").textContent = "";
  $("cvSheet").classList.add("is-open");
}

$("btnCloseCv").addEventListener("click", () => $("cvSheet").classList.remove("is-open"));
$("cvSheet").addEventListener("click", (e) => {
  if (e.target.id === "cvSheet") $("cvSheet").classList.remove("is-open");
});

$("btnApplyCv").addEventListener("click", async () => {
  const checked = Array.from($("cvReviewBody").querySelectorAll('input[type="checkbox"]:checked'));
  if (!checked.length) { toast("Nessun elemento selezionato", "bad"); return; }

  $("btnApplyCv").disabled = true;
  $("cvApplyHint").textContent = "Applico le modifiche...";

  const fieldUpdates = {};
  const tasks = [];

  checked.forEach(cb => {
    const payload = JSON.parse(cb.dataset.payload);
    if (cb.dataset.type === "field") {
      fieldUpdates[payload.key] = payload.value;
    } else if (cb.dataset.type === "hard_skill") {
      tasks.push(post(`/users/${state.userId}/hard-skills`, payload));
    } else if (cb.dataset.type === "soft_skill") {
      tasks.push(post(`/users/${state.userId}/soft-skills`, payload));
    } else if (cb.dataset.type === "language") {  
      tasks.push(post(`/users/${state.userId}/languages`, payload));
    } else if (cb.dataset.type === "experience") {
      tasks.push(post(`/users/${state.userId}/experiences`, payload));
    } else if (cb.dataset.type === "education") {
      tasks.push(post(`/users/${state.userId}/education`, payload));
    }
  });

  if (Object.keys(fieldUpdates).length) {
    tasks.push(patch(`/users/${state.userId}`, fieldUpdates));
  }

  const results = await Promise.allSettled(tasks);
  const failures = results.filter(r => r.status === "rejected").length;

  $("btnApplyCv").disabled = false;
  $("cvSheet").classList.remove("is-open");
  cvExtracted = null;

  await loadUser();

  if (failures) {
    toast(`Applicato con ${failures} errori su ${checked.length} — controlla il profilo`, "bad");
  } else {
    toast(`${checked.length} elementi applicati al profilo`, "ok");
  }
}); 

// ================================================================
// SESSIONI
// ================================================================



attachAutocomplete($("ssRole"), $("ssRoleSuggest"), ROLE_CATALOG);

$("ssThreshold").addEventListener("input", (e) => {
  $("ssThresholdOut").textContent = e.target.value + "%";
});

$("btnCreateSession").addEventListener("click", async () => {
  if (!state.userId) { toast("Crea prima il profilo", "bad"); return; }
  const role = $("ssRole").value.trim();
  if (!role) { toast("Indica il ruolo che cerchi", "bad"); return; }
  const country = $("ssCountry").value || null;
  const zone = $("ssLocation").value || null;
  const isContinent = !!geoTree?.continents.some(c => c.code === country);
  const payload = {
    role_title: role,
    preferred_country: country,
    location_pref: zone,
    // forma strutturata accanto a quella storica: preferred_country e
    // location_pref restano perche' sono cio' che la costruzione degli URL
    // dei portali legge, e le ricerche gia' salvate le usano
    geo_scope: !country ? null : (isContinent ? "continent" : (zone ? "region" : "country")),
    geo_country: country && !isContinent ? country : null,
    geo_region: zone || null,
    contract_type: $("ssContract").value || null,
    match_threshold: parseInt($("ssThreshold").value, 10) / 100,
  };
  // le aziende d'interesse rimaste spuntate si uniscono a quelle scelte
  // qui sopra, deduplicate per nome
  const scelte = [...state.draftCompanies];
  const gia = new Set(scelte.map(c => c.name.toLowerCase().trim()));
  Array.from(
    $("preferredCompaniesChecklist").querySelectorAll('input[type="checkbox"]:checked')
  ).forEach(cb => {
    const c = state.preferredCompanies.find(pc => pc.id === cb.dataset.companyId);
    if (!c) return;
    const k = c.name.toLowerCase().trim();
    if (gia.has(k)) return;
    gia.add(k);
    scelte.push({
      name: c.name, country: c.country, size: c.size, sector: c.sector,
      website: c.website, source: c.source || "manual",
    });
  });

  payload.hard_skills = state.draftSkills.map(x => x.name);
  payload.companies = scelte;

  const btnC = $("btnCreateSession");
  btnC.disabled = true;
  try {
    // Un solo POST: competenze e aziende viaggiano con la ricerca. Prima
    // erano N chiamate in sequenza DOPO la creazione, ognuna delle quali
    // poteva fallire lasciando la ricerca a meta'.
    const s = await post(`/users/${state.userId}/sessions`, payload);

    $("ssRole").value = "";
    state.draftSkills = [];
    state.draftCompanies = [];
    state.suggestedRoleSkills = [];
    $("skillSuggestions").innerHTML = "";
    $("companyResults").innerHTML = "";
    $("similarBlock").classList.add("hidden");
    renderDraftSkills();
    renderDraftCompanies();

    await refreshSessions();
    await loadPreferredCompanies();
    await selectSession(s.id);
    toast(`Ricerca creata: ${payload.hard_skills.length} competenze, ${scelte.length} aziende`, "ok");
  } catch (e) {
    toast(e.message, "bad");
  } finally {
    btnC.disabled = false;
  }
});

// Ricerche concluse (in un modo o nell'altro) portano al Resoconto; quelle
// non ancora concluse portano alla configurazione — stesso gesto (click
// sulla card), destinazione diversa a seconda dello stato.
const REPORT_STATUSES = new Set(["completed", "error", "cancelled"]);

async function refreshSessions() {
  const sessions = await get(`/users/${state.userId}/sessions`);
  const box = $("sessionList");
  box.innerHTML = "";
  if (!sessions.length) {
    box.innerHTML = '<div class="stack-empty">Nessuna ricerca ancora. Creane una qui sopra.</div>';
    return;
  }
  sessions.forEach(s => {
    const card = el("div", "session-card");
    if (s.id === state.sessionId) card.classList.add("is-on");
    card.addEventListener("click", async () => {
      if (REPORT_STATUSES.has(s.status)) {
        await openSessionReport(s.id);
      } else {
        await selectSession(s.id);
        switchView("sessions");
      }
    });

    card.appendChild(el("div", "session-role", s.role_title));
    const badge = el("span", `badge badge-${s.status}`, s.status);
    if (s.status === "running") {
      const spinner = el("span", "run-spinner is-active badge-spinner");
      badge.prepend(spinner);
    }
    const meta = el("div", "session-meta");
    if (s.preferred_country) meta.appendChild(el("span", "", s.preferred_country));
    if (s.location_pref) meta.appendChild(el("span", "", s.location_pref));
    meta.appendChild(badge);
    card.appendChild(meta);

    box.appendChild(card);
  });
}

async function openSessionReport(id) {
  state.sessionId = id;
  localStorage.setItem("jm.sessionId", id);
  switchView("intelligence");
  await refreshIntelligence(); // esplicito, non ci si affida solo al guard interno di switchView
}

async function selectSession(id) {
  state.sessionId = id;
  localStorage.setItem("jm.sessionId", id);
  document.querySelectorAll(".session-card").forEach(c => c.classList.remove("is-on"));

  const s = await get(`/users/${state.userId}/sessions/${id}`);
  $("cfgTag").textContent = `Ricerca · ${s.role_title}`;
  $("sessionConfig").classList.remove("hidden");

  await Promise.all([loadWorkspaceCompanies(), loadWorkspaceDocs()]);
  await refreshResultsView();
  refreshSessions();
  $("sessionConfig").scrollIntoView({ behavior: "smooth", block: "start" });
}

// ---------- Workspace della ricerca aperta ----------
// E2: definizione, avanzamento ed esiti di una ricerca vivono nella stessa
// schermata. Erano due view separate, ma una ricerca e' una cosa sola.
const ESITO = {
  found: "annunci trovati",
  no_openings: "nessuna posizione aperta",
  unreachable: "pagina carriere non raggiungibile",
};

async function loadWorkspaceCompanies() {
  const list = await get(`/users/${state.userId}/sessions/${state.sessionId}/companies`);
  const ul = $("wsCompanies");
  ul.innerHTML = "";
  if (!list.length) {
    ul.innerHTML = '<li class="stack-empty">Nessuna azienda in questa ricerca: girerà solo sui portali.</li>';
    return;
  }
  list.forEach(c => {
    const li = el("li");
    const main = el("div", "stack-main");
    main.appendChild(el("div", "stack-title", c.name));
    const quando = c.last_searched_at
      ? new Date(c.last_searched_at).toLocaleString("it-IT",
          { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" })
      : null;
    const parti = [ESITO[c.last_result] || "mai cercata"];
    if (c.last_postings_count != null) parti.push(`${c.last_postings_count} annunci`);
    if (quando) parti.push(`ultima ricerca ${quando}`);
    main.appendChild(el("div", "stack-sub", parti.join(" · ")));
    li.appendChild(main);
    ul.appendChild(li);
  });
}

async function loadWorkspaceDocs() {
  const box = $("wsBaseDocs");
  box.innerHTML = "";
  let docs = [];
  try { docs = await get(`/users/${state.userId}/base-documents`); } catch { /* nessuno */ }
  const cv = docs.find(d => d.doc_type === "cv");
  if (!cv) {
    box.innerHTML = '<div class="stack-empty">Nessun CV base. Caricane uno dal Profilo: le versioni per ogni azienda verranno adattate da quello invece che riscritte da zero.</div>';
    return;
  }
  const riga = el("div", "stack-main");
  riga.appendChild(el("div", "stack-title", "CV base"));
  riga.appendChild(el("div", "stack-sub",
    `${(cv.content || "").length.toLocaleString("it-IT")} caratteri · origine ${cv.source} · aggiornato ${new Date(cv.updated_at).toLocaleDateString("it-IT")}`));
  box.appendChild(riga);
}

// ---------- Aziende preferite del profilo — checklist compatta nel form
// "Nuova ricerca" (non più un pannello espanso dentro la configurazione
// sessione). Caricate al boot(), non solo quando si seleziona una sessione,
// così il conteggio è corretto anche la primissima volta che si vede il form. ----------
async function loadPreferredCompanies() {
  state.preferredCompanies = await get(`/users/${state.userId}/preferred-companies`);
  renderPreferredCompaniesChecklist();
}

function renderPreferredCompaniesChecklist() {
  const wrap = $("preferredCompaniesFieldWrap");
  const summary = $("preferredCompaniesSummary");
  const box = $("preferredCompaniesChecklist");

  if (!state.preferredCompanies.length) {
    wrap.classList.add("hidden");
    return;
  }
  wrap.classList.remove("hidden");
  summary.textContent = `Aziende d'interesse (${state.preferredCompanies.length})`;

  box.innerHTML = "";
  state.preferredCompanies.forEach(c => {
    const row = el("div", "preferred-check-row");
    const cbId = `prefCo_${c.id}`;

    const cb = document.createElement("input");
    cb.type = "checkbox";
    cb.id = cbId;
    cb.checked = true; // pre-selezionate: l'utente deseleziona quelle che non vuole
    cb.dataset.companyId = c.id;
    row.appendChild(cb);

    const label = document.createElement("label");
    label.htmlFor = cbId;
    label.className = "preferred-check-name";
    label.textContent = c.name;
    row.appendChild(label);

    // "×" = smetti di seguire del tutto (cancella dal profilo) — distinto
    // dal deselezionare la checkbox, che significa solo "non per questa
    // ricerca" e non tocca l'elenco salvato
    const rm = el("button", "btn btn-micro", "×");
    rm.type = "button";
    rm.title = "Smetti di seguire questa azienda";
    rm.addEventListener("click", async () => {
      await del(`/users/${state.userId}/preferred-companies/${c.id}`);
      await loadPreferredCompanies();
    });
    row.appendChild(rm);

    box.appendChild(row);
  });
}

// ---------- Suggerimento skill del ruolo (RF2.1) ----------
$("btnSuggestSkills").addEventListener("click", async () => {
  if (!state.sessionId) return;
  const s = await get(`/users/${state.userId}/sessions/${state.sessionId}`);
  $("skillHint").textContent = "Sto chiedendo all'AI le competenze tipiche del ruolo...";
  $("skillHint").className = "hint";
  try {
    const sugg = await get(`/skills/suggest?role=${encodeURIComponent(s.role_title)}`);
    state.suggestedRoleSkills = sugg;
    renderSkillSuggestions();
    $("skillHint").textContent = `${sugg.length} competenze suggerite. Clicca quelle che vuoi richiedere.`;
  } catch (e) {
    $("skillHint").textContent = "Non riesco a raggiungere l'AI. Aggiungi le competenze manualmente."; 
    $("skillHint").className = "hint bad";
  }
});

async function renderSkillSuggestions() {
  const existingNames = new Set(state.draftSkills.map(x => x.name.toLowerCase()));

  const box = $("skillSuggestions");
  box.innerHTML = "";
  state.suggestedRoleSkills.forEach(sug => {
    const chip = el("button", "chip", sug.name);
    chip.type = "button";
    if (existingNames.has(sug.name.toLowerCase())) chip.classList.add("is-on");
    if (sug.importance) chip.appendChild(el("span", "chip-meta", sug.importance.slice(0, 3)));
    chip.addEventListener("click", async () => {
      const k = sug.name.toLowerCase();
      if (chip.classList.contains("is-on")) {
        state.draftSkills = state.draftSkills.filter(x => x.name.toLowerCase() !== k);
        chip.classList.remove("is-on");
      } else {
        state.draftSkills.push({
          name: sug.name, category: sug.category,
          required: sug.importance !== "nice_to_have",
        });
        chip.classList.add("is-on");
        // selezionarla la salva anche tra le competenze personali: e' un
        // effetto secondario utile e non deve poter far fallire l'azione
        // principale. Deselezionarla NON la rimuove dal profilo: "non
        // richiesta per questo ruolo" non vuol dire "non la possiedo".
        try {
          await post(`/users/${state.userId}/hard-skills`, {
            name: sug.name, category: sug.category, level: "beginner",
            years_exp: 0, acquired_via: null,
          });
        } catch (e) { console.warn("Salvataggio skill nel profilo fallito:", e); }
      }
      renderDraftSkills();
    });
    box.appendChild(chip);
  });
}

function renderDraftSkills() {
  const ul = $("sessionSkillList");
  ul.innerHTML = "";
  if (!state.draftSkills.length) {
    ul.innerHTML = '<li class="stack-empty">Nessuna competenza richiesta impostata</li>';
    return;
  }
  state.draftSkills.forEach(sk => {
    const li = el("li");
    const main = el("div", "stack-main");
    main.appendChild(el("div", "stack-title", sk.name));
    main.appendChild(el("div", "stack-sub", sk.required ? "obbligatoria" : "preferibile"));
    const btn = el("button", "btn btn-danger", "Rimuovi");
    btn.addEventListener("click", () => {
      state.draftSkills = state.draftSkills.filter(x => x.name !== sk.name);
      renderDraftSkills();
      renderSkillSuggestions();
    });
    li.appendChild(main); li.appendChild(btn);
    ul.appendChild(li);
  });
}

// ---------- Ricerca aziende (RF2.2) ----------
$("btnSearchCompany").addEventListener("click", async () => {
  const q = $("coQuery").value.trim();
  if (!q) return;
  const results = await post(`/users/${state.userId}/companies/search`, {
    query: q, location: $("ssLocation").value || null, sector: null, limit: 8,
  });
  state.currentCompanySuggestions = results;
  renderCompanyResults();
});

$("btnSearchLocal").addEventListener("click", async () => {
  const sector = $("coSector").value.trim();
  const area = $("coArea").value.trim();
  if (!sector || !area) { toast("Serve settore e zona", "bad"); return; }
  const results = await post(`/users/${state.userId}/companies/search-local`, {
    sector, area, limit: 10,
  });
  state.currentCompanySuggestions = results;
  renderCompanyResults();
});

function renderCompanyResults() {
  const box = $("companyResults");
  box.innerHTML = "";
  const already = new Set(state.targetCompanies.map(c => c.name.toLowerCase()));

  state.currentCompanySuggestions.forEach(c => {
    const card = el("div", "co-card");
    if (!c.exists_online) card.classList.add("is-ghost");
    card.appendChild(el("div", "co-name", c.name));
    if (c.country || c.sector) {
      card.appendChild(el("div", "co-sub", [c.sector, c.country].filter(Boolean).join(" · ")));
    }
    const tags = el("div", "co-tags");
    if (c.size) tags.appendChild(el("span", "tag", c.size));
    if (c.source) tags.appendChild(el("span", "tag", c.source));
    if (!c.exists_online) tags.appendChild(el("span", "tag", "non verificata"));
    card.appendChild(tags);

    if (already.has(c.name.toLowerCase())) {
      card.appendChild(el("span", "hint ok", "già aggiunta"));
    } else {
      const btn = el("button", "btn btn-ghost", "Aggiungi");
      btn.addEventListener("click", () => addTargetCompany(c));
      card.appendChild(btn);
    }
    box.appendChild(card);
  });
}

// ---------- Aziende target + effetto Spotify (RF2.3) ----------
function addTargetCompany(c) {
  const k = (c.name || "").toLowerCase().trim();
  if (!k || state.draftCompanies.some(x => x.name.toLowerCase().trim() === k)) return;
  state.draftCompanies.push({
    name: c.name, country: c.country, size: c.size, sector: c.sector,
    website: c.website, source: c.source || "manual",
  });
  renderDraftCompanies();
  renderCompanyResults();
  refreshSimilar();  // effetto Spotify: la lista cumulativa affina i suggerimenti
}

function renderDraftCompanies() {
  // `targetCompanies` resta il nome usato dal resto del file per "le
  // aziende scelte adesso": qui punta alla bozza
  state.targetCompanies = state.draftCompanies;
  const ul = $("targetList");
  ul.innerHTML = "";
  if (!state.draftCompanies.length) {
    ul.innerHTML = '<li class="stack-empty">Nessuna azienda selezionata (opzionale — la ricerca funziona anche solo sui portali)</li>';
    $("similarBlock").classList.add("hidden");
    return;
  }
  state.draftCompanies.forEach(c => {
    const li = el("li");
    const main = el("div", "stack-main");
    main.appendChild(el("div", "stack-title", c.name));
    main.appendChild(el("div", "stack-sub",
      [c.sector, c.country, c.source].filter(Boolean).join(" · ")));
    const btn = el("button", "btn btn-danger", "Rimuovi");
    btn.addEventListener("click", () => {
      state.draftCompanies = state.draftCompanies.filter(x => x.name !== c.name);
      renderDraftCompanies();
      renderCompanyResults();
    });
    li.appendChild(main); li.appendChild(btn);
    ul.appendChild(li);
  });
}

$("btnRefreshSimilar").addEventListener("click", refreshSimilar);

async function refreshSimilar() {
  if (!state.targetCompanies.length) {
    $("similarBlock").classList.add("hidden");
    return;
  }
  try {
    const similar = await post(`/users/${state.userId}/companies/similar`, {
      selected_companies: state.targetCompanies.map(c => c.name),
      location: $("ssLocation").value || null, sector: null, limit: 5,
    });
    $("similarBlock").classList.remove("hidden");
    const box = $("similarResults");
    box.innerHTML = "";
    const already = new Set(state.targetCompanies.map(c => c.name.toLowerCase()));

    similar.forEach(c => {
      if (already.has(c.name.toLowerCase())) return;
      const card = el("div", "co-card");
      if (!c.exists_online) card.classList.add("is-ghost");
      card.appendChild(el("div", "co-name", c.name));
      if (c.reason) card.appendChild(el("div", "co-sub", c.reason));
      const tags = el("div", "co-tags");
      if (c.sector) tags.appendChild(el("span", "tag", c.sector));
      if (c.size) tags.appendChild(el("span", "tag", c.size));
      card.appendChild(tags);
      const btn = el("button", "btn btn-ghost", "Aggiungi");
      btn.addEventListener("click", () => addTargetCompany(c));
      card.appendChild(btn);
      box.appendChild(card);
    });

    if (!box.children.length) {
      box.innerHTML = '<div class="stack-empty">Nessun ulteriore suggerimento — l\'AI non trova altre aziende simili distinte da quelle già scelte.</div>';
    }
  } catch (e) {
    console.warn(e);
    $("similarBlock").classList.add("hidden");
  }
}

// ---------- Avvia ricerca ----------
$("btnRunSearch").addEventListener("click", async () => {
  if (!state.sessionId) return;
  try {
    await post(`/users/${state.userId}/sessions/${state.sessionId}/run`, {});
    startPolling();
    $("runPanel").scrollIntoView({ behavior: "smooth", block: "center" });
    toast("Ricerca avviata — segui il log qui sotto", "ok");
  } catch (e) { toast(e.message, "bad"); }
});

// ================================================================
// RISULTATI + polling
// ================================================================
function stopPolling() {
  if (state.pollTimer) clearInterval(state.pollTimer);
  state.pollTimer = null;
}

function startPolling() {
  stopPolling();
  refreshResultsView();
  state.pollTimer = setInterval(async () => {
    if (!state.sessionId) { stopPolling(); return; }
    const s = await get(`/users/${state.userId}/sessions/${state.sessionId}/status`);
    updateRunBar(s);
    await refreshLogs();
    await refreshResultsList();
    if (s.status === "completed" || s.status === "error" || s.status === "cancelled") {
      stopPolling();
      refreshSessions();
    }
  }, 2500);
}

async function refreshResultsView() {
  if (!state.sessionId) return;
  const s = await get(`/users/${state.userId}/sessions/${state.sessionId}/status`);
  updateRunBar(s);
  await refreshLogs();
  await refreshResultsList();
  if (s.status === "running") startPolling();
}

function updateRunBar(s) {
  const map = { draft: "In attesa", running: "In esecuzione", completed: "Completata", error: "Errore", cancelled: "Annullata" };
  $("runState").textContent = map[s.status] || s.status;
  $("runMsg").textContent = s.progress_message || "—";
  $("runCount").textContent = `${s.matches_found} match`;
  const pct = s.progress_total > 0 ? (s.progress_current / s.progress_total) * 100 : (s.status === "completed" ? 100 : 0);
  $("progressFill").style.width = pct + "%";
  $("progressFill").classList.toggle("is-running", s.status === "running");
  $("runSpinner").classList.toggle("is-active", s.status === "running");
  $("btnCancelSearch").classList.toggle("hidden", s.status !== "running");
  $("btnCancelSearch").disabled = false;
}

$("btnCancelSearch").addEventListener("click", async () => {
  if (!state.sessionId) return;
  $("btnCancelSearch").disabled = true;
  try {
    await post(`/users/${state.userId}/sessions/${state.sessionId}/cancel`, {});
    toast("Annullamento richiesto...", "");
  } catch (e) {
    toast(e.message, "bad");
    $("btnCancelSearch").disabled = false;
  }
});

async function refreshLogs() {
  try {
    const logs = await get(`/users/${state.userId}/sessions/${state.sessionId}/logs?limit=60`);
    const box = $("logStream");
    box.innerHTML = "";
    logs.slice().reverse().forEach(l => {
      const line = el("div", `log-line ${l.level || "info"}`);
      const t = new Date(l.ts);
      const hh = String(t.getHours()).padStart(2, "0");
      const mm = String(t.getMinutes()).padStart(2, "0");
      const ss = String(t.getSeconds()).padStart(2, "0");
      line.appendChild(el("span", "log-time", `${hh}:${mm}:${ss}`));
      line.appendChild(el("span", "log-src", (l.source || "").slice(0, 18)));
      line.appendChild(el("span", "log-msg", l.result || l.action || ""));
      box.appendChild(line);
    });
    box.scrollTop = box.scrollHeight;
  } catch (e) { console.warn(e); }
}

// ---------- Filtri (agiscono sulla lista Zona A) ----------
document.querySelectorAll("#matchFilters .pill").forEach(p => {
  p.addEventListener("click", () => {
    document.querySelectorAll("#matchFilters .pill").forEach(x => x.classList.remove("is-active"));
    p.classList.add("is-active");
    state.matchStatusFilter = p.dataset.status;
    renderListingList();
  });
});

// ---------- Merge listings + matches (Zona A: TUTTI gli annunci, non solo i match) ----------
async function refreshResultsList() {
  const [listings, matches] = await Promise.all([
    get(`/users/${state.userId}/sessions/${state.sessionId}/listings`),
    get(`/users/${state.userId}/sessions/${state.sessionId}/matches`), // niente filtro qui: serve la mappa completa
  ]);
  const matchByListing = new Map(matches.map(m => [m.listing_id, m]));
  const merged = listings.map(l => ({ listing: l, match: matchByListing.get(l.id) || null }));

  // sopra soglia (ha un Match) prima, per score decrescente; poi sotto soglia, più recenti prima
  merged.sort((a, b) => {
    if (!!a.match !== !!b.match) return a.match ? -1 : 1;
    if (a.match) return b.match.score - a.match.score;
    return new Date(b.listing.scraped_at) - new Date(a.listing.scraped_at);
  });

  state.resultsItems = merged;

  // se l'elemento selezionato non esiste più nella lista aggiornata, deseleziona
  if (state.selectedResultItem) {
    const stillThere = merged.find(it => it.listing.id === state.selectedResultItem.listing.id);
    state.selectedResultItem = stillThere || null;
    if (stillThere) renderDetail(stillThere); // riflette eventuali documenti/stato aggiornati
  }

  renderListingList();
  if (!state.selectedResultItem) renderDetail(null);
}

function renderListingList() {
  // il filtro di stato ha senso solo per i match (gli annunci sotto soglia
  // non hanno uno status): con "Tutti" restano visibili, altrimenti no
  const filtered = state.matchStatusFilter
    ? state.resultsItems.filter(it => it.match && it.match.status === state.matchStatusFilter)
    : state.resultsItems;

  const box = $("listingList");
  box.innerHTML = "";
  if (!filtered.length) {
    box.innerHTML = '<div class="stack-empty">Nessun annuncio ancora. Se la ricerca è finita vai al Resoconto per capire perché.</div>';
    return;
  }
  filtered.forEach(item => box.appendChild(renderListingCard(item)));
}

function renderListingCard(item) {
  const isSelected = !!(state.selectedResultItem && state.selectedResultItem.listing.id === item.listing.id);
  const cls = "listing-card" + (item.match ? " is-match" : "") + (isSelected ? " is-selected" : "");
  const card = el("div", cls);

  const line = el("div", "listing-line");
  line.appendChild(el("span", "listing-role", item.listing.title));
  line.appendChild(el("span", "listing-arrow", "→"));
  line.appendChild(el("span", "listing-co", [item.listing.company_name, item.listing.source_board].filter(Boolean).join(" · ")));
  card.appendChild(line);

  if (item.match) {
    const meta = el("div", "listing-meta");
    meta.appendChild(el("span", `listing-score ${scoreClass(item.match.score)}`, fmtPct(item.match.score)));
    const statusLabels = { new: "Nuovo", saved: "Salvato", applied: "Inviato", interview: "Colloquio", rejected: "Scartato" };
    meta.appendChild(el("span", "badge", statusLabels[item.match.status] || item.match.status));
    card.appendChild(meta);
  }

  card.addEventListener("click", () => selectResultItem(item));
  return card;
}

// ---------- Selezione: popola Zona B (dettaglio) + Zona C (contenuto annuncio) ----------
function selectResultItem(item) {
  state.selectedResultItem = item;
  renderListingList();
  renderDetail(item);
  if (window.matchMedia("(max-width: 900px)").matches) {
    $("resultsLayout").classList.add("show-detail");
  }
}

$("btnBackToList").addEventListener("click", () => {
  $("resultsLayout").classList.remove("show-detail");
});

function renderDetail(item) {
  $("detailPlaceholder").classList.toggle("hidden", !!item);
  $("detailGrid").classList.toggle("hidden", !item);
  $("listingContentPlaceholder").classList.toggle("hidden", !!item);
  $("listingContent").classList.toggle("hidden", !item);
  if (!item) return;

  renderDetailStats(item);
  renderDetailDoc("detailLetter", "cover_letter", "Lettera di presentazione", item);
  renderDetailDoc("detailCV", "cv", "CV", item);
  renderDetailDoc("detailEmail", "email", "Email", item);
  renderListingContent(item);
}

function renderDetailStats(item) {
  const card = $("detailStats");
  card.innerHTML = "";
  card.appendChild(el("div", "detail-card-title", "Statistiche e consigli"));

  if (!item.match) {
    card.appendChild(el("div", "detail-empty", "Sotto soglia — nessuna analisi salvata per questo annuncio."));
    return;
  }
  const m = item.match;
  card.appendChild(el("div", `detail-score ${scoreClass(m.score)}`, fmtPct(m.score)));
  card.appendChild(el("div", "detail-score-cap", `Keyword ${fmtPct(m.keyword_score)} · AI ${fmtPct(m.semantic_score)}`));

  const matched = parseJSON(m.matched_skills, []);
  const missing = parseJSON(m.missing_skills, []);
  if (matched.length || missing.length) {
    const sk = el("div", "match-skills");
    matched.slice(0, 8).forEach(s => sk.appendChild(el("span", "sk sk-yes", "+ " + s)));
    missing.slice(0, 6).forEach(s => sk.appendChild(el("span", "sk sk-no", "– " + s)));
    card.appendChild(sk);
  }
  if (m.gap_analysis) card.appendChild(el("div", "match-gap", m.gap_analysis));

  const sel = document.createElement("select");
  sel.className = "detail-status-select";
  ["new", "saved", "applied", "interview", "rejected"].forEach(v => {
    const opt = document.createElement("option");
    opt.value = v;
    opt.textContent = { new: "Nuovo", saved: "Salvato", applied: "Inviato", interview: "Colloquio", rejected: "Scartato" }[v];
    if (m.status === v) opt.selected = true;
    sel.appendChild(opt);
  });
  sel.addEventListener("change", async () => {
    await patch(`/matches/${m.id}/status`, { status: sel.value });
    m.status = sel.value;
    toast("Stato aggiornato", "ok");
    renderListingList(); // aggiorna il badge nella card di sinistra
  });
  card.appendChild(sel);
}

function renderDetailDoc(elId, docType, label, item) {
  const card = $(elId);
  card.innerHTML = "";
  card.appendChild(el("div", "detail-card-title", label));

  if (!item.match) {
    card.appendChild(el("div", "detail-empty", "Non generato — annuncio sotto soglia."));
    return;
  }
  const doc = (item.match.documents || []).find(d => d.doc_type === docType);
  if (!doc) {
    card.appendChild(el("div", "detail-empty", "Non ancora generato."));
    const btn = el("button", "btn btn-ghost", "Genera");
    btn.addEventListener("click", () => regenerateDetailDoc(item, docType));
    card.appendChild(btn);
    return;
  }

  const preview = doc.content.length > 160 ? doc.content.slice(0, 160) + "…" : doc.content;
  card.appendChild(el("div", "detail-doc-preview", preview));

  const actions = el("div", "detail-card-actions");
  const openBtn = el("button", "btn btn-ghost", "Apri");
  openBtn.addEventListener("click", () => openDoc(doc, item.match));
  const regenBtn = el("button", "btn btn-ghost", "Rigenera");
  regenBtn.addEventListener("click", () => regenerateDetailDoc(item, docType));
  actions.appendChild(openBtn);
  actions.appendChild(regenBtn);
  card.appendChild(actions);
}

async function regenerateDetailDoc(item, docType) {
  if (!item.match) return;
  toast("Sto generando il documento...", "");
  try {
    await post(`/documents/regenerate/${item.match.id}`, { doc_type: docType });
    toast("Documento pronto", "ok");
    const fresh = await get(`/matches/${item.match.id}`);
    item.match = fresh;
    if (state.selectedResultItem && state.selectedResultItem.listing.id === item.listing.id) {
      state.selectedResultItem.match = fresh;
      renderDetail(item);
    }
  } catch (e) { toast(e.message, "bad"); }
}

// ---------- Zona C: contenuto dell'annuncio ----------
function renderListingContent(item) {
  const box = $("listingContent");
  box.innerHTML = "";
  const l = item.listing;

  box.appendChild(el("div", "lc-eyebrow", l.source_board || "Fonte sconosciuta"));
  box.appendChild(el("h3", "lc-title", l.title));
  box.appendChild(el("div", "lc-company", l.company_name));

  const metaBits = [l.location, l.contract_type, l.posted_date].filter(Boolean);
  if (metaBits.length) box.appendChild(el("div", "lc-meta", metaBits.join(" · ")));

  if (l.description) {
    box.appendChild(el("div", "lc-h4", "Descrizione"));
    box.appendChild(el("div", "lc-text", l.description));
  }
  if (l.requirements_raw) {
    box.appendChild(el("div", "lc-h4", "Requisiti"));
    box.appendChild(el("div", "lc-text", l.requirements_raw));
  }
  if (!l.description && !l.requirements_raw) {
    box.appendChild(el("div", "stack-empty", "Nessun testo disponibile per questo annuncio."));
  }

  if (l.source_url) {
    const foot = el("div", "lc-foot");
    const a = document.createElement("a");
    a.href = l.source_url;
    a.target = "_blank";
    a.rel = "noreferrer";
    a.className = "btn btn-primary";
    a.textContent = "Apri annuncio originale ↗";
    foot.appendChild(a);
    box.appendChild(foot);
  }
}

// ---------- Sheet documento ----------
let currentDoc = null;
function openDoc(doc, m) {
  // Preserva is_temp se esiste, altrimenti false
  currentDoc = {
    ...doc,
    is_temp: doc.is_temp || false
  };
  const labels = { cv: "Curriculum", cover_letter: "Lettera di presentazione", email: "Bozza email" };
  $("docKind").textContent = labels[doc.doc_type];
  $("docTitle").textContent = `${m.listing?.company_name} — ${m.listing?.title}`;
  $("docBody").textContent = doc.content;
  $("docSheet").classList.add("is-open");
}


$("btnCloseDoc").addEventListener("click", () => $("docSheet").classList.remove("is-open"));
$("docSheet").addEventListener("click", (e) => {
  if (e.target.id === "docSheet") $("docSheet").classList.remove("is-open");
});

document.querySelectorAll(".sheet-foot .btn[data-fmt]").forEach(b => {
  b.addEventListener("click", async () => {
    if (!currentDoc) return;
    const fmt = b.dataset.fmt;
    try {
      // Se è un documento temporaneo (da URL) → scarica il contenuto direttamente
      if (currentDoc.is_temp) {
        const content = currentDoc.content;
        const blob = new Blob([content], { type: 'text/plain' });
        const downloadUrl = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = downloadUrl;
        a.download = `${currentDoc.doc_type}.${fmt}`;
        a.click();
        URL.revokeObjectURL(downloadUrl);
        toast('Documento scaricato', 'ok');
        return;
      }

      // Altrimenti, se è un documento salvato in DB → usa l'API
      if (currentDoc.id) {
        const response = await fetch(`${API}/documents/${currentDoc.id}/export?fmt=${fmt}`, {
          headers: { 'X-API-Token': 'local-dev-token-2026' }
        });
        if (!response.ok) throw new Error('Download fallito');
        const blob = await response.blob();
        const downloadUrl = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = downloadUrl;
        a.download = `documento.${fmt}`;
        a.click();
        URL.revokeObjectURL(downloadUrl);
      } else {
        throw new Error('Documento senza contenuto');
      }
    } catch (e) {
      toast('Errore download: ' + e.message, 'bad');
    }
  });
});


$("btnCopyDoc").addEventListener("click", async () => {
  if (!currentDoc) return;
  await navigator.clipboard.writeText(currentDoc.content);
  toast("Copiato negli appunti", "ok");
});

// ================================================================
// INTELLIGENCE
// ================================================================
async function refreshIntelligence() {
  if (!state.sessionId) return;
  const body = $("intelBody");
  body.innerHTML = '<div class="panel"><div class="stack-empty">Calcolo il resoconto...</div></div>';

  try {
    const r = await get(`/users/${state.userId}/sessions/${state.sessionId}/intelligence`);
    body.innerHTML = "";

    if (r.summary) {
      const p = el("div", "panel");
      p.appendChild(el("div", "eyebrow", "In poche parole"));
      p.appendChild(el("div", "summary-block", r.summary));
      body.appendChild(p);
    }

    // metriche
    const metrics = el("div", "panel");
    metrics.appendChild(el("div", "eyebrow", "I numeri"));
    const row = el("div", "metric-row");
    [
      ["Annunci esaminati", r.total_listings],
      ["Match sopra soglia", r.total_matches],
      ["Score medio", fmtPct(r.avg_score)],
      ["Miglior match", fmtPct(r.best_score)],
      ["Portali usati", r.sources_queried],
      ["Aziende verificate", `${r.companies_verified}/${r.total_companies}`],
    ].forEach(([cap, val]) => {
      const c = el("div", "metric");
      c.appendChild(el("div", "metric-val", val));
      c.appendChild(el("div", "metric-cap", cap));
      row.appendChild(c);
    });
    metrics.appendChild(row);
    body.appendChild(metrics);

    // skill mancanti
    if (r.top_missing_skills.length) {
      const p = el("div", "panel");
      const h = el("div", "panel-head");
      h.appendChild(el("h2", "", "Cosa ti manca più spesso"));
      h.appendChild(el("p", "panel-note", "Le competenze richieste dagli annunci che non hai indicato nel profilo."));
      p.appendChild(h);
      const maxN = Math.max(...r.top_missing_skills.map(x => x.count));
      r.top_missing_skills.forEach(s => {
        const row = el("div", "gap-bar-row");
        row.appendChild(el("div", "gap-name", s.skill));
        const track = el("div", "gap-track");
        const fill = el("div", "gap-fill");
        fill.style.width = ((s.count / maxN) * 100) + "%";
        track.appendChild(fill);
        row.appendChild(track);
        row.appendChild(el("div", "gap-n", `${s.count} annunci`));
        p.appendChild(row);
      });
      body.appendChild(p);
    }

    // outcome per azienda
    if (r.company_outcomes.length) {
      const p = el("div", "panel");
      const h = el("div", "panel-head");
      h.appendChild(el("h2", "", "Aziende target: cosa è successo"));
      h.appendChild(el("p", "panel-note", "Per ogni azienda che hai scelto, cosa ho trovato e perché."));
      p.appendChild(h);
      r.company_outcomes.forEach(o => {
        const row = el("div", "outcome");
        row.appendChild(el("div", "outcome-name", o.company));
        row.appendChild(el("div", "outcome-why", o.reason));
        row.appendChild(el("div", "outcome-n", `${o.matches_found}/${o.listings_found}`));
        p.appendChild(row);
      });
      body.appendChild(p);
    }

    // ruoli alternativi
    if (r.alternative_roles.length) {
      const p = el("div", "panel");
      const h = el("div", "panel-head");
      h.appendChild(el("h2", "", "Prova anche questi ruoli"));
      h.appendChild(el("p", "panel-note", "Posizioni con competenze sovrapposte a quelle che hai — spesso più aperte del ruolo target."));
      p.appendChild(h);
      const grid = el("div", "card-row");
      r.alternative_roles.forEach(a => {
        const card = el("div", "alt-card");
        card.appendChild(el("div", "alt-role", a.role));
        if (a.why) card.appendChild(el("div", "alt-why", a.why));
        if (a.overlap) card.appendChild(el("div", "alt-overlap", "Sovrapposizione: " + a.overlap));
        grid.appendChild(card);
      });
      p.appendChild(grid);
      body.appendChild(p);
    }
  } catch (e) {
    body.innerHTML = `<div class="panel"><div class="stack-empty">Impossibile calcolare il resoconto: ${e.message}</div></div>`;
  }
}

// ---------- Avvio ----------
(async function init() {
    await boot();
})();

// ================================================================
// Geografia — Paese/continente e Zona dipendente
//
// Il campo Zona prima era testo libero e finiva grezzo nell'URL di ogni
// portale: "Marche" veniva mandato anche a StepStone (Germania) e a Reed
// (Regno Unito). Ora è un elenco che dipende dal paese scelto, e su un
// continente si spegne — un continente non ha regioni.
// ================================================================
let geoTree = null;

async function loadGeo() {
  try {
    geoTree = await get("/geo");
  } catch (e) {
    console.warn("Geografia non disponibile", e);
    return;
  }
  const sel = $("ssCountry");
  const prev = sel.value;
  sel.innerHTML = '<option value="">Nessuna preferenza</option>';

  geoTree.continents.forEach(c => {
    const o = document.createElement("option");
    o.value = c.code;
    o.textContent = `${c.name} (tutti i portali configurati)`;
    sel.appendChild(o);
  });
  geoTree.countries.forEach(c => {
    const o = document.createElement("option");
    o.value = c.code;
    o.textContent = c.name;
    sel.appendChild(o);
  });

  sel.value = prev || "IT";
  refreshZoneOptions();
}

function refreshZoneOptions() {
  if (!geoTree) return;
  const code = $("ssCountry").value;
  const zone = $("ssLocation");
  const help = $("ssLocationHelp");
  const prev = zone.value;

  const isContinent = geoTree.continents.some(c => c.code === code);
  const country = geoTree.countries.find(c => c.code === code);

  zone.innerHTML = '<option value="">Tutto il paese</option>';

  if (!code) {
    zone.disabled = true;
    help.textContent = "Scegli prima un paese.";
    return;
  }
  if (isContinent) {
    // Deliberato: niente campo libero. Una zona di un paese mandata ai
    // portali di tutti gli altri è rumore, non un filtro.
    zone.disabled = true;
    help.textContent =
      "Un continente non ha regioni: la ricerca gira su tutti i portali dei paesi configurati.";
    return;
  }

  zone.disabled = false;
  (country?.regions || []).forEach(r => {
    const o = document.createElement("option");
    o.value = r;
    o.textContent = r;
    zone.appendChild(o);
  });
  zone.value = (country?.regions || []).includes(prev) ? prev : "";
  help.textContent = zone.options.length > 1
    ? "Facoltativa: lascia \u201cTutto il paese\u201d per non restringere."
    : "Nessuna regione configurata per questo paese.";
}

$("ssCountry").addEventListener("change", refreshZoneOptions);

// ================================================================
// Bio derivata dal CV base
// ================================================================
$("btnRegenBio").addEventListener("click", async () => {
  if (!state.userId) { toast("Crea prima il profilo", "bad"); return; }
  const btn = $("btnRegenBio");
  btn.disabled = true;
  btn.textContent = "Genero\u2026";
  try {
    const r = await post(`/users/${state.userId}/base-documents/bio/regenerate`, {});
    $("pfBio").value = r.bio || "";
    toast("Sintesi aggiornata dal CV");
  } catch (e) {
    toast(e.message || "Serve prima un CV base", "bad");
  } finally {
    btn.disabled = false;
    btn.textContent = "Rigenera dal CV";
  }
});

// ================================================================
// Collezioni di aziende — le "bacheche"
//
// Differenza rispetto alle "Aziende d'interesse" del profilo, che sono una
// lista unica e piatta: qui si raggruppano per tema, e il riferimento per
// trovare simili e' il GRUPPO, non la singola azienda.
// ================================================================
let currentCollection = null;

async function loadThemes() {
  if (!state.userId) return;
  let themes = [];
  try { themes = await get(`/users/${state.userId}/collections/themes`); }
  catch { return; }
  const box = $("themeChips");
  box.innerHTML = "";
  themes.forEach(t => {
    const b = document.createElement("button");
    b.className = "chip";
    b.textContent = t.label;
    b.addEventListener("click", () => searchByTheme(t.key, t.label));
    box.appendChild(b);
  });
}

async function searchByTheme(key, label) {
  if (!currentCollection) { toast("Apri prima una lista", "bad"); return; }
  toast(`Cerco: ${label}\u2026`);
  try {
    const res = await post(`/users/${state.userId}/companies/by-theme`, {
      theme: key,
      country_code: $("ssCountry")?.value || null,
      limit: 8,
    });
    renderSuggestions(res, "collSimilarResults");
  } catch (e) { toast(e.message || "Ricerca per tema fallita", "bad"); }
}

async function loadCollections() {
  if (!state.userId) return;
  let colls = [];
  try { colls = await get(`/users/${state.userId}/collections`); }
  catch { return; }

  const box = $("collectionList");
  box.innerHTML = "";
  if (!colls.length) {
    box.innerHTML = '<p class="hint">Nessuna lista. Creane una qui sopra.</p>';
    return;
  }
  colls.forEach(c => {
    const li = document.createElement("div");
    li.className = "panel";
    li.innerHTML = `<div class="panel-head"><h2>${escapeHtml(c.name)}</h2>
      <p class="panel-note">${escapeHtml(c.description || c.profile_summary || "")}</p></div>`;
    const foot = document.createElement("div");
    foot.className = "panel-foot";
    const open = document.createElement("button");
    open.className = "btn btn-ghost";
    open.textContent = "Apri";
    open.addEventListener("click", () => openCollection(c));
    const del = document.createElement("button");
    del.className = "btn btn-micro";
    del.textContent = "Elimina";
    del.addEventListener("click", async () => {
      if (!confirm(`Eliminare la lista "${c.name}"? Le ricerche a cui l'hai gia' applicata non cambiano.`)) return;
      await del(`/users/${state.userId}/collections/${c.id}`);
      if (currentCollection?.id === c.id) {
        currentCollection = null;
        $("collectionDetail").classList.add("hidden");
      }
      await loadCollections();
    });
    foot.append(open, del);
    li.appendChild(foot);
    box.appendChild(li);
  });
}

async function openCollection(c) {
  currentCollection = c;
  $("collectionDetail").classList.remove("hidden");
  $("collDetailName").textContent = c.name;
  $("collDetailSummary").textContent = c.profile_summary || c.description || "";
  $("collSimilarResults").innerHTML = "";
  await Promise.all([loadCollectionMembers(), fillApplyTargets()]);
}

async function loadCollectionMembers() {
  if (!currentCollection) return;
  const members = await get(
    `/users/${state.userId}/collections/${currentCollection.id}/members`);
  const ul = $("collMembers");
  ul.innerHTML = "";
  if (!members.length) {
    ul.innerHTML = '<li class="hint">Lista vuota: aggiungi un\'azienda o parti da un tema.</li>';
    return;
  }
  members.forEach(m => {
    const li = document.createElement("li");
    li.className = "stack-row";
    li.innerHTML = `<span>${escapeHtml(m.name)}</span>
      <span class="hint">${escapeHtml([m.sector, m.country].filter(Boolean).join(" \u00b7 "))}</span>`;
    const x = document.createElement("button");
    x.className = "btn btn-micro";
    x.textContent = "\u00d7";
    x.addEventListener("click", async () => {
      await del(`/users/${state.userId}/collections/${currentCollection.id}/members/${m.id}`);
      await loadCollectionMembers();
    });
    li.appendChild(x);
    ul.appendChild(li);
  });
}

async function addToCollection(company) {
  if (!currentCollection) { toast("Apri prima una lista", "bad"); return; }
  await post(`/users/${state.userId}/collections/${currentCollection.id}/members`, company);
  await loadCollectionMembers();
}

function renderSuggestions(list, targetId) {
  const box = $(targetId);
  box.innerHTML = "";
  if (!list.length) {
    box.innerHTML = '<p class="hint">Nessun suggerimento.</p>';
    return;
  }
  list.forEach(s => {
    const card = document.createElement("div");
    card.className = "card";
    card.innerHTML = `<strong>${escapeHtml(s.name)}</strong>
      <span class="hint">${escapeHtml([s.sector, s.size, s.reason].filter(Boolean).join(" \u00b7 "))}</span>`;
    const add = document.createElement("button");
    add.className = "btn btn-micro";
    add.textContent = "Aggiungi";
    add.addEventListener("click", async () => {
      await addToCollection({
        name: s.name, sector: s.sector, size: s.size,
        website: s.website, country: s.country, added_via: "similar",
      });
      add.textContent = "\u2713";
      add.disabled = true;
    });
    card.appendChild(add);
    box.appendChild(card);
  });
}

async function fillApplyTargets() {
  const sel = $("collApplyTarget");
  sel.innerHTML = "";
  const sessions = await get(`/users/${state.userId}/sessions`);
  if (!sessions.length) {
    sel.innerHTML = '<option value="">Nessuna ricerca</option>';
    return;
  }
  sessions.forEach(s => {
    const o = document.createElement("option");
    o.value = s.id;
    o.textContent = `${s.role_title} \u2014 ${new Date(s.created_at).toLocaleDateString("it-IT")}`;
    sel.appendChild(o);
  });
}

$("btnCreateCollection").addEventListener("click", async () => {
  if (!state.userId) { toast("Crea prima il profilo", "bad"); return; }
  const name = $("collName").value.trim();
  if (!name) { toast("Dai un nome alla lista", "bad"); return; }
  await post(`/users/${state.userId}/collections`, {
    name, description: $("collDesc").value.trim() || null,
  });
  $("collName").value = ""; $("collDesc").value = "";
  await loadCollections();
  toast("Lista creata");
});

$("btnCollAdd").addEventListener("click", async () => {
  const name = $("collAddCompany").value.trim();
  if (!name) return;
  await addToCollection({ name, added_via: "manual" });
  $("collAddCompany").value = "";
});

$("btnCollSimilar").addEventListener("click", async () => {
  if (!currentCollection) return;
  const btn = $("btnCollSimilar");
  btn.disabled = true; btn.textContent = "Cerco\u2026";
  try {
    const res = await post(
      `/users/${state.userId}/collections/${currentCollection.id}/similar`,
      { limit: 8, country_code: $("ssCountry")?.value || null });
    renderSuggestions(res, "collSimilarResults");
  } catch (e) { toast(e.message || "Nessun suggerimento", "bad"); }
  finally { btn.disabled = false; btn.textContent = "Trova simili alla lista"; }
});

$("btnCollApply").addEventListener("click", async () => {
  const sid = $("collApplyTarget").value;
  if (!currentCollection || !sid) { toast("Scegli una ricerca", "bad"); return; }
  const r = await post(
    `/users/${state.userId}/collections/${currentCollection.id}/apply/${sid}`, {});
  toast(`${r.added} aziende aggiunte alla ricerca (${r.total} nella lista)`);
});


