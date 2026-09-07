/* Hand-drawn stage props, one per agent. All SVG attributes are in JSX camel
   case (strokeWidth, strokeLinejoin) rather than the HTML hyphenated form. */

export function Megaphone() {
  return (
    <svg viewBox="0 0 200 160" aria-hidden="true">
      <g stroke="#C8992F" strokeWidth="2.6" fill="none" strokeLinejoin="round">
        <path d="M60 56h22l70-34v116l-70-34H60Z" fill="#8C1420" />
        <path d="M40 56h20v48H40a10 10 0 0 1-10-10V66a10 10 0 0 1 10-10Z" fill="#4A0A10" />
        <path d="M152 22v116" strokeWidth="4" />
        <circle cx="46" cy="122" r="10" fill="#2A1D22" />
        <path d="M46 112V104" />
        <path d="M168 52c10 12 10 34 0 46M182 40c16 20 16 60 0 80" opacity=".7" />
      </g>
    </svg>
  );
}

export function Typewriter() {
  return (
    <svg viewBox="0 0 200 170" aria-hidden="true">
      <g stroke="#C8992F" strokeWidth="2.6" fill="none" strokeLinejoin="round">
        <path d="M46 22h108v58H46Z" fill="#E8DCC2" opacity=".14" />
        <path d="M60 38h80M60 50h64M60 62h72" strokeWidth="2" opacity=".8" />
        <path d="M26 80h148l12 58H14Z" fill="#2A1D22" />
        <path d="M34 96h132M40 110h120" strokeWidth="2" opacity=".5" />
        <rect x="52" y="122" width="96" height="10" rx="5" fill="#8C1420" />
        <circle cx="30" cy="70" r="9" />
        <circle cx="170" cy="70" r="9" />
      </g>
    </svg>
  );
}

export function Camera() {
  return (
    <svg viewBox="0 0 210 150" aria-hidden="true">
      <g stroke="#C8992F" strokeWidth="2.6" fill="none" strokeLinejoin="round">
        <circle cx="66" cy="34" r="24" fill="#2A1D22" />
        <circle cx="126" cy="34" r="24" fill="#2A1D22" />
        <circle cx="66" cy="34" r="9" />
        <circle cx="126" cy="34" r="9" />
        <path d="M30 58h130v56H30Z" fill="#8C1420" />
        <path d="M160 74l34-18v58l-34-18Z" fill="#4A0A10" />
        <path d="M46 128h96M94 114v14" />
        <path d="M60 138l34-24 34 24" />
      </g>
    </svg>
  );
}

export function Waveform() {
  return (
    <svg viewBox="0 0 210 150" aria-hidden="true">
      <g stroke="#C8992F" strokeWidth="2.6" fill="none" strokeLinecap="round">
        <path d="M14 22h182v106H14Z" fill="#2A1D22" strokeWidth="2" />
        <g opacity=".55" strokeWidth="2">
          <rect x="22" y="30" width="10" height="10" />
          <rect x="22" y="110" width="10" height="10" />
          <rect x="178" y="30" width="10" height="10" />
          <rect x="178" y="110" width="10" height="10" />
        </g>
        <path d="M48 75v-22M62 75v-38M76 75v-14M90 75v-30M104 75v-46M118 75v-18M132 75v-34M146 75v-10M160 75v-26" />
        <path
          d="M48 75v24M62 75v40M76 75v12M90 75v32M104 75v20M118 75v44M132 75v16M146 75v28M160 75v10"
          stroke="#C4262E"
        />
      </g>
    </svg>
  );
}

export function Microphone() {
  return (
    <svg viewBox="0 0 160 180" aria-hidden="true">
      <g stroke="#C8992F" strokeWidth="2.6" fill="none" strokeLinejoin="round">
        <rect x="46" y="14" width="68" height="86" rx="34" fill="#8C1420" />
        <path d="M58 34h44M58 46h44M58 58h44M58 70h44M58 82h44" opacity=".55" strokeWidth="2" />
        <path d="M30 78a50 50 0 0 0 100 0" />
        <path d="M80 128v22M52 150h56" />
        <path d="M40 160h80l8 14H32Z" fill="#2A1D22" />
      </g>
    </svg>
  );
}

export function Masks() {
  return (
    <svg viewBox="0 0 220 160" aria-hidden="true">
      <g stroke="#C8992F" strokeWidth="2.6" fill="none" strokeLinejoin="round">
        <path d="M18 24h84v58c0 30-18 52-42 52S18 112 18 82Z" fill="#8C1420" />
        <circle cx="42" cy="58" r="5" fill="#C8992F" stroke="none" />
        <circle cx="78" cy="58" r="5" fill="#C8992F" stroke="none" />
        <path d="M40 92c8 12 32 12 40 0" />
        <path d="M118 24h84v58c0 30-18 52-42 52s-42-22-42-52Z" fill="#4A0A10" />
        <circle cx="142" cy="58" r="5" fill="#C8992F" stroke="none" />
        <circle cx="178" cy="58" r="5" fill="#C8992F" stroke="none" />
        <path d="M140 100c8-12 32-12 40 0" />
      </g>
    </svg>
  );
}

