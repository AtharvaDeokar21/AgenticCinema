import { agents } from "@/data/agents";
import { propsByName } from "@/components/props";

export default function Company() {
  return (
    <section className="act-wrap" id="company">
      <div className="bay bay--flush">
        <p className="slug">
          <span>The company</span>
          <em>Seven agents, in running order</em>
        </p>
        <h2 className="playbill">
          Everyone on this crew <i>has one job.</i>
        </h2>
      </div>

      {agents.map((agent, index) => {
        const Prop = propsByName[agent.prop];
        return (
          <article
            key={agent.name}
            className={`act${index % 2 === 1 ? " act--flip" : ""}`}
            data-act
          >
            <div className="act__numeral">{agent.numeral}</div>

            <div className="act__body">
              <h3>{agent.name}</h3>
              <p className="act__role">{agent.role}</p>
              <p>{agent.body}</p>

              <dl className="callsheet">
                {agent.callsheet.map(([term, detail]) => (
                  <div key={term}>
                    <dt>{term}</dt>
                    <dd>{detail}</dd>
                  </div>
                ))}
              </dl>
            </div>

            <div
              className="act__prop"
              data-par
              data-speed={(0.07 + (index % 3) * 0.02).toFixed(2)}
            >
              <Prop />
              <p className="spare">
                <b>THE BOTTLENECK</b>
                {agent.bottleneck}
              </p>
            </div>
          </article>
        );
      })}
    </section>
  );
}
