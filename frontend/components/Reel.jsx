import { pipeline } from "@/data/pipeline";

/* Sticky filmstrip. StageDirection translates #strip-track horizontally as
   the section scrolls past. */
export default function Reel() {
  return (
    <section className="reel" id="reel">
      <div className="reel__pin">
        <div className="reel__head">
          <p className="slug">
            <span>The reel</span>
            <em>Clearance runs between every stage</em>
          </p>
          <h2 className="playbill">
            Nine frames, <i>start to publish.</i>
          </h2>
        </div>

        <div className="strip">
          <div className="strip__track" id="strip-track">
            {pipeline.map((frame) => (
              <article
                key={frame.no}
                className={`frame${frame.gate ? " frame--gate" : ""}`}
              >
                <p className="frame__no">{frame.no}</p>
                <h4>{frame.title}</h4>
                <p>{frame.copy}</p>
              </article>
            ))}
          </div>
        </div>
      </div>
    </section>
  );
}
