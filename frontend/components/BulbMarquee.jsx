import { Fragment } from "react";

const phrases = [
  "SEVEN AGENTS",
  "ONE SHARED SCRIPT",
  "CITED OR CUT",
  "NO RESHOOTS",
  "CLEARED BEFORE IT COSTS YOU",
  "YOU CALL ACTION",
];

/* Fragment, not a wrapper element: the bulb flicker delays are set with
   `i:nth-child(6n+2)`, which only works while the bulbs and labels are
   direct children of .bulbs__run. */
function Run() {
  return (
    <div className="bulbs__run">
      {phrases.map((phrase) => (
        <Fragment key={phrase}>
          <i />
          <span>{phrase}</span>
        </Fragment>
      ))}
    </div>
  );
}

/* Two identical runs; the CSS translates the track by -50% for a seamless loop. */
export default function BulbMarquee() {
  return (
    <div className="bulbs" aria-hidden="true">
      <div className="bulbs__track">
        <Run />
        <Run />
      </div>
    </div>
  );
}
