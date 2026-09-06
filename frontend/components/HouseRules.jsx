import { houseRules } from "@/data/crew";

export default function HouseRules() {
  return (
    <section className="rule-bay" id="house">
      <div className="rule-grid">
        <div>
          <p className="slug">
            <span>House rules</span>
          </p>
          <h2 className="playbill">
            Four rules <i>the whole company works to.</i>
          </h2>
        </div>

        <div>
          {houseRules.map((rule) => (
            <div className="tenet" key={rule.title}>
              <h3>{rule.title}</h3>
              <p>{rule.copy}</p>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
