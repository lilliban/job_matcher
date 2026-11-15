/*
 * Soft skill: la stessa capacità arriva spesso ripetuta (più import del CV)
 * o in due lingue ("Critical Thinking" e "Pensiero critico"). Qui la si
 * riconduce a un nome solo, in italiano come nel catalogo del backend.
 * Vale per la vista e per ciò che il frontend salva; i dati già nel
 * database restano come sono.
 */
const SYNONYMS: Record<string, string> = {
  "problem solving": "Problem solving",
  "problem-solving": "Problem solving",
  "risoluzione dei problemi": "Problem solving",
  "critical thinking": "Pensiero critico",
  "pensiero critico": "Pensiero critico",
  "detail oriented": "Attenzione ai dettagli",
  "detailed oriented": "Attenzione ai dettagli",
  "detail-oriented": "Attenzione ai dettagli",
  "attention to detail": "Attenzione ai dettagli",
  "attenzione ai dettagli": "Attenzione ai dettagli",
  teamwork: "Lavoro in team",
  "team work": "Lavoro in team",
  "team player": "Lavoro in team",
  "lavoro di squadra": "Lavoro in team",
  "lavoro in team": "Lavoro in team",
  communication: "Comunicazione",
  "communication skills": "Comunicazione",
  comunicazione: "Comunicazione",
  "time management": "Gestione del tempo",
  "gestione del tempo": "Gestione del tempo",
  adaptability: "Adattabilità",
  flexibility: "Adattabilità",
  "adattabilità": "Adattabilità",
  "flessibilità": "Adattabilità",
  creativity: "Creatività",
  "creatività": "Creatività",
  leadership: "Leadership",
  autonomy: "Autonomia",
  independence: "Autonomia",
  autonomia: "Autonomia",
  "stress management": "Gestione dello stress",
  "gestione dello stress": "Gestione dello stress",
  negotiation: "Negoziazione",
  negoziazione: "Negoziazione",
  "result orientation": "Orientamento al risultato",
  "results oriented": "Orientamento al risultato",
  "results-oriented": "Orientamento al risultato",
  "orientamento al risultato": "Orientamento al risultato",
  "active listening": "Ascolto attivo",
  "ascolto attivo": "Ascolto attivo",
  "continuous learning": "Apprendimento continuo",
  "fast learning": "Apprendimento continuo",
  "fast learner": "Apprendimento continuo",
  "quick learner": "Apprendimento continuo",
  "apprendimento continuo": "Apprendimento continuo",
  "agile mindset": "Mentalità agile",
  "mentalità agile": "Mentalità agile",
};

/** Nome unico della skill: il sinonimo italiano se lo conosco, altrimenti il nome ripulito. */
export function canonicalSoftSkill(name: string): string {
  const clean = name.trim().replace(/\s+/g, " ");
  return SYNONYMS[clean.toLowerCase()] ?? clean;
}

/** Chiave di confronto: due skill con la stessa chiave sono la stessa skill. */
export function softSkillKey(name: string): string {
  return canonicalSoftSkill(name).toLowerCase();
}

/** Lista senza doppioni né coppie inglese/italiano, nell'ordine originale. */
export function dedupeSoftSkills(names: string[]): string[] {
  const seen = new Set<string>();
  const out: string[] = [];
  for (const n of names) {
    if (!n || !n.trim()) continue;
    const k = softSkillKey(n);
    if (seen.has(k)) continue;
    seen.add(k);
    out.push(canonicalSoftSkill(n));
  }
  return out;
}
