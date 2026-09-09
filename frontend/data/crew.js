export const crew = [
  ["Reasoning & multimodal", "Gemini 3.6 Flash", "Ranking, transcreation, video-plus-audio judgement"],
  ["Web intelligence", "Parallel", "Search, Extract, Task, FindAll, Entity Search, Monitor"],
  ["Speech", "Gemini Flash TTS", "Audio tags, multi-speaker, SynthID watermark kept intact"],
  ["Media execution", "FFmpeg & FFprobe", "Probing, VFR conforming, frame extraction, every cut and mix"],
  ["Contracts", "Pydantic", "One shared ProjectState. Agents never pass loose dictionaries."],
  ["Service", "FastAPI on Render", "For media staging"],
];

export const houseRules = [
  {
    title: "Gemini decides. Deterministic tools execute.",
    copy: "The model says \u201ccut the dead air from 1:12 to 1:19.\u201d FFmpeg makes the cut. Nothing here asks a model to do arithmetic on waveforms.",
  },
  {
    title: "Every outside claim carries a source.",
    copy: "Parallel returns URLs and excerpts; the model cites labels and the application resolves them to real links. An uncited red is downgraded to unverified, in code, not by trust.",
  },
  {
    title: "Failure is a correct output.",
    copy: "\u201cI couldn't verify this\u201d is honest. A confident fabrication costs a bounced pitch, a lost negotiation, or a takedown. Every agent has a defined degraded mode and declares it.",
  },
  {
    title: "You get final cut.",
    copy: "The agent never signs a deal, never agrees to exclusivity, and never publishes into a language nobody on the team reads. It shortens the work, not the judgement.",
  },
];
