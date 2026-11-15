import { Backdrop, C, Illustration, type IllustrationProps } from "./Illustration";

/** Documento con spunta: il profilo. */
export function DocumentCheck({ className }: IllustrationProps) {
  return (
    <Illustration className={className}>
      <Backdrop />

      {/* foglio dietro e foglio davanti */}
      <rect x="56" y="24" width="60" height="82" rx="8" fill={C.soft} />
      <rect x="44" y="16" width="60" height="82" rx="8" fill={C.white} />
      <rect x="54" y="28" width="32" height="7" rx="3.5" fill={C.deep} />
      <rect x="54" y="42" width="40" height="5" rx="2.5" fill={C.soft} />
      <rect x="54" y="52" width="32" height="5" rx="2.5" fill={C.soft} />
      <rect x="54" y="62" width="36" height="5" rx="2.5" fill={C.soft} />
      <rect x="54" y="76" width="20" height="8" rx="4" fill={C.plum} />

      {/* spunta */}
      <circle cx="106" cy="88" r="17" fill={C.deep} />
      <path
        d="M98 88.5 L104 94.5 L115 82.5"
        fill="none"
        stroke={C.white}
        strokeWidth="5"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </Illustration>
  );
}
