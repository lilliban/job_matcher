import { Backdrop, C, Illustration, type IllustrationProps } from "./Illustration";

/**
 * Cartella con le linguette degli stati e una busta che ne esce: le candidature,
 * ancora senza niente da mostrare. Solo oggetti, nessun personaggio.
 */
export function FolderTabs({ className }: IllustrationProps) {
  return (
    <Illustration className={className}>
      <Backdrop />

      {/* retro della cartella con tre linguette */}
      <rect x="32" y="30" width="30" height="16" rx="6" fill={C.deep} />
      <rect x="65" y="34" width="30" height="12" rx="6" fill={C.soft} />
      <rect x="98" y="34" width="30" height="12" rx="6" fill={C.plum} />
      <rect x="32" y="40" width="96" height="64" rx="9" fill={C.mid} />

      {/* busta che esce dalla cartella */}
      <rect x="46" y="48" width="68" height="44" rx="6" fill={C.white} />
      <path d="M50 52 L80 74 L110 52 Z" fill={C.soft} />

      {/* davanti della cartella e due righe di testo */}
      <rect x="28" y="66" width="104" height="40" rx="9" fill={C.deep} />
      <rect x="42" y="80" width="42" height="5" rx="2.5" fill={C.soft} />
      <rect x="42" y="90" width="26" height="5" rx="2.5" fill={C.soft} />
    </Illustration>
  );
}
