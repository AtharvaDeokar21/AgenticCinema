// The company, in running order. `prop` maps to a component in components/props.
export const agents = [
  {
    numeral: "I",
    name: "CreatorScout",
    role: "Business development, while you sleep",
    body:
      "Finds brands that are actually spending on creators right now, ranks them against your real audience numbers, and drafts the first message. It watches for funding rounds, product launches and new marketing heads; because creator marketing is won on timing, not on pitch quality.",
    prop: "megaphone",
    bottleneck:
      "Unpaid hours on a market you can't see into, and a launch window missed by a week.",
    callsheet: [
      ["Reads", "Audience split, rate floor, exclusivity ledger, eight-week capacity"],
      ["Uses", "Parallel Monitor API"],
      ["Returns", "A ranked queue where every entry argues its own case, with citations"],
      ["Never", "Signs. Agrees to exclusivity. Invents a fee."],
    ],
  },
  {
    numeral: "II",
    name: "Script Suggestor",
    role: "Turns intent into a timed, shootable page",
    body:
      "Reads how heavily your topic is already covered, tells you whether it's a spike or evergreen, and names the angle nobody has taken. Then it does the arithmetic you'd otherwise guess at: 260 words is 1:50, and you have a 60-second slot.",
    prop: "typewriter",
    bottleneck:
      "Scrolling for an hour to guess if a topic is dead, then filming 90 seconds for a 60-second slot.",
    callsheet: [
      ["Reads", "Your brief or a voice note, plus your own past transcripts"],
      ["Uses", "Parallel Search API, Gemini multimodal reasoning"],
      ["Returns", "Per-beat timecodes, delivery notes, on-screen text, visual cues"],
      ["Also", "Re-times every downstream timestamp when you edit a line"],
    ],
  },
  {
    numeral: "III",
    name: "Storyboard",
    role: "Answers \u201cwhat does this look like\u201d",
    body:
      "Pulls content that already worked, extracts frames at every shot boundary, and reads how each one was actually lit and framed. Then it fits that to the gear in your room; a recommendation you can't execute is a defect, not an aspiration.",
    prop: "camera",
    bottleneck:
      "Discovering in the edit that every shot is the same size and the background is distracting.",
    callsheet: [
      ["Reads", "The locked script, your cameras, lenses, lights, room and aspect ratio"],
      ["Uses", "Parallel Search and Extract, FFmpeg scene detection"],
      ["Returns", "A shot plan keyed to script timecodes, plus three thumbnail variants"],
      ["Never", "Reproduces a reference frame. They're analysed, then discarded."],
    ],
  },
  {
    numeral: "IV",
    name: "Syncer",
    role: "Puts every device on one timeline",
    body:
      "No timecode box, no slate clap. It transcribes the camera's useless on-board audio and the good lav recording, matches the words, and reports the offset at several points across each clip, so drift shows up before you've cut the whole video, not after.",
    prop: "waveform",
    bottleneck:
      "\u201cIt was fine and then it went out of sync near the end\u201d; found after the edit was already done.",
    callsheet: [
      ["Reads", "Every camera clip, phone B-roll, and the continuous recorder file"],
      ["Uses", "FFprobe, FFmpeg, Gemini timestamped transcription; no waveform maths"],
      ["Returns", "A written map: what goes where, dead air to trim, pauses to keep"],
      ["Honest about", "Accuracy to the word, not the frame. You'll nudge by a frame or two."],
    ],
  },
  {
    numeral: "V",
    name: "Audio",
    role: "The difference between professional and homemade",
    body:
      "Two ways in: generate the read with expressive TTS from the script's own delivery column, or clean the take you recorded. Either way Gemini decides where, and FFmpeg does it: denoise first, de-hum at 50\u00a0Hz for Indian mains, level-match speakers by measurement rather than by ear.",
    prop: "microphone",
    bottleneck:
      "Mixing on the same headphones you recorded through, in the same room, with no engineer.",
    callsheet: [
      ["Reads", "The final script, or your recording plus the Syncer's timing map"],
      ["Uses", "Gemini TTS, FFmpeg for every actual cut"],
      ["Returns", "A clean master, separate stems, and a per-segment pass/fix/re-record verdict"],
      ["Never", "Fixes a writing problem by speeding up the voice"],
    ],
  },
  {
    numeral: "VI",
    name: "Cultural Dub",
    role: "Localises. Does not translate.",
    body:
      "A literal Hindi rendering of an English punchline isn't a Hindi punchline, it's a sentence where a joke used to be. Slang decays faster than any model's training data, so every idiom, meme and honorific gets checked against the live web before it's used, and screened for offence in the target region.",
    prop: "masks",
    bottleneck:
      "An agency engagement measured in weeks, costing more than the video earns, so it gets skipped.",
    callsheet: [
      ["Reads", "The clean master, plus the geographies your analytics actually show"],
      ["Uses", "Parallel Search on a tight freshness policy, weekly per-locale monitors"],
      ["Returns", "One track per language, subtitles, and a note on every substitution made"],
      ["Requires", "A native reviewer. Nobody publishes into a language nobody on the team speaks."],
    ],
  },
  {
    numeral: "VII",
    name: "ClearanceCheck",
    role: "Runs six times, between every other agent",
    body:
      "A song flagged at script stage costs a line rewrite. The same song flagged after the shoot costs a reshoot. After publish it costs the video's monetisation, and sometimes the channel. Running clearance once at the end is the same as not running it.",
    prop: "stamp",
    bottleneck:
      "Invisible work everyone skips until it costs a takedown, a strike, or a breached contract.",
    callsheet: [
      ["Reads", "Whatever the previous agent produced, plus the running asset ledger"],
      ["Uses", "Parallel Search and Extract; licence terms are usually PDFs"],
      ["Returns", "Green, yellow, red and a concrete substitute for every red"],
      ["Catches", "The caf\u00e9 playlist under your dialogue, before the edit rather than after"],
    ],
  },
];
