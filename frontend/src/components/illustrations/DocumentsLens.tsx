import { Backdrop, C, Illustration, type IllustrationProps } from "./Illustration";

/** Due annunci e una lente che misura la copertura: i tuoi match. */
export function DocumentsLens({ className }: IllustrationProps) {
  return (
    <Illustration className={className}>
      <Backdrop />

      {/* primo annuncio */}
      <rect x="22" y="28" width="56" height="72" rx="8" fill={C.soft} transform="rotate(-8 50 64)" />
      <rect x="30" y="42" width="24" height="6" rx="3" fill={C.mid} transform="rotate(-8 50 64)" />

      {/* secondo annuncio, con barra di copertura */}
      <rect x="56" y="20" width="58" height="76" rx="8" fill={C.white} />
      <rect x="66" y="32" width="28" height="7" rx="3.5" fill={C.deep} />
      <rect x="66" y="46" width="38" height="5" rx="2.5" fill={C.soft} />
      <rect x="66" y="56" width="30" height="5" rx="2.5" fill={C.soft} />
      <rect x="66" y="72" width="38" height="6" rx="3" fill={C.soft} />
      <rect x="66" y="72" width="26" height="6" rx="3" fill={C.deep} />
      <rect x="66" y="84" width="16" height="7" rx="3.5" fill={C.plum} />

      {/* lente */}
      <circle cx="112" cy="78" r="16" fill={C.paper} stroke={C.mid} strokeWidth="6" />
      <rect x="128.7" y="88.2" width="9" height="22" rx="4.5" fill={C.deep} transform="rotate(-45 133.2 99.2)" />
    </Illustration>
  );
}
