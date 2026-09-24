# JobMatcher

Cerca lavoro su portali e careers page aziendali, calcola quanto ogni annuncio è compatibile con il tuo profilo, e per ogni buon match genera CV, lettera di presentazione ed email, tutto su misura per quella specifica offerta.

**Costo di esercizio:** zero. Nessun abbonamento, tutto gira in locale, gli LLM usano il free tier di Google Gemini con fallback su Ollama.

---

## Come funziona in 30 secondi

1. **Compili il profilo una volta:** dati anagrafici, esperienze, formazione, skill tecniche, soft skill, lingue.
2. **Carichi il CV in PDF:** il sistema estrae i dati e ti propone cosa aggiungere al profilo.
3. **Crei una ricerca:** un ruolo, paese, zona, soglia di compatibilità.
4. **Aggiungi aziende target:** puoi cercarle per nome o per zona geografica.
5. **Premi Cerca:** il sistema interroga i portali del paese scelto e le careers page delle aziende target. Per ogni annuncio calcola uno score di match e, se supera la soglia, genera CV, lettera ed email.
6. **Consulti il Resoconto:** anche quando i match sono pochi, ti dice perché: quali skill mancano più spesso, quali aziende non hanno posizioni aperte, quali ruoli alternativi hanno più mercato per il tuo profilo.

---

## Installazione

### Requisiti
* **Python 3.11** o superiore (testato con 3.13)
* **Node.js 18** o superiore (per compilare il frontend React)
* **~500 MB** di spazio libero per Ollama, se lo usi

### Passi per l'avvio

1. Estrai lo zip e apri il terminale nella cartella:
   ```bash
   cd job_matcher
   ```

2. **Backend Python** — crea un virtual environment e installa le dipendenze:

   macOS/Linux:
   ```bash
   python -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```

   Windows:
   ```powershell
   python -m venv .venv
   .venv\Scripts\activate
   pip install -r requirements.txt
   ```

3. **Frontend React** — installa i pacchetti e compila la build di produzione:

   ```bash
   cd frontend
   npm install
   npm run build
   cd ..
   ```

   Il backend serve automaticamente la build compilata da `frontend/dist/`.

4. Configura le chiavi API creando il file `.env`:

   macOS/Linux: `cp .env.example .env`

   Windows: `copy .env.example .env`

Poi apri `.env` e imposta almeno una di queste opzioni:

## Opzione A — Gemini (consigliata):

Vai su Google AI Studio.

Fai login con Google e clicca Create API Key.

Copia la chiave e incollala in .env alla riga GEMINI_API_KEY=. (1500 richieste gratis al giorno).

## Opzione B — Ollama (offline, zero registrazioni):

Installa Ollama da ollama.com.

Scarica un modello: ollama pull llama3

Avvia il servizio: ollama serve

Lascia GEMINI_API_KEY vuoto in .env.

(Puoi configurarle entrambe: Gemini è più veloce, Ollama subentra automaticamente se Gemini non risponde).

# Avvia l'app:

```bash
python run.py
```

Apri il browser su http://localhost:8000

### Sviluppo con hot reload (backend + frontend)

**Windows (one-shot):**

```powershell
.\dev.ps1
```

Apre due finestre (backend con `RELOAD=1`, frontend con `npm run dev`) e il browser
su http://localhost:5173. Modifiche a `.py` in `app/` → uvicorn ricarica; modifiche
a `.tsx`/`.css` → Vite HMR aggiorna in <1s.

**A mano (macOS/Linux/Windows):**

```bash
# Terminale 1 — backend con reload
RELOAD=1 python run.py
# Windows PowerShell:  $env:RELOAD="1"; python run.py

# Terminale 2 — frontend con HMR
cd frontend
npm run dev
```

Apri http://localhost:5173 (Vite proxya `/api` su :8000).

### Test

Suite di regressione automatica (pytest + Playwright):

```bash
pip install -r requirements-dev.txt
python -m playwright install chromium
# Poi (Windows):
.\Claude\scripts\run-regression.ps1
# Oppure a mano:
python run.py &  # in background
python -m pytest tests/api tests/e2e -v
```

## PostgreSQL (opzionale)

