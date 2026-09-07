/* The company, in DAG order.

   key        -> the agent id used by lib/api.js ENDPOINTS
   needs      -> ProjectState fields this agent reads (filled by earlier agents)
   produces   -> the ProjectState field this agent writes
   fields     -> the form the creator actually fills in
   working    -> the run console lights these up one at a time while it executes
   outputKind -> which renderer OutputDailies uses for the result              */
export const agents = [
  {
    key: "creator_scout",
    numeral: "I",
    name: "Creator Scout",
    role: "Finds who should make this",
    prop: "megaphone",
    body:
      "Searches the live web for creators whose audience actually overlaps the brief, and scores the fit with the numbers behind it.",
    needs: [],
    produces: "creator_recommendations",
    model: "CreatorRecommendation[]",
    outputKind: "creators",
    working: [
      "Builds a candidate universe from the live web, not from a static list",
      "Pulls follower count and engagement rate for each name found",
      "Scores fit against your niche, audience and goal",
      "Drops anything it cannot cite, and says so",
    ],
    handoff: "Writes creator_recommendations. Nothing downstream depends on it — run it whenever.",
    fields: [
      { name: "niche", label: "Target niche", type: "text", required: true,
        placeholder: "personal finance explainers" },
      { name: "audience", label: "Audience demographics", type: "text", required: true,
        placeholder: "22–30, urban India, 60% male" },
      { name: "goal", label: "Project goal", type: "textarea", required: true,
        placeholder: "A 60-second explainer for a UPI credit product, aimed at first-time borrowers." },
    ],
  },
  {
    key: "script_suggestor",
    numeral: "II",
    name: "Script Suggestor",
    role: "Turns a brief into a timed page",
    prop: "typewriter",
    body:
      "Reads current coverage of your topic, names the angle nobody used, and writes beats to the second so nothing downstream has to guess at timing.",
    needs: [],
    produces: "script",
    model: "ScriptVersion",
    outputKind: "script",
    working: [
      "Researches live coverage of the topic through Parallel",
      "Calls it: spike or evergreen, and finds the unused angle",
      "Derives runtime from the beat count and a spoken word budget",
      "Writes each beat with timecode, visual intent, audio intent and expression",
    ],
    handoff: "Writes script. Storyboard, Audio and Syncer all read it.",
    fields: [
      { name: "brief", label: "Your brief", type: "textarea", required: true,
        placeholder: "Explain what a UPI credit line does to your credit score. Nobody covers this part." },
      { name: "duration_seconds", label: "Target duration (seconds)", type: "number",
        required: true, value: 60 },
      { name: "tone", label: "Tone", type: "text", placeholder: "direct, slightly conspiratorial" },
      { name: "language", label: "Language", type: "text", value: "English" },
    ],
  },
  {
    key: "storyboard",
    numeral: "III",
    name: "Storyboard",
    role: "Decides what it looks like",
    prop: "camera",
    body:
      "Maps every script beat to a shot you can actually execute with the gear in your room, and keeps the timings locked to the script.",
    needs: ["script"],
    produces: "storyboard",
    model: "ShotPlan",
    outputKind: "shotplan",
    working: [
      "Reads the locked ScriptVersion beat by beat",
      "Finds references that performed on this topic and reads their frames",
      "Aggregates the working visual grammar: framing, palette, cut rate",
      "Fits it to your kit, then emits one shot per beat with matching timings",
    ],
    handoff: "Writes storyboard. Every Shot carries the beat_id it belongs to.",
    fields: [
      { name: "cameras", label: "Cameras you own", type: "text", value: "iPhone 15" },
      { name: "lights", label: "Lights", type: "text", value: "one LED panel, a desk lamp" },
      { name: "location", label: "Where you're shooting", type: "text", value: "small room, desk against a wall" },
      { name: "aspect_ratio", label: "Aspect ratio", type: "select", value: "9:16",
        options: ["9:16", "16:9", "1:1", "4:5"] },
    ],
  },
  {
    key: "audio",
    numeral: "IV",
    name: "Audio",
    role: "Makes it sound paid for",
    prop: "microphone",
    body:
      "Generates the read from the script, or cleans the take you recorded. Gemini decides what to fix; FFmpeg does the fixing.",
    needs: ["script"],
    produces: "audio_master",
    model: "AudioMaster",
    outputKind: "audio",
    working: [
      "Generates speech beat by beat, or extracts the audio from your upload",
      "Re-paces any beat that overruns its slot, and never speeds up a bad line",
      "Denoises, de-hums at 50Hz, cuts fillers, level-matches the speakers",
      "Returns word-level timestamps for every segment",
    ],
    handoff: "Writes audio_master. Cultural Dub needs those word timings.",
    fields: [
      { name: "mode", label: "Which voice", type: "select", value: "ai_voice",
        options: ["ai_voice", "creator_voice"] },
      { name: "voice", label: "Voice", type: "select", value: "Kore",
        options: ["Kore", "Puck", "Charon", "Fenrir"] },
      { name: "video", label: "Your recording (creator-voice path)", type: "file",
        accept: "video/*,audio/*" },
    ],
  },
  {
    key: "syncer",
    numeral: "V",
    name: "Syncer",
    role: "Puts every device on one timeline",
    prop: "waveform",
    body:
      "Matches the words across your camera audio and your good recording, and reports the offset for every clip — several times per clip, so drift shows up.",
    needs: ["script"],
    produces: "sync_report",
    model: "SyncReport",
    outputKind: "sync",
    working: [
      "Probes each file and flags variable frame rate before it corrupts anything",
      "Transcribes the camera's throwaway audio and the good recording",
      "Matches the words across both to find each clip's offset",
      "Checks the mouth against the take, and reports drift with where to split",
    ],
    handoff: "Writes sync_report. Nothing is rendered — it is a map for your editor.",
    fields: [
      { name: "video", label: "Your footage", type: "file", accept: "video/*", required: true },
      { name: "target_fps", label: "Conform to (fps)", type: "select", value: "30",
        options: ["24", "25", "30", "60"] },
      { name: "notes", label: "Take notes", type: "text", placeholder: "take 2 is the keeper" },
    ],
  },
  {
    key: "cultural_dub",
    numeral: "VI",
    name: "Cultural Dub",
    role: "Localises, does not translate",
    prop: "masks",
    body:
      "Rebuilds the joke instead of translating it, checks the slang against the live web, and fits every line back into its original slot.",
    needs: ["audio_master", "script"],
    produces: "dub_tracks",
    model: "DubTrack[]",
    outputKind: "dub",
    working: [
      "Transcribes in the language actually spoken, code-switching intact",
      "Tags every span that breaks: idiom, slang, meme, honorific, currency",
      "Searches the live web for what those mean in that region, this year",
      "Rewrites to fit the slot, screens for offence, then speaks it",
    ],
    handoff: "Writes dub_tracks. Flagged lines still go to a native reviewer.",
    fields: [
      { name: "target_locales", label: "Target locales", type: "chips",
        value: ["Hindi-IN"], options: ["Hindi-IN", "Tamil-IN", "Spanish-MX", "Japanese-JP", "Indonesian-ID", "Portuguese-BR"] },
      { name: "register", label: "Register", type: "select", value: "conversational",
        options: ["formal", "conversational", "street"] },
    ],
  },
  {
    key: "compliance",
    numeral: "VII",
    name: "Compliance",
    role: "Clears it before it costs you",
    prop: "stamp",
    body:
      "Runs against whatever just finished. Green passes quietly, yellow attaches a task, red blocks the pipeline and proposes a substitute.",
    needs: [],
    produces: "clearance_report",
    model: "ClearanceReport",
    outputKind: "clearance",
    working: [
      "Extracts everything carrying rights: songs, brands, people, locations, claims",
      "Skips whatever an earlier pass already cleared",
      "Finds the terms on the open web, then reads the licence page itself",
      "Assigns green, yellow or red — an uncited red is downgraded, in code",
    ],
    handoff: "Writes clearance_report and registers a checkpoint. Red returns to the agent that produced it.",
    fields: [
      { name: "stage", label: "Check which stage", type: "select", value: "script",
        options: ["script", "storyboard", "audio", "dubbing"] },
      { name: "target_markets", label: "Markets", type: "chips", value: ["India"],
        options: ["India", "United States", "Indonesia", "Brazil", "Japan", "Mexico"] },
      { name: "is_sponsored", label: "Sponsored video", type: "select", value: "yes",
        options: ["yes", "no"] },
    ],
  },
];

/* Which agent fills each ProjectState field — used to tell the creator
   exactly where a missing input is supposed to come from. */
export const producedBy = Object.fromEntries(
  agents.map((a) => [a.produces, a.name])
);
