import { Backdrop, C, Illustration, type IllustrationProps } from "./Illustration";

/** Tre edifici stilizzati: la lista delle aziende. */
export function Buildings({ className }: IllustrationProps) {
  const windowsA = [34, 50, 66, 82].flatMap((y) => [39, 55].map((x) => ({ x, y })));
  return (
    <Illustration className={className}>
      <Backdrop />
      <circle cx="128" cy="36" r="9" fill={C.white} />
      <rect x="14" y="100" width="132" height="8" rx="4" fill={C.soft} />

      {/* edificio alto */}
      <rect x="30" y="22" width="42" height="82" rx="7" fill={C.deep} />
      {windowsA.map(({ x, y }) => (
        <rect key={`${x}-${y}`} x={x} y={y} width="8" height="9" rx="2" fill={C.white} />
      ))}

      {/* edificio medio */}
      <rect x="76" y="46" width="36" height="58" rx="7" fill={C.mid} />
      <rect x="84" y="56" width="8" height="8" rx="2" fill={C.paper} />
      <rect x="96" y="56" width="8" height="8" rx="2" fill={C.paper} />
      <rect x="84" y="70" width="8" height="8" rx="2" fill={C.paper} />
      <rect x="96" y="70" width="8" height="8" rx="2" fill={C.paper} />
      <rect x="88" y="88" width="12" height="16" rx="3" fill={C.paper} />

      {/* edificio basso */}
      <rect x="116" y="66" width="24" height="38" rx="6" fill={C.plum} />
      <rect x="124" y="74" width="8" height="8" rx="2" fill={C.white} />
      <rect x="124" y="88" width="8" height="16" rx="2" fill={C.white} />
    </Illustration>
  );
}
