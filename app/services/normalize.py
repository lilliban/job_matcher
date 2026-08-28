"""
Estrazione dei campi filtrabili da un annuncio, senza chiamare un LLM.

Ordine di costo, dal più economico:
  1. Il dato arriva già strutturato dal JSON dell'ATS — si usa quello.
  2. Regex sul testo dell'annuncio — gratis, imprecisa ma utile.
  3. LLM — non usato qui, di proposito: la quota è la risorsa scarsa del
     progetto (ADR-003) e questi campi servono a scartare, non a decidere.

Tutto quello che esce da qui è **best-effort**. Un annuncio raccolto via
scraping HTML ha la sede scritta in linguaggio naturale e spesso non ha
affatto gli anni di esperienza. Servono a filtrare e a mostrare, non a
fondarci sopra una decisione automatica.
"""
import json
import re

# ---------------------------------------------------------------------
# Tipo di contratto
# ---------------------------------------------------------------------
_CONTRACT_PATTERNS: list[tuple[str, tuple[str, ...]]] = [
    ("internship", ("intern", "internship", "stage", "tirocinio", "praktikum",
                    "werkstudent", "apprendistato", "apprentice")),
    ("part_time", ("part-time", "part time", "parttime", "teilzeit",
                   "tempo parziale", "temps partiel")),
    ("contract", ("contract", "freelance", "consultant", "partita iva",
                  "p.iva", "interim", "temporary", "a termine", "befristet")),
    ("full_time", ("full-time", "full time", "fulltime", "permanent",
                   "vollzeit", "tempo pieno", "indeterminato", "unbefristet",
                   "temps plein")),
]


def contract_type_norm(*sources: str | None) -> str | None:
    """Normalizza in full_time/part_time/contract/internship.

    L'ordine dei pattern conta: "internship part-time" è prima di tutto uno
    stage, e "permanent" non deve vincere su "part-time" solo perché
    compare prima nel testo."""
    blob = " ".join(s.lower() for s in sources if s)
    if not blob:
        return None
    for norm, keys in _CONTRACT_PATTERNS:
        if any(k in blob for k in keys):
            return norm
    return None


# ---------------------------------------------------------------------
# Modalità di lavoro
# ---------------------------------------------------------------------
def work_mode(*sources: str | None) -> str | None:
    blob = " ".join(s.lower() for s in sources if s)
    if not blob:
        return None
    if any(k in blob for k in ("hybrid", "ibrido", "hybride", "hybrid-remote")):
        return "hybrid"
    if any(k in blob for k in ("fully remote", "100% remote", "remote", "da remoto",
                               "telelavoro", "smart working", "homeoffice",
                               "home office", "télétravail")):
        return "remote"
    if any(k in blob for k in ("on-site", "onsite", "in office", "in sede",
                               "presenza", "vor ort")):
        return "onsite"
    return None


# ---------------------------------------------------------------------
# Anni di esperienza
# ---------------------------------------------------------------------
_RANGE_RE = re.compile(r"(\d{1,2})\s*[-–—/]\s*(\d{1,2})\s*\+?\s*(?:years?|yrs?|anni|jahre|ans)", re.I)
_MIN_RE = re.compile(
    r"(?:at least|minimum(?: of)?|min\.?|almeno|mindestens|au moins|\+)?\s*"
    r"(\d{1,2})\s*\+?\s*(?:years?|yrs?|anni|jahre|ans)",
    re.I,
)


_BARE_RANGE_RE = re.compile(r"^\s*(\d{1,2})\s*[-–—]\s*(\d{1,2})\s*\+?\s*$")


