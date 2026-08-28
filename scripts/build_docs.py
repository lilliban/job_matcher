"""
Genera la documentazione di architettura dai dati raccolti sul codice.

    python scripts/build_docs.py <journal.jsonl>

Produce due file in docs/:
  ARCHITETTURA-TECNICA.md      — ogni classe e ogni funzione, per chi sviluppa
  ARCHITETTURA-PANORAMICA.md   — a cosa serve ogni pezzo, per chi non programma

Rigenerabile: i due documenti sono derivati, non si modificano a mano. Se il
codice cambia, si rilancia l'analisi e poi questo script.
"""
import json
import sys
from collections import OrderedDict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"

# ordine di lettura: dalle fondamenta verso l'esterno
ORDINE = [
    "Configurazione", "Modello dati", "Schemi", "Gateway LLM", "Scraper",
    "Connettori ATS", "Orchestratore", "Router", "Frontend",
]


def sort_key(titolo: str) -> int:
    for i, k in enumerate(ORDINE):
        if k.lower() in titolo.lower():
            return i
    return len(ORDINE)


def load(journal: Path) -> list[dict]:
    out = []
    for line in journal.read_text(encoding="utf-8").splitlines():
        try:
            d = json.loads(line)
        except json.JSONDecodeError:
            continue
        if d.get("type") != "result":
            continue
        r = d.get("result")
        if isinstance(r, str):
            try:
                r = json.loads(r)
            except json.JSONDecodeError:
                continue
        if isinstance(r, dict) and "simboli" in r:
            out.append(r)
    out.sort(key=lambda r: sort_key(r.get("sottosistema", "")))
    return out


def anchor(s: str) -> str:
    keep = "".join(c if c.isalnum() or c in " -" else "" for c in s.lower())
    return keep.strip().replace(" ", "-")


TIPO_ORDINE = ["classe", "modello-dati", "schema-pydantic", "endpoint",
               "funzione", "metodo", "costante"]


def build_tecnica(parti: list[dict]) -> str:
    n_sym = sum(len(p["simboli"]) for p in parti)
    L = [
        "# JobMatcher — Architettura tecnica",
        "",
        "> Documento generato da `scripts/build_docs.py`. Non modificarlo a mano:",
        "> le modifiche vanno fatte al codice e poi rigenerate.",
        "",
        f"Copre **{len(parti)} sottosistemi** e **{n_sym} tra classi, funzioni e metodi**.",
        "Per il contesto delle scelte progettuali vedi [DECISIONS.md](DECISIONS.md);",
        "per la versione non tecnica vedi [ARCHITETTURA-PANORAMICA.md](ARCHITETTURA-PANORAMICA.md).",
        "",
        "---",
        "",
        "## Come è fatto il sistema, in breve",
        "",
        "JobMatcher è un'applicazione web che gira in locale. Un backend Python",
        "(FastAPI) espone un'API REST; un frontend a pagina singola in JavaScript",
        "senza framework la consuma. I dati stanno in un unico file SQLite. Le",
        "operazioni che richiedono capacità linguistiche — leggere un CV, capire",
        "un annuncio, scrivere una lettera — passano da un gateway che nasconde",
        "quale modello risponda (Gemini o Ollama) e che mette in cache ogni",
        "risposta.",
        "",
        "La ricerca vera e propria è un'operazione lunga: parte in background e il",
        "frontend ne segue l'avanzamento interrogando periodicamente lo stato.",
        "",
        "### Il percorso di una ricerca, dall'inizio alla fine",
        "",
        "```",
        "  utente definisce una ricerca (ruolo, geografia, soglia, aziende)",
        "        |",
        "        v",
        "  POST /run  ->  risposta immediata, il lavoro continua in background",
        "        |",
        "        v",
        "  PER OGNI AZIENDA TARGET, in ordine di costo crescente:",
        "     1. cache      annunci raccolti di recente -> nessuna rete",
        "     2. ATS        feed JSON pubblico          -> nessuna chiamata LLM",
        "     3. scraping   pagina carriere + parsing LLM (percorso storico)",
        "        |",
        "        v",
        "  POI I PORTALI GENERALISTI, tutti in parallelo (uno per host)",
        "        |",
        "        v",
        "  PER OGNI ANNUNCIO RACCOLTO:",
        "     dedup per content_hash",
        "     -> salvato una volta sola in job_postings (globale)",
        "     -> agganciato alla sessione via job_listings",
        "     -> punteggio keyword (gratis)",
        "     -> se supera il pre-filtro: valutazione semantica LLM",
        "     -> se supera la soglia: CV + lettera + email su misura",
        "        |",
        "        v",
        "  risultati, resoconto, documenti scaricabili",
        "```",
        "",
        "### Indice",
        "",
    ]
    for p in parti:
        L.append(f"- [{p['sottosistema']}](#{anchor(p['sottosistema'])})"
                 f" — {len(p['simboli'])} simboli")
    L += ["", "---", ""]

    for p in parti:
        L += [f"## {p['sottosistema']}", "", p["ruolo"], "",
              "### Come funziona", "", p["flusso"], ""]

        if p.get("dipendenze"):
            L += ["### Da cosa dipende", ""]
            L += [f"- {d}" for d in p["dipendenze"]]
            L.append("")

        gruppi: OrderedDict[str, list] = OrderedDict()
        for s in p["simboli"]:
            gruppi.setdefault(s.get("tipo", "altro"), []).append(s)
        for tipo in sorted(gruppi, key=lambda t: (
                TIPO_ORDINE.index(t) if t in TIPO_ORDINE else 99, t)):
            L += [f"### {tipo.replace('-', ' ').capitalize()}", ""]
            for s in gruppi[tipo]:
                L.append(f"#### `{s['nome']}`")
                L.append("")
                L.append(f"*{s['posizione']}*")
                L.append("")
                if s.get("firma"):
                    L += ["```python", s["firma"], "```", ""]
                L += [s["cosa_fa"], ""]
                if s.get("note", "").strip():
                    L += [f"> **Da sapere.** {s['note']}", ""]

        if p.get("limitazioni"):
            L += ["### Limiti di questo sottosistema", ""]
            L += [f"- {x}" for x in p["limitazioni"]]
            L.append("")
        L += ["---", ""]

    return "\n".join(L)


