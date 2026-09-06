/* The fixed theatre frame: valance, velvet wings, vignette and film grain.
   Static, so it stays a server component. */
export default function Proscenium() {
  return (
    <>
      <div className="proscenium" aria-hidden="true">
        <div className="valance">
          <svg className="valance-swag" viewBox="0 0 1200 110" preserveAspectRatio="none">
            <path
              d="M0 0h1200v42c-100 34-200 46-300 46S700 76 600 76 400 88 300 88 100 76 0 42Z"
              fill="#4A0A10"
              opacity=".7"
            />
            <path
              d="M0 0h1200v20c-150 40-250 52-350 52S850 60 750 60 550 72 450 72 150 60 0 20Z"
              fill="#C4262E"
              opacity=".35"
            />
          </svg>
        </div>
        <div className="wing wing--l" />
        <div className="wing wing--r" />
      </div>
      <div className="house-lights" aria-hidden="true" />
      <div className="grain" aria-hidden="true" />
    </>
  );
}