Di default il progetto usa SQLite (`job_matcher.db`), zero setup. Per
collegare strumenti come Power BI o pgAdmin/DBeaver, o semplicemente per
avere un database "vero" in locale, si può passare a PostgreSQL — il
backend è già pronto (`DATABASE_URL` è l'unica cosa che cambia).

1. **Avvia Postgres in Docker** (serve Docker Desktop attivo):
   ```bash
   docker compose up -d
   ```
   Crea un container `job_matcher_postgres` su `localhost:5432` con
   utente/password/db `job_matcher` (vedi `docker-compose.yml`), con i
   dati persistiti in un volume Docker (sopravvivono a `docker compose down`).

2. **Punta l'app a Postgres**: nel tuo `.env`, imposta
   ```
   DATABASE_URL=postgresql+psycopg://job_matcher:job_matcher@localhost:5432/job_matcher
   ```

3. **Migra i dati esistenti** da `job_matcher.db` (profilo, ricerche già
   fatte, match, documenti):
   ```bash
   python scripts/migrate_sqlite_to_postgres.py
   ```
   Lo script è rilanciabile senza rischi se si interrompe a metà (fa
   upsert per riga, non duplica nulla).

4. **Avvia normalmente**: `python run.py` — ora legge/scrive su Postgres.

Per tornare a SQLite basta rimettere `DATABASE_URL=sqlite:///job_matcher.db`
(o commentare la riga) nel `.env`: `job_matcher.db` non viene mai toccato
dalla migrazione, resta come backup.

### Esplorare il database

- **DBeaver** (gratis, multi-DB — funziona sia con SQLite che con
  Postgres): connessione a `localhost:5432`, db `job_matcher`, utente e
  password `job_matcher`.
- **pgAdmin**: incluso se installi Postgres nativamente invece che via
  Docker; altrimenti scaricabile a parte.

### Collegare Power BI

Power BI Desktop → **Recupera dati** → **Database PostgreSQL** → host
`localhost`, database `job_matcher`. Serve il provider **Npgsql**
installato una tantum su Windows (Power BI lo richiede al primo utilizzo
del connettore PostgreSQL e offre il link per scaricarlo). Con SQLite
questo passaggio non è altrettanto pulito — è uno dei motivi per cui
conviene Postgres se l'obiettivo è collegare Power BI.

## Struttura del progetto

```text
job_matcher/
├── app/
│   ├── core/
│   │   ├── config.py           # Configurazione e dizionario job board per paese
│   │   └── security.py         # Verifica token API
│   ├── data/
│   │   └── geo.json            # Dati geografici: paesi, continenti, regioni
│   ├── models/
│   │   └── domain.py           # Entità: User, Session, Company, Listing, Match
│   ├── schemas/
│   │   └── schemas.py          # Pydantic per validazione request/response
│   ├── routers/
│   │   ├── users.py            # Profilo, skill, esperienze, lingue, import CV
│   │   ├── skills.py           # Catalogo soft skill e suggerimenti simili
│   │   ├── sessions.py         # Ricerche, esecuzione background, stato
│   │   ├── companies.py        # Discovery aziende e suggerimenti
│   │   ├── matches.py          # Tracking stato candidature
│   │   ├── documents.py        # Export PDF/DOCX e rigenerazione
│   │   ├── collections.py      # Liste aziende raggruppate per tema
│   │   └── geo.py              # Endpoint per i dati geografici
│   ├── services/
│   │   ├── llm_gateway.py      # Gateway unificato: Gemini + fallback Ollama
│   │   ├── matcher.py          # Score ibrido: keyword + semantico con LLM
│   │   ├── scraper.py          # Rotazione user-agent, rate limit, LLM parsing
│   │   ├── doc_generator.py    # Generazione CV, lettera, email con template
│   │   ├── cv_parser.py        # Estrazione dati da CV PDF con LLM
│   │   ├── company_discovery.py# Pipeline aziende: LLM + Places API
│   │   ├── search_runner.py    # Orchestratore asincrono
│   │   └── geo.py              # Gestione regioni
│   ├── database.py             # SQLite + SQLAlchemy
│   └── main.py                 # Entry point FastAPI
├── frontend/                   # SPA React + Vite + TypeScript + Tailwind v4
│   ├── package.json
│   ├── vite.config.ts
│   ├── tsconfig.json
│   ├── index.html
│   ├── src/
│   │   ├── main.tsx            # entry React
│   │   ├── router.tsx          # rotte React Router (profile/collections/sessions/intelligence)
│   │   ├── api/                # client HTTP, tipi generati da OpenAPI, hook TanStack Query
│   │   ├── components/
│   │   │   ├── AppLayout.tsx   # rail sidebar + stage
│   │   │   └── ui/             # componenti shadcn/ui (Button, Card, Input, Badge, ...)
│   │   ├── hooks/              # useCurrentUser, useHealth
│   │   ├── stores/             # Zustand (userId, sessionId in localStorage)
│   │   ├── styles/             # tokens.css (Tailwind @theme)
│   │   └── views/              # 4 view + sotto-componenti per pannello
│   └── dist/                   # build compilata (servita da FastAPI in produzione)
├── output/                     # Cartella documenti esportati (PDF/DOCX/MD/TXT)
├── scripts/
│   ├── migrate.py              # Migrazioni database
│   └── seed_collections.py     # Dati iniziali per collezioni aziende
├── tests/
│   ├── api/                    # Smoke test API (pytest + FastAPI TestClient)
│   ├── e2e/                    # End-to-end frontend (Playwright)
│   ├── conftest.py             # Fixture pytest (DB isolato, TestClient, auth headers)
│   └── test_*.py               # Test unitari esistenti (normalize, schema, lock)
├── .env                        # Configurazione chiavi API (non tracciato)
├── .env.example                # Esempio di configurazione
├── README.md
├── pyproject.toml              # Config ruff/black/pytest
├── requirements.txt            # Dipendenze runtime
├── requirements-dev.txt        # Dipendenze dev (pytest, ruff, playwright)
└── run.py                      # Entry point di avvio
```

# Note sulla legalità
Il sistema effettua scraping su portali pubblici per esclusivo uso personale. Per utilizzi differenti o commerciali, si raccomanda di verificare i Terms of Service delle singole piattaforme e di utilizzare API ufficiali dove disponibili.   