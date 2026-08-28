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
* **Python 3.11** o superiore
* **~500 MB** di spazio libero per Ollama, se lo usi

### Passi per l'avvio

1. Estrai lo zip e apri il terminale nella cartella:
   ```bash
   cd job_matcher



# Crea un virtual environment e installa le dipendenze:

## macOS/Linux:

python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

## Windows:

python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt


# Configura le chiavi API creando il file .env:

macOS/Linux: cp .env.example .env

Windows: copy .env.example .env

Poi apri .env e imposta almeno una di queste opzioni:

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


python run.py
Apri il browser su http://localhost:8000

# Struttura del progetto
Plaintext
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
├── frontend/
│   ├── index.html
│   ├── style.css
│   ├── roles.js                # Catalogo ruoli statico per autocomplete
│   └── app.js                  # SPA vanilla JavaScript
├── output/                     # Cartella documenti esportati (PDF/DOCX/MD/TXT)
├── scripts/
│   ├── migrate.py              # Migrazioni database
│   └── seed_collections.py     # Dati iniziali per collezioni aziende
├── tests/                      # Test unitari
├── .env                        # Configurazione chiavi API (non tracciato)
├── .env.example                # Esempio di configurazione
├── README.md
├── requirements.txt
└── run.py                      # Entry point di avvio


# Note sulla legalità
Il sistema effettua scraping su portali pubblici per esclusivo uso personale. Per utilizzi differenti o commerciali, si raccomanda di verificare i Terms of Service delle singole piattaforme e di utilizzare API ufficiali dove disponibili.   