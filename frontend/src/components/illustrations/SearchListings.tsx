import { Backdrop, C, Illustration, type IllustrationProps } from "./Illustration";

/** Lente su un annuncio: lanciare una ricerca. */
export function SearchListings({ className }: IllustrationProps) {
  return (
    <Illustration className={className}>
      <Backdrop />

      {/* annuncio dietro, inclinato */}
      <rect x="30" y="20" width="62" height="80" rx="8" fill={C.soft} transform="rotate(-8 61 60)" />
      {/* annuncio davanti */}
      <rect x="44" y="22" width="62" height="80" rx="8" fill={C.white} />
      <rect x="54" y="34" width="30" height="7" rx="3.5" fill={C.deep} />
      <rect x="54" y="48" width="42" height="5" rx="2.5" fill={C.soft} />
      <rect x="54" y="58" width="34" height="5" rx="2.5" fill={C.soft} />
      <rect x="54" y="68" width="38" height="5" rx="2.5" fill={C.soft} />
      <rect x="54" y="84" width="20" height="9" rx="4.5" fill={C.plum} />

      {/* lente */}
      <circle cx="110" cy="70" r="20" fill={C.paper} stroke={C.mid} strokeWidth="7" />
      <rect x="101" y="60" width="9" height="4" rx="2" fill={C.white} transform="rotate(-45 105.5 62)" />
      <rect x="126" y="86" width="10" height="28" rx="5" fill={C.deep} transform="rotate(-45 131 100)" />
    </Illustration>
  );
}
