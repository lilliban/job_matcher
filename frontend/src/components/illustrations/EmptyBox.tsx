import { Backdrop, C, Illustration, type IllustrationProps } from "./Illustration";

/** Scatola aperta e vuota: nessun annuncio. */
export function EmptyBox({ className }: IllustrationProps) {
  return (
    <Illustration className={className}>
      <Backdrop />

      {/* due puntini sospesi: dentro non c'è niente */}
      <circle cx="74" cy="30" r="5" fill={C.plum} />
      <circle cx="92" cy="22" r="3.5" fill={C.white} />

      {/* lembi aperti */}
      <rect x="22" y="44" width="38" height="14" rx="5" fill={C.soft} transform="rotate(-18 41 51)" />
      <rect x="100" y="44" width="38" height="14" rx="5" fill={C.soft} transform="rotate(18 119 51)" />

      {/* bordo dell'apertura e corpo */}
      <rect x="42" y="50" width="76" height="14" rx="5" fill={C.mid} />
      <rect x="40" y="58" width="80" height="46" rx="8" fill={C.deep} />
      <rect x="66" y="74" width="28" height="8" rx="4" fill={C.white} />
    </Illustration>
  );
}
