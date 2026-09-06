import Motes from "@/components/Motes";
import { DirectorsChair, FilmReel, StageLamp, TicketStub } from "@/components/props";

/* Six planes of stage. Everything with data-par is driven by StageDirection. */
export default function Hero() {
  return (
    <header className="stage" id="top">
      <div className="plane plane--beam" data-par data-speed="0.06" aria-hidden="true" />

      <Motes />

      <div className="plane plane--barrel" data-par data-speed="0.20" aria-hidden="true">
        <div className="lamp-bar">
          <StageLamp />
          <StageLamp />
          <StageLamp />
          <StageLamp />
        </div>
      </div>

      <div className="stage__type" data-par data-speed="0.34" data-mouse="14">
        <p className="overtitle">A one-person production company, staffed</p>
        <h1 className="marquee-title">
          <span>Agentic</span>
          <span>Cinema</span>
        </h1>
        <p className="logline">
          Seven agents share one script and one shared state. They find the deal, time the
          words, plan the shot, sync the audio, dub it for your actual audience, and clear
          the rights before any of it costs a reshoot. You still call action.
        </p>
      </div>

      <div className="plane plane--floor" data-par data-speed="-0.14" aria-hidden="true" />

      <div className="plane plane--props" data-par data-speed="-0.30" aria-hidden="true">
        <DirectorsChair className="prop-chair" />
        <FilmReel className="prop-reel" />
      </div>

      <div className="scroll-cue" aria-hidden="true">
        <TicketStub />
        KEEP SCROLLING
      </div>
    </header>
  );
}