def build_panoramica(parti: list[dict]) -> str:
    L = [
        "# JobMatcher — Come funziona, in parole semplici",
        "",
        "> Documento generato da `scripts/build_docs.py`.",
        "> Versione per chi non programma. La controparte tecnica, con ogni",
        "> classe e funzione, è in [ARCHITETTURA-TECNICA.md](ARCHITETTURA-TECNICA.md).",
        "",
        "## Che problema risolve",
        "",
        "Cercare lavoro significa ripetere ogni giorno lo stesso lavoro manuale:",
        "aprire dieci portali, leggere decine di annunci, capire quali valgono la",
        "pena, e per ognuno riscrivere il CV e la lettera adattandoli all'azienda.",
        "È un lavoro ripetitivo che consuma le energie che servirebbero per i",
        "colloqui.",
        "",
        "JobMatcher automatizza la parte ripetitiva. L'utente descrive una volta",
        "chi è e cosa cerca; il sistema va a cercare, misura quanto ogni offerta",
        "sia compatibile col suo profilo, e per le offerte buone prepara già CV,",
        "lettera di presentazione ed email, ciascuno adattato a quella specifica",
        "azienda.",
        "",
        "## I quattro passaggi che vede l'utente",
        "",
        "1. **Profilo** — dati, esperienze, formazione, competenze. Si può",
        "   caricare un CV in PDF e il sistema ne ricava tutto da solo. Quel CV",
        "   diventa il documento di partenza da cui derivano tutte le versioni",
        "   personalizzate.",
        "2. **Aziende** — liste tematiche di aziende di interesse, come bacheche.",
        "   Da una lista il sistema sa proporre aziende simili.",
        "3. **Ricerca** — ruolo, area geografica, tipo di contratto, e la soglia",
        "   minima di compatibilità sotto la quale un annuncio viene scartato.",
        "4. **Risultati** — le offerte trovate con il loro punteggio, i documenti",
        "   già pronti, e un resoconto che spiega *perché* i risultati sono quelli:",
        "   quali competenze mancano più spesso, quali aziende non hanno posizioni",
        "   aperte.",
        "",
        "## Le tre idee che reggono il sistema",
        "",
        "**Chiedere all'intelligenza artificiale solo quando serve davvero.**",
        "Ogni domanda a un modello linguistico costa. Il sistema usa prima i",
        "metodi gratuiti — confronto di parole chiave, dati già strutturati — e",
        "chiama il modello solo su ciò che è sopravvissuto a quel primo filtro.",
        "Ogni risposta viene inoltre memorizzata: la stessa domanda non viene mai",
        "pagata due volte.",
        "",
        "**Preferire i dati strutturati allo scraping.** Molte aziende pubblicano",
        "le proprie posizioni aperte in un formato che i motori di ricerca possono",
        "leggere. Quando esiste, il sistema usa quello: è più veloce, più preciso",
        "e legalmente più solido che leggere le pagine web. Solo quando non esiste",
        "si ripiega sulla lettura della pagina.",
        "",
        "**Ricordare invece di rifare.** Il sistema tiene un archivio di ciò che",
        "ha già scoperto — dove un'azienda pubblica le sue offerte, quali offerte",
        "erano attive, quando le ha viste l'ultima volta. Una seconda ricerca",
        "sulla stessa azienda non ricomincia da capo.",
        "",
        "## I pezzi del sistema",
        "",
    ]
    for p in parti:
        L += [f"### {p['sottosistema'].split('(')[0].strip()}", "",
              p["per_manager"], ""]

    L += [
        "## Cosa il sistema NON fa, e va detto",
        "",
        "- **Non si candida al posto tuo.** Prepara i documenti; inviare la",
        "  candidatura resta una scelta e un'azione della persona.",
        "- **Non garantisce di trovare tutte le offerte esistenti.** Vede quello",
        "  che le fonti configurate espongono. Alcuni grandi portali bloccano",
        "  attivamente l'accesso automatico.",
        "- **Non verifica che le aziende suggerite stiano assumendo.** Una lista",
        "  di aziende è un elenco di desideri finché il sistema non va a vedere.",
        "- **Non è multiutente.** È pensato per girare sul computer di una",
        "  persona. Aprirlo a più utenti richiede un lavoro di infrastruttura che",
        "  oggi non c'è.",
        "",
        "## Costi e rischi in sintesi",
        "",
        "| | |",
        "|---|---|",
        "| Costo di esercizio | Zero. Nessun abbonamento: si usa il livello gratuito di Google Gemini, con un modello locale come riserva. |",
        "| Infrastruttura | Nessuna. Un file di database, nessun server da gestire. |",
        "| Rischio principale | La copertura delle fonti. Per l'Italia oggi funziona di fatto un solo portale. |",
        "| Secondo rischio | Il limite giornaliero di richieste gratuite all'intelligenza artificiale. |",
        "| Terzo rischio | Nessun test automatico: ogni verifica è manuale. |",
        "",
        "L'elenco completo e onesto di limiti e sviluppi futuri è nella sezione",
        "finale di [DECISIONS.md](DECISIONS.md).",
        "",
    ]
    return "\n".join(L)


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    parti = load(Path(sys.argv[1]))
    if not parti:
        print("Nessun dato trovato nel journal.")
        return 1

    DOCS.mkdir(exist_ok=True)
    t = DOCS / "ARCHITETTURA-TECNICA.md"
    p = DOCS / "ARCHITETTURA-PANORAMICA.md"
    t.write_text(build_tecnica(parti), encoding="utf-8")
    p.write_text(build_panoramica(parti), encoding="utf-8")

    n = sum(len(x["simboli"]) for x in parti)
    lim = sum(len(x.get("limitazioni", [])) for x in parti)
    print(f"{t.relative_to(ROOT)}      {len(t.read_text(encoding='utf-8')):>7,} char")
    print(f"{p.relative_to(ROOT)}   {len(p.read_text(encoding='utf-8')):>7,} char")
    print(f"\n{len(parti)} sottosistemi, {n} simboli, {lim} limitazioni raccolte.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
