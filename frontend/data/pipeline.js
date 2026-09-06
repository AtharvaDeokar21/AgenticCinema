// Frames on the filmstrip. `gate` marks a ClearanceCheck pass.
export const pipeline = [
  { no: "FRAME 01", title: "Brief", copy: "You bring a rough idea, a voice note, or a brand brief as a PDF." },
  { no: "FRAME 02", title: "CreatorScout", copy: "Ranked brand queue, drafted outreach, exclusivity tracked with expiry dates." },
  { no: "CLEARANCE \u00b7 PASS 1", title: "Deal terms", gate: true, copy: "Perpetual usage rights with no separate fee is a red. It stops here." },
  { no: "FRAME 03", title: "Script Suggestor", copy: "Timed beats, delivery notes, the angle nobody covered, word budget shown." },
  { no: "CLEARANCE \u00b7 PASS 2", title: "Claims and mentions", gate: true, copy: "A competitor named inside a sponsored script is a contract breach, not awkwardness." },
  { no: "FRAME 04", title: "Storyboard", copy: "Shot plan keyed to timecodes, three thumbnails, a setup list you can actually shoot." },
  { no: "CLEARANCE \u00b7 PASS 3", title: "Visual assets", gate: true, copy: "Recognisable character in a thumbnail, or a station that needs a filming permit." },
  { no: "FRAME 05", title: "You shoot", copy: "The one step nobody automates. Take the setup list and go." },
  { no: "FRAME 06", title: "Syncer", copy: "Every clip placed, drift measured, dead air marked, wrong takes named." },
  { no: "CLEARANCE \u00b7 PASS 4", title: "Room audio", gate: true, copy: "The TV in the background is identifiable, and it can claim your revenue." },
  { no: "FRAME 07", title: "Audio", copy: "Clean master, separate stems, generated bed, a change log you can reverse." },
  { no: "CLEARANCE \u00b7 PASS 5", title: "Music and voice", gate: true, copy: "Does the licence tier cover sponsored content? Is the consent record on file?" },
  { no: "FRAME 08", title: "Cultural Dub", copy: "One track per market, subtitles, and every substitution written down with its source." },
  { no: "CLEARANCE \u00b7 PASS 6", title: "Per market", gate: true, copy: "Disclosure rules differ by country. India cleared is not Indonesia cleared." },
  { no: "FRAME 09", title: "Final cut", copy: "Yours. Every decision needing taste, and every one carrying legal weight, stays with you." },
];
