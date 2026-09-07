import Link from "next/link";
import { Clapper} from "@/components/props";

/* The closing invitation, styled as a box-office window. Sits between the
   Crew credits and the footer. */
export default function TryAgent() {
  return (
    <section className="boxoffice" id="try">
      <div className="boxoffice__inner">
        <p className="slug slug--centre">
          <span>Box office</span>
        </p>

        <h2 className="playbill boxoffice__title">
          Try our <i>agent.</i>
        </h2>

        <p className="boxoffice__copy">
          Bring an idea, a rough cut, a voice note or a brand brief. The crew reads
          all of it and hands the job to whichever agent it belongs to.
        </p>

        <Link href="/green-room" className="boxoffice__cta">
          <span className="boxoffice__cta-art" aria-hidden="true">
            <Clapper />
          </span>
          Step into the Green Room
        </Link>
      </div>
    </section>
  );
}
