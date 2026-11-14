// ================================================================
// JobMatcher — frontend
// SPA leggera: fetch dell'API + rendering vanilla JS.
// Stato in localStorage per persistere user_id e session_id attivi.
// ================================================================

const API = "/api";

const state = {
  userId: localStorage.getItem("jm.userId") || null,
  sessionId: localStorage.getItem("jm.sessionId") || null,
  view: "profile",
  softCatalog: [],
  softSelected: new Set(),
  currentCompanySuggestions: [],
  targetCompanies: [],
  suggestedRoleSkills: [],
  matchStatusFilter: "",
  pollTimer: null,
};

// ---------- HTTP ----------
async function api(method, path, body) {
  const opt = { method, headers: { "Content-Type": "application/json" } };
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
function el(tag, cls, txt) {
  const e = document.createElement(tag);
  if (cls) e.className = cls;
  if (txt !== undefined) e.textContent = txt;
  return e;
}

// ---------- Navigation ----------
document.querySelectorAll(".rail-item").forEach(btn => {
  btn.addEventListener("click", () => switchView(btn.dataset.view));
});
function switchView(name) {
  state.view = name;
  document.querySelectorAll(".rail-item").forEach(b => b.classList.toggle("is-active", b.dataset.view === name));
  document.querySelectorAll(".view").forEach(v => v.classList.toggle("is-visible", v.id === `view-${name}`));
  if (name === "results" && state.sessionId) refreshResultsView();
  if (name === "intelligence" && state.sessionId) refreshIntelligence();
  if (name === "sessions" && state.userId) refreshSessions();
}

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
  if (state.userId) {
    try {
      await loadUser();
      unlockProfilePanels();
      await refreshSessions();
    } catch (e) {
      console.warn(e);
      localStorage.removeItem("jm.userId");
      state.userId = null;
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
      localStorage.setItem("jm.userId", user.id);
    }
    $("railUser").textContent = user.name;
    $("profileHint").textContent = "Salvato";
    $("profileHint").className = "hint ok";
    unlockProfilePanels();
    await loadAllProfileSections();
    toast("Profilo salvato", "ok");
  } catch (e) {
    toast("Errore: " + e.message, "bad");
  }
});

function unlockProfilePanels() {
  ["panelSoft", "panelHard", "panelExp", "panelEdu"].forEach(id => {
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
  unlockProfilePanels();
  await loadAllProfileSections();
}

async function loadAllProfileSections() {
  await Promise.all([loadSoftSkills(), loadHardSkills(), loadExperiences(), loadEducation()]);
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
  } catch (e) { toast(e.message, "bad"); }
}

async function loadSoftSkills() {
  const list = await get(`/users/${state.userId}/soft-skills`);
  state.softSelected = new Set(list.map(s => s.name));
  renderSoftCatalog();
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
// SESSIONI
// ================================================================
$("ssThreshold").addEventListener("input", (e) => {
  $("ssThresholdOut").textContent = e.target.value + "%";
});

$("btnCreateSession").addEventListener("click", async () => {
  if (!state.userId) { toast("Crea prima il profilo", "bad"); return; }
  const role = $("ssRole").value.trim();
  if (!role) { toast("Indica il ruolo che cerchi", "bad"); return; }
  const payload = {
    role_title: role,
    preferred_country: $("ssCountry").value || null,
    location_pref: $("ssLocation").value.trim() || null,
    contract_type: $("ssContract").value || null,
    match_threshold: parseInt($("ssThreshold").value, 10) / 100,
  };
  try {
    const s = await post(`/users/${state.userId}/sessions`, payload);
    $("ssRole").value = "";
    $("ssLocation").value = "";
    await refreshSessions();
    selectSession(s.id);
    toast("Ricerca creata", "ok");
  } catch (e) { toast(e.message, "bad"); }
});

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
    card.addEventListener("click", () => selectSession(s.id));

    card.appendChild(el("div", "session-role", s.role_title));
    const badge = el("span", `badge badge-${s.status}`, s.status);
    const meta = el("div", "session-meta");
    if (s.preferred_country) meta.appendChild(el("span", "", s.preferred_country));
    if (s.location_pref) meta.appendChild(el("span", "", s.location_pref));
    meta.appendChild(badge);
    card.appendChild(meta);

    box.appendChild(card);
  });
}

