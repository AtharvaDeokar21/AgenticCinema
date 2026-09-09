const productionCard = [
  ["Agents in the company", "7"],
  ["Shared state object", "1"],
  ["Clearance passes per video", "6"],
  ["Reasoning", "Gemini 3.6 Flash"],
  ["Audio","Gemini TTS"],
  ["Web evidence", "Parallel"],
  ["Media execution", "FFmpeg"],
  ["Final cut", "Yours"],
];

export default function NowShowing() {
  return (
    <section className="act-wrap" id="now-showing">
      <div className="bay">
        <p className="slug">
          <span>Now showing</span>
          <em>Continuous performance</em>
        </p>

        <div className="sheet">
          <div>
            <h2 className="playbill">
              A solo creator does <i>eleven jobs.</i> Ten of them are unpaid.
            </h2>
            <p>
              Business development, trend research, script timing, shot planning, multicam
              sync, audio cleanup, localisation, rights clearance. None of it is the part
              anyone got into this to do, and all of it decides whether the video works.
            </p>
            <p>
              <strong>CreatorCrew staffs those jobs.</strong> Seven agents read one shared
              project state, do their piece, write it back, and hand off. No agent calls
              another; an orchestrator sequences them, so any one of them can be replaced
              without touching the rest.
            </p>
            <p>
              Every claim about the outside world carries a source. An uncited claim is
              rejected by the compiler check, not softened.
            </p>
          </div>

          <aside className="sheet__poster">
            <h3>Production card</h3>
            <ul className="tally">
              {productionCard.map(([label, value]) => (
                <li key={label}>
                  <span>{label}</span>
                  <span>{value}</span>
                </li>
              ))}
            </ul>
          </aside>
        </div>
      </div>
    </section>
  );
}