export function Stamp() {
  return (
    <svg viewBox="0 0 190 170" aria-hidden="true">
      <g stroke="#C8992F" strokeWidth="2.6" fill="none" strokeLinejoin="round">
        <rect x="46" y="10" width="98" height="34" rx="8" fill="#2A1D22" />
        <path d="M74 44h42v22H74Z" />
        <path d="M40 66h110v34H40Z" fill="#8C1420" />
        <path d="M18 128h154" strokeWidth="4" />
        <circle cx="95" cy="83" r="12" strokeWidth="2" />
        <path d="M88 83l5 6 10-12" strokeWidth="2.4" />
        <path d="M44 146h102" opacity=".5" strokeDasharray="4 6" />
      </g>
    </svg>
  );
}

export function DirectorsChair({ className }) {
  return (
    <svg className={className} viewBox="0 0 120 150" aria-hidden="true">
      <g stroke="#C8992F" strokeWidth="2.4" fill="none" strokeLinecap="round">
        <path d="M14 30h92M14 30 96 122M106 30 24 122M20 122h16M84 122h16" />
        <path d="M18 8h84v22H18Z" fill="#8C1420" stroke="#C8992F" />
        <path d="M22 60h76l-6 16H28Z" fill="#8C1420" />
        <path d="M30 76v40M90 76v40" />
      </g>
    </svg>
  );
}

export function FilmReel({ className }) {
  return (
    <svg className={className} viewBox="0 0 120 120" aria-hidden="true">
      <g stroke="#C8992F" strokeWidth="2.4" fill="none">
        <circle cx="60" cy="60" r="52" />
        <circle cx="60" cy="60" r="46" strokeWidth="1" />
        <circle cx="60" cy="60" r="10" fill="#8C1420" />
        <circle cx="60" cy="26" r="11" />
        <circle cx="60" cy="94" r="11" />
        <circle cx="26" cy="60" r="11" />
        <circle cx="94" cy="60" r="11" />
        <circle cx="36" cy="36" r="8" />
        <circle cx="84" cy="84" r="8" />
        <circle cx="84" cy="36" r="8" />
        <circle cx="36" cy="84" r="8" />
      </g>
    </svg>
  );
}

export function StageLamp() {
  return (
    <svg className="lamp" viewBox="0 0 60 80" aria-hidden="true">
      <g fill="#2A1D22" stroke="#C8992F" strokeWidth="1.5">
        <rect x="26" y="0" width="8" height="14" />
        <path d="M8 14h44l-6 36H14Z" />
        <ellipse cx="30" cy="50" rx="16" ry="5" fill="#F6E7C6" stroke="none" opacity=".9" />
        <rect x="4" y="10" width="52" height="5" />
      </g>
    </svg>
  );
}

export function TicketStub() {
  return (
    <svg viewBox="0 0 120 46" aria-hidden="true">
      <g stroke="#C8992F" strokeWidth="1.6" fill="none">
        <path d="M4 6h112v34H4Z" />
        <path d="M86 6v34" strokeDasharray="3 4" />
      </g>
      <text x="14" y="29" fill="#C8992F" fontSize="13" letterSpacing="2">
        ADMIT ONE
      </text>
      <text x="94" y="29" fill="#C8992F" fontSize="13">
        &#8595;
      </text>
    </svg>
  );
}


export function Clapper({ className }) {
  return (
    <svg className={className} viewBox="0 0 120 100" aria-hidden="true">
      <g stroke="#C8992F" strokeWidth="3" fill="none" strokeLinejoin="round">
        <rect x="10" y="30" width="100" height="58" rx="4" fill="#1B2422" />
        <path d="M14 8h96l-6 20H8Z" fill="#151517" />
        <g fill="#EDE6D6" stroke="none">
          <path d="M24 9h16l-8 18H16z" />
          <path d="M52 9h16l-8 18H44z" />
          <path d="M80 9h16l-8 18H72z" />
        </g>
        <path d="M22 48h76M22 64h50" strokeWidth="2.4" opacity=".45" />
      </g>
    </svg>
  );
}

export function Projector({ className }) {
  return (
    <svg className={className} viewBox="0 0 180 130" aria-hidden="true">
      <g stroke="#C8992F" strokeWidth="2.6" fill="none" strokeLinejoin="round">
        <circle cx="52" cy="34" r="22" />
        <circle cx="104" cy="30" r="16" />
        <path d="M28 58h104v34H28Z" fill="#2A1D22" />
        <path d="M132 66l30-12v34l-30-12Z" fill="#4A0A10" />
        <path d="M46 92v18M118 92v18M34 110h96" />
      </g>
    </svg>
  );
}

/* Looked up by the `prop` key on each agent record. */
export const propsByName = {
  megaphone: Megaphone,
  typewriter: Typewriter,
  camera: Camera,
  waveform: Waveform,
  microphone: Microphone,
  masks: Masks,
  stamp: Stamp,
};