async function selectSession(id) {
  state.sessionId = id;
  localStorage.setItem("jm.sessionId", id);
  document.querySelectorAll(".session-card").forEach(c => c.classList.remove("is-on"));

  const s = await get(`/users/${state.userId}/sessions/${id}`);
  $("cfgTag").textContent = `Ricerca · ${s.role_title}`;
  $("sessionConfig").classList.remove("hidden");
  $("skillHint").textContent = "";
  $("skillSuggestions").innerHTML = "";
  $("companyResults").innerHTML = "";
  $("similarBlock").classList.add("hidden");

  await Promise.all([loadSessionSkills(), loadTargetCompanies()]);
  refreshSessions();
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
  const existing = await get(`/users/${state.userId}/sessions/${state.sessionId}/hard-skills`);
  const existingNames = new Set(existing.map(x => x.name.toLowerCase()));

  const box = $("skillSuggestions");
  box.innerHTML = "";
  state.suggestedRoleSkills.forEach(s => {
    const chip = el("button", "chip", s.name);
    chip.type = "button";
    if (existingNames.has(s.name.toLowerCase())) chip.classList.add("is-on");
    if (s.importance) {
      const meta = el("span", "chip-meta", s.importance.slice(0, 3));
      chip.appendChild(meta);
    }
    chip.addEventListener("click", async () => {
      if (chip.classList.contains("is-on")) {
        const list = await get(`/users/${state.userId}/sessions/${state.sessionId}/hard-skills`);
        const f = list.find(x => x.name.toLowerCase() === s.name.toLowerCase());
        if (f) await del(`/users/${state.userId}/sessions/${state.sessionId}/hard-skills/${f.id}`);
        chip.classList.remove("is-on");
      } else {
        await post(`/users/${state.userId}/sessions/${state.sessionId}/hard-skills`,
          { name: s.name, category: s.category, required: s.importance !== "nice_to_have" });
        chip.classList.add("is-on");
      }
      loadSessionSkills();
    });
    box.appendChild(chip);
  });
}

async function loadSessionSkills() {
  const list = await get(`/users/${state.userId}/sessions/${state.sessionId}/hard-skills`);
  const ul = $("sessionSkillList");
  ul.innerHTML = "";
  if (!list.length) { ul.innerHTML = '<li class="stack-empty">Nessuna competenza richiesta impostata</li>'; return; }
  list.forEach(s => {
    const li = el("li");
    const main = el("div", "stack-main");
    main.appendChild(el("div", "stack-title", s.name));
    main.appendChild(el("div", "stack-sub",
      `${s.required ? "obbligatoria" : "preferibile"} · min ${s.min_years} anni`));
    const btn = el("button", "btn btn-danger", "Rimuovi");
    btn.addEventListener("click", async () => {
      await del(`/users/${state.userId}/sessions/${state.sessionId}/hard-skills/${s.id}`);
      loadSessionSkills();
      renderSkillSuggestions();
    });
    li.appendChild(main); li.appendChild(btn);
    ul.appendChild(li);
  });
}

// ---------- Tabs aziende ----------
document.querySelectorAll("#companyTabs .tab").forEach(tab => {
  tab.addEventListener("click", () => {
    document.querySelectorAll("#companyTabs .tab").forEach(t => t.classList.remove("is-active"));
    tab.classList.add("is-active");
    document.querySelectorAll(".tab-body").forEach(b => b.classList.toggle("is-visible", b.dataset.body === tab.dataset.tab));
  });
});

// ---------- Ricerca aziende (RF2.2) ----------
$("btnSearchCompany").addEventListener("click", async () => {
  const q = $("coQuery").value.trim();
  if (!q) return;
  const s = await get(`/users/${state.userId}/sessions/${state.sessionId}`);
  const results = await post(`/users/${state.userId}/sessions/${state.sessionId}/companies/search`, {
    query: q, location: s.location_pref, sector: null, limit: 8,
  });
  state.currentCompanySuggestions = results;
  renderCompanyResults();
});

