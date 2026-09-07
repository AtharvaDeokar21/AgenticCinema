import AgentStage from "@/components/company/AgentStage";
import { ProjectProvider } from "@/context/ProjectState";

/* Server component. The heading prerenders; the stage below it runs the agents. */
export default function Company() {
  return (
    <section className="act-wrap company" id="company">
      <div className="bay bay--tight">
        <p className="slug">
          <span>The company</span>
          <em>Seven agents, in running order</em>
        </p>
        <h2 className="playbill">
          Everyone on crew <i>has one job.</i>
        </h2>
        <p className="company__lede">
          This board runs the real agents. Give one what it needs and press Action — what
          comes back is written into the shared project, where the next agent reads it.
        </p>

        <ProjectProvider>
          <AgentStage />
        </ProjectProvider>
      </div>
    </section>
  );
}