def years_experience(*sources: str | None) -> tuple[int | None, int | None]:
    """(minimo, massimo). Riconosce "3-5 years", "5+ anni", "mindestens 3 Jahre".

    Il PRIMO argomento è trattato come campo strutturato: Personio dichiara
    `yearsOfExperience` come "7-10", senza unità di misura. Lì un intervallo
    nudo è inequivocabile, mentre trovarlo in mezzo al testo di un annuncio
    significherebbe scambiare un "2-3 volte a settimana" per esperienza
    richiesta — per questo il pattern nudo vale solo sul campo dedicato."""
    if sources and sources[0]:
        m = _BARE_RANGE_RE.match(str(sources[0]))
        if m:
            lo, hi = int(m.group(1)), int(m.group(2))
            if lo <= hi <= 50:
                return lo, hi

    for src in sources:
        if not src:
            continue
        m = _RANGE_RE.search(src)
        if m:
            lo, hi = int(m.group(1)), int(m.group(2))
            if lo <= hi <= 50:
                return lo, hi
    for src in sources:
        if not src:
            continue
        m = _MIN_RE.search(src)
        if m:
            v = int(m.group(1))
            if 0 < v <= 50:
                return v, None
    return None, None


# ---------------------------------------------------------------------
# Lingue richieste
# ---------------------------------------------------------------------
_LANGUAGES = {
    "italian": ("italian", "italiano", "italienisch"),
    "english": ("english", "inglese", "englisch", "anglais"),
    "german": ("german", "tedesco", "deutsch", "allemand"),
    "french": ("french", "francese", "französisch", "français"),
    "spanish": ("spanish", "spagnolo", "spanisch", "espagnol", "español"),
    "dutch": ("dutch", "olandese", "niederländisch", "nederlands"),
    "portuguese": ("portuguese", "portoghese", "português"),
}


def languages(*sources: str | None) -> list[str]:
    blob = " ".join(s.lower() for s in sources if s)
    if not blob:
        return []
    return sorted(
        code for code, keys in _LANGUAGES.items() if any(k in blob for k in keys)
    )


# ---------------------------------------------------------------------
# Sede
# ---------------------------------------------------------------------
_COUNTRY_HINTS = {
    "IT": ("italy", "italia", "italien", "milano", "milan", "roma", "rome",
           "torino", "turin", "napoli", "bologna", "firenze", "florence",
           "genova", "venezia", "verona", "padova", "ancona", "bari",
           "palermo", "catania", "brescia", "modena", "parma", "trieste"),
    "CH": ("switzerland", "svizzera", "schweiz", "suisse", "zurich", "zürich",
           "geneva", "genève", "ginevra", "basel", "bern", "lausanne",
           "lugano", "winterthur", "neuchâtel", "chur"),
    "DE": ("germany", "germania", "deutschland", "berlin", "münchen", "munich",
           "hamburg", "frankfurt", "köln", "cologne", "stuttgart", "düsseldorf",
           "leipzig", "dresden", "mannheim", "karlsruhe", "nürnberg"),
    "AT": ("austria", "österreich", "vienna", "wien", "graz", "linz",
           "salzburg", "innsbruck"),
    "FR": ("france", "francia", "paris", "lyon", "marseille", "toulouse",
           "bordeaux", "lille", "nantes", "nice", "strasbourg"),
    "ES": ("spain", "spagna", "españa", "madrid", "barcelona", "valencia",
           "sevilla", "bilbao", "málaga", "zaragoza"),
    "UK": ("united kingdom", "england", "scotland", "wales", "london",
           "manchester", "birmingham", "edinburgh", "glasgow", "bristol",
           "leeds", "cambridge", "oxford"),
    "US": ("united states", "usa", "stati uniti", "new york", "san francisco",
           "boston", "chicago", "seattle", "austin", "denver", "atlanta",
           "los angeles", "pittsburgh", "wichita", "texas", "california"),
    "NL": ("netherlands", "olanda", "paesi bassi", "amsterdam", "rotterdam",
           "utrecht", "eindhoven", "den haag", "the hague"),
    "IE": ("ireland", "irlanda", "dublin", "dublino", "cork"),
    "BE": ("belgium", "belgio", "brussels", "bruxelles", "antwerp", "gent"),
    "PT": ("portugal", "portogallo", "lisbon", "lisbona", "porto"),
    "PL": ("poland", "polonia", "warsaw", "varsavia", "krakow", "wrocław"),
}