$("btnSearchLocal").addEventListener("click", async () => {
  const sector = $("coSector").value.trim();
  const area = $("coArea").value.trim();
  if (!sector || !area) { toast("Serve settore e zona", "bad"); return; }
  const results = await post(`/users/${state.userId}/sessions/${state.sessionId}/companies/search-local`, {
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
async function addTargetCompany(c) {
  try {
    await post(`/users/${state.userId}/sessions/${state.sessionId}/companies`, {
      name: c.name, country: c.country, size: c.size, sector: c.sector,
      website: c.website, source: c.source || "manual",
    });
    await loadTargetCompanies();
    await refreshSimilar();  // effetto Spotify
    renderCompanyResults();
  } catch (e) { toast(e.message, "bad"); }
}

async function loadTargetCompanies() {
  const list = await get(`/users/${state.userId}/sessions/${state.sessionId}/companies`);
  state.targetCompanies = list;
  const ul = $("targetList");
  ul.innerHTML = "";
  if (!list.length) {
    ul.innerHTML = '<li class="stack-empty">Nessuna azienda selezionata (opzionale — la ricerca funziona anche solo sui portali)</li>';
    $("similarBlock").classList.add("hidden");
    return;
  }
  list.forEach(c => {
    const li = el("li");
    const main = el("div", "stack-main");
    main.appendChild(el("div", "stack-title", c.name));
    main.appendChild(el("div", "stack-sub",
      [c.sector, c.country, c.source].filter(Boolean).join(" · ")));
    const btn = el("button", "btn btn-danger", "Rimuovi");
    btn.addEventListener("click", async () => {
      await del(`/users/${state.userId}/sessions/${state.sessionId}/companies/${c.id}`);
      loadTargetCompanies();
      refreshSimilar();
    });
    li.appendChild(main); li.appendChild(btn);
    ul.appendChild(li);
  });

  if (list.length >= 1) await refreshSimilar();
}

$("btnRefreshSimilar").addEventListener("click", refreshSimilar);

async function refreshSimilar() {
  if (!state.targetCompanies.length) {
    $("similarBlock").classList.add("hidden");
    return;
  }
  const s = await get(`/users/${state.userId}/sessions/${state.sessionId}`);
  try {
    const similar = await post(`/users/${state.userId}/sessions/${state.sessionId}/companies/similar`, {
      selected_companies: state.targetCompanies.map(c => c.name),
      location: s.location_pref, sector: null, limit: 5,
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
    switchView("results");
    startPolling();
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
    if (s.status === "completed" || s.status === "error") {
      stopPolling();
      await refreshMatches();
      refreshSessions();
    }
  }, 2500);
}

async function refreshResultsView() {
  if (!state.sessionId) return;
  const s = await get(`/users/${state.userId}/sessions/${state.sessionId}/status`);
  updateRunBar(s);
  await refreshLogs();
  await refreshMatches();
  if (s.status === "running") startPolling();
}

function updateRunBar(s) {
  const map = { draft: "In attesa", running: "In esecuzione", completed: "Completata", error: "Errore" };
  $("runState").textContent = map[s.status] || s.status;
  $("runMsg").textContent = s.progress_message || "—";
  $("runCount").textContent = `${s.matches_found} match`;
  const pct = s.progress_total > 0 ? (s.progress_current / s.progress_total) * 100 : (s.status === "completed" ? 100 : 0);
  $("progressFill").style.width = pct + "%";
}

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

// ---------- Filtri match ----------
document.querySelectorAll("#matchFilters .pill").forEach(p => {
  p.addEventListener("click", () => {
    document.querySelectorAll("#matchFilters .pill").forEach(x => x.classList.remove("is-active"));
    p.classList.add("is-active");
    state.matchStatusFilter = p.dataset.status;
    refreshMatches();
  });
});

async function refreshMatches() {
  const qs = state.matchStatusFilter ? `?status=${state.matchStatusFilter}` : "";
  const list = await get(`/users/${state.userId}/sessions/${state.sessionId}/matches${qs}`);
  const box = $("matchList");
  box.innerHTML = "";
  if (!list.length) {
    box.innerHTML = '<div class="stack-empty">Nessun match ancora. Se la ricerca è finita vai al Resoconto per capire perché.</div>';
    return;
  }
  list.forEach(m => box.appendChild(renderMatch(m)));
}

function renderMatch(m) {
  const wrap = el("div", "match");
  const top = el("div", "match-top");

  const info = el("div");
  info.appendChild(el("div", "match-title", m.listing?.title || "—"));
  info.appendChild(el("div", "match-co", m.listing?.company_name || ""));
  top.appendChild(info);

  const sc = el("div", "match-score");
  sc.appendChild(el("div", `score-num ${scoreClass(m.score)}`, fmtPct(m.score)));
  sc.appendChild(el("div", "score-cap", `KW ${fmtPct(m.keyword_score)} · AI ${fmtPct(m.semantic_score)}`));
  top.appendChild(sc);

  wrap.appendChild(top);

  // skill
  const matched = parseJSON(m.matched_skills, []);
  const missing = parseJSON(m.missing_skills, []);
  if (matched.length || missing.length) {
    const sk = el("div", "match-skills");
    matched.slice(0, 8).forEach(s => sk.appendChild(el("span", "sk sk-yes", "+ " + s)));
    missing.slice(0, 6).forEach(s => sk.appendChild(el("span", "sk sk-no", "– " + s)));
    wrap.appendChild(sk);
  }

  if (m.gap_analysis) {
    wrap.appendChild(el("div", "match-gap", m.gap_analysis));
  }

  // footer
  const foot = el("div", "match-foot");
  ["cv", "cover_letter", "email"].forEach(dt => {
    const doc = (m.documents || []).find(d => d.doc_type === dt);
    const labels = { cv: "CV", cover_letter: "Lettera", email: "Email" };
    const btn = el("button", "btn btn-ghost", labels[dt]);
    if (!doc) {
      btn.textContent = `${labels[dt]} · rigenera`;
      btn.addEventListener("click", () => regenerateDoc(m.id, dt));
    } else {
      btn.addEventListener("click", () => openDoc(doc, m));
    }
    foot.appendChild(btn);
  });

  const sel = document.createElement("select");
  ["new","saved","applied","interview","rejected"].forEach(v => {
    const opt = document.createElement("option");
    opt.value = v;
    opt.textContent = { new: "Nuovo", saved: "Salvato", applied: "Inviato", interview: "Colloquio", rejected: "Scartato" }[v];
    if (m.status === v) opt.selected = true;
    sel.appendChild(opt);
  });
  sel.addEventListener("change", async () => {
    await patch(`/matches/${m.id}/status`, { status: sel.value });
    toast("Stato aggiornato", "ok");
  });
  foot.appendChild(sel);

  if (m.listing?.source_url) {
    const src = el("div", "match-src");
    const a = document.createElement("a");
    a.href = m.listing.source_url;
    a.target = "_blank";
    a.rel = "noreferrer";
    a.textContent = m.listing.source_board || "annuncio originale";
    src.appendChild(el("span", "", "fonte: "));
    src.appendChild(a);
    foot.appendChild(src);
  }

  wrap.appendChild(foot);
  return wrap;
}

async function regenerateDoc(matchId, docType) {
  toast("Sto rigenerando il documento...", "");
  try {
    await post(`/documents/regenerate/${matchId}`, { doc_type: docType });
    toast("Documento pronto", "ok");
    refreshMatches();
  } catch (e) { toast(e.message, "bad"); }
}

// ---------- Sheet documento ----------
let currentDoc = null;
function openDoc(doc, m) {
  currentDoc = doc;
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
  b.addEventListener("click", () => {
    if (!currentDoc) return;
    window.open(`${API}/documents/${currentDoc.id}/export?fmt=${b.dataset.fmt}`, "_blank");
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
boot();
