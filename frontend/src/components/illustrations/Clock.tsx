import { Backdrop, C, Illustration, type IllustrationProps } from "./Illustration";

/** Orologio: lo storico delle ricerche, ancora senza niente da mostrare. */
export function Clock({ className }: IllustrationProps) {
  return (
    <Illustration className={className}>
      <Backdrop />

      {/* cassa e quadrante */}
      <circle cx="80" cy="62" r="40" fill={C.mid} />
      <circle cx="80" cy="62" r="32" fill={C.white} />

      {/* tacche delle ore 12, 3, 6, 9 */}
      <rect x="77" y="34" width="6" height="8" rx="3" fill={C.soft} />
      <rect x="77" y="82" width="6" height="8" rx="3" fill={C.soft} />
      <rect x="100" y="59" width="8" height="6" rx="3" fill={C.soft} />
      <rect x="52" y="59" width="8" height="6" rx="3" fill={C.soft} />

      {/* lancette */}
      <rect x="77" y="45" width="6" height="20" rx="3" fill={C.deep} />
      <rect x="77" y="59" width="6" height="24" rx="3" fill={C.mid} transform="rotate(-60 80 62)" />
      <circle cx="80" cy="62" r="5" fill={C.plum} />

      {/* campanelle */}
      <rect x="48" y="18" width="18" height="10" rx="5" fill={C.deep} transform="rotate(-30 57 23)" />
      <rect x="94" y="18" width="18" height="10" rx="5" fill={C.deep} transform="rotate(30 103 23)" />
    </Illustration>
  );
}