def country_code(location: str | None) -> str | None:
    """Indovina il paese dalla stringa della sede.

    Grossolano di proposito: la sede degli annunci è testo libero e a volte
    elenca più città ("Karlsruhe, Köln, München"). Basta il primo indizio
    riconosciuto — serve a scartare un annuncio americano da una ricerca
    italiana, non a fare geocodifica."""
    if not location:
        return None
    low = location.lower()
    for code, hints in _COUNTRY_HINTS.items():
        if any(h in low for h in hints):
            return code
    return None


def city(location: str | None) -> str | None:
    """Primo segmento della sede, che nella stragrande maggioranza dei
    formati ("Milano, Lombardia, Italia") è la città."""
    if not location:
        return None
    first = location.split(",")[0].strip()
    return first[:80] or None


# ---------------------------------------------------------------------
# Stipendio
# ---------------------------------------------------------------------
_SALARY_RE = re.compile(
    r"(?P<cur>[€$£]|eur|usd|gbp|chf)?\s*"
    r"(?P<lo>\d{2,3}(?:[.,]\d{3})+|\d{2,3})\s*(?:k\b)?"
    r"\s*(?:-|–|to|a)\s*"
    r"(?P<cur2>[€$£]|eur|usd|gbp|chf)?\s*"
    r"(?P<hi>\d{2,3}(?:[.,]\d{3})+|\d{2,3})\s*(?:k\b)?"
    # la valuta può stare anche in coda: in italiano si scrive più spesso
    # "RAL 35.000 - 45.000 EUR" che "EUR 35.000 - 45.000"
    r"\s*(?P<cur3>[€$£]|eur|usd|gbp|chf)?",
    re.I,
)
_CURRENCY_MAP = {"€": "EUR", "$": "USD", "£": "GBP"}


def salary(*sources: str | None) -> tuple[int | None, int | None, str | None]:
    """Range di stipendio, solo quando è dichiarato in modo inequivocabile.

    Volutamente conservativa: preferisce non trovare nulla piuttosto che
    scambiare "500-1000 clienti" per una retribuzione. Per questo pretende
    un simbolo di valuta e un valore in un intervallo plausibile."""
    for src in sources:
        if not src:
            continue
        for m in _SALARY_RE.finditer(src):
            cur_raw = (m.group("cur") or m.group("cur2") or m.group("cur3") or "").lower()
            if not cur_raw:
                continue
            cur = _CURRENCY_MAP.get(cur_raw, cur_raw.upper())
            lo = int(re.sub(r"[.,]", "", m.group("lo")))
            hi = int(re.sub(r"[.,]", "", m.group("hi")))
            if lo < 1000:   # notazione "45k - 60k"
                lo, hi = lo * 1000, hi * 1000
            if 5_000 <= lo <= hi <= 1_000_000:
                return lo, hi, cur
    return None, None, None


# ---------------------------------------------------------------------
def enrich(item: dict) -> dict:
    """Aggiunge a un annuncio i campi normalizzati.

    `item` è il dizionario prodotto da un connettore ATS o dallo scraper.
    I valori già presenti (perché l'ATS li dichiarava) hanno la precedenza
    su quelli indovinati dal testo: un campo strutturato batte sempre una
    regex."""
    text = " ".join(
        str(item.get(k) or "") for k in ("title", "description", "requirements_raw")
    )
    loc = item.get("location")

    lo, hi = years_experience(item.get("seniority"), text)
    sal_lo, sal_hi, cur = salary(text)

    item["contract_type_norm"] = contract_type_norm(item.get("contract_type"), text)
    item["work_mode"] = item.get("work_mode") or work_mode(loc, text)
    item["min_years_exp"] = lo
    item["max_years_exp"] = hi
    item["languages"] = json.dumps(languages(text)) if languages(text) else None
    item["city"] = city(loc)
    item["country_code"] = country_code(loc)
    item["salary_min"] = sal_lo
    item["salary_max"] = sal_hi
    item["salary_currency"] = cur
    return item
