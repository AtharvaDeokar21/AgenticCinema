import { crew } from "@/data/crew";

export default function Crew() {
  return (
    <section className="crew-bay" id="crew">
      <p className="slug">
        <span>Crew</span>
        <em>Built on</em>
      </p>
      <h2 className="playbill">Below the line.</h2>

      <dl className="crew">
        {crew.map(([role, name, note]) => (
          <div key={name}>
            <dt>{role}</dt>
            <dd>
              {name}
              <em>{note}</em>
            </dd>
          </div>
        ))}
      </dl>
    </section>
  );
}
