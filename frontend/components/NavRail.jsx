const sections = [
  ["now-showing", "Now showing"],
  ["company", "The company"],
  ["slate", "The slate"],
  ["reel", "The reel"],
  ["house", "House rules"],
  ["crew", "Crew"],
  ["try", "Try our agent"],
];

/* Plain anchors, not next/link: these are in-page jumps on a single route.
   The active state is toggled by StageDirection. */
export default function NavRail() {
  return (
    <nav className="rail" aria-label="Sections">
      {sections.map(([id, label]) => (
        <a key={id} href={`#${id}`}>
          {label}
        </a>
      ))}
    </nav>
  );
}
