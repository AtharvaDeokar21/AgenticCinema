# Agentic Cinema — frontend

Next.js 15 (App Router) port of the single-file theatre landing page.

## Run it

```bash
npm install
npm run dev      # http://localhost:3000
```

```bash
npm run build && npm start   # production
```

Node 18.18+ is required by Next 15. Fonts are fetched at build time by
`next/font/google`, so the first build needs network access to Google Fonts.

## Layout

```
app/
  layout.js         next/font setup, metadata, <html> shell
  page.js           composes the sections
  globals.css       the entire house style
components/
  CurtainCall.jsx   client — the page-load curtain reveal
  Proscenium.jsx    server — fixed velvet frame, vignette, grain
  StageDirection.jsx client — one rAF loop: parallax, filmstrip, follow spot, nav
  NavRail.jsx       server — in-page anchors
  Hero.jsx          server — six stage planes
  Motes.jsx         client — randomised dust, generated after mount
  BulbMarquee.jsx   server
  NowShowing.jsx    server
  Company.jsx       server — maps data/agents.js
  Slate.jsx         client — the interactive clapperboard
  Reel.jsx          server — sticky filmstrip
  HouseRules.jsx    server
  Crew.jsx          server
  Credits.jsx       server
  props/index.jsx   all stage-prop SVGs, exported individually
hooks/
  useReducedMotion.js
data/
  agents.js         the seven agents
  pipeline.js       filmstrip frames
  crew.js           tech credits + house rules
  slateStages.js    clapperboard states
```

Only four components are client components. Everything else prerenders.

## What changed in the port

- **Fonts** — the `<link>` to Google Fonts became `next/font/google`, which
  self-hosts the files and removes the render-blocking request. The families
  arrive as `--font-display` / `--font-sheet` and `globals.css` reads them.
  Bodoni Moda is a variable font, so it takes no `weight` array.
- **The curtain** used to toggle a class on `<body>`. It is now React state on
  the component itself, so the CSS selector is `.curtain-call.is-open` rather
  than `body.is-open .curtain-call`.
- **Dust motes** are generated in `useEffect`, not during render. Random values
  produced during render would differ between server and client and trigger a
  hydration mismatch.
- **The slate** no longer writes to the DOM with `dangerouslySetInnerHTML` or
  `textContent`; it renders from state, and `slateStages` is data.
- **The rAF loop** lives in `StageDirection` and cleans up after itself —
  listeners removed and inline transforms cleared on unmount, so it survives
  fast refresh and route changes.
- **Reduced motion** was CSS-only before. It is now also read in JS, so the
  parallax loop and the clapper animation genuinely stop rather than being
  computed and then overridden.
- SVG attributes converted to JSX casing (`strokeWidth`, `strokeLinejoin`,
  `strokeDasharray`, `fontSize`), and every inline `style="…"` became an object.
- Repeated inline styles were moved into real classes: `.bay--flush`,
  `.slug--centre`, `.tenet + .tenet`, `.sheet p:first-of-type`.
- `#clapper` became `.clapper`, since an id is the wrong hook for a component
  that could appear more than once.

## Deploying

Nothing here is dynamic — `next build` prerenders the single route as static
content, so any static host works. On Vercel it deploys with no configuration.
