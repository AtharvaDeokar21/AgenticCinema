"use client";
//path = frontend/components/chat/Message.jsx
import { Clapper, DirectorsChair } from "@/components/props";

/* Laid out as screenplay dialogue rather than chat bubbles: a cue line in
   caps, then the speech indented under it. Screenplays are set in Courier,
   which is already the site's body face, so this costs nothing and reads
   as the right thing. */

const kindOf = (type = "") => {
  if (type.startsWith("image/")) return "image";
  if (type.startsWith("video/")) return "video";
  if (type.startsWith("audio/")) return "audio";
  return "file";
};

export default function Message({ message }) {
  const you = message.role === "you";

  return (
    <article className={`line line--${you ? "you" : "crew"}`}>
      <p className="line__cue">
        <span className="line__mark" aria-hidden="true">
          {you ? <DirectorsChair /> : <Clapper />}
        </span>
        {you ? "You" : "The Crew"}
        {message.agent && <em>({message.agent})</em>}
        {message.__demo && <b className="chip chip--warn">sample</b>}
      </p>

      <div className="line__speech">
        {message.pending ? (
          <p className="line__thinking">
            <i /><i /><i />
            <span>rolling…</span>
          </p>
        ) : message.error ? (
          <p className="line__error">{message.error}</p>
        ) : (
          message.text
            .split("\n")
            .filter(Boolean)
            .map((paragraph, i) => <p key={i}>{paragraph}</p>)
        )}

        {/* what the creator attached */}
        {message.attachments?.length > 0 && (
          <ul className="props-strip">
            {message.attachments.map((file, i) => (
              <li key={i} className={`prop-card prop-card--${kindOf(file.type)}`}>
                {kindOf(file.type) === "image" && (
                  /* eslint-disable-next-line @next/next/no-img-element */
                  <img src={file.url} alt={file.name} />
                )}
                {kindOf(file.type) === "video" && <video src={file.url} controls />}
                {kindOf(file.type) === "audio" && <audio src={file.url} controls />}
                <span className="prop-card__name">{file.name}</span>
              </li>
            ))}
          </ul>
        )}

        {/* what the crew sent back */}
        {message.images?.length > 0 && (
          <ul className="stills">
            {message.images.map((image, i) => (
              <li key={i}>
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img src={image.url || image} alt={image.caption || "Generated still"}
                onError={(e) => { e.currentTarget.style.display = "none"; }} />
                {image.caption && <span>{image.caption}</span>}
              </li>
            ))}
          </ul>
        )}

        {message.audio?.length > 0 && (
          <ul className="tracks">
            {message.audio.map((track, i) => (
              <li key={i}>
                <span>{track.label || `Track ${i + 1}`}</span>
                <audio src={track.url || track} controls />
              </li>
            ))}
          </ul>
        )}

        {message.files?.length > 0 && (
          <ul className="props-strip">
            {message.files.map((file, i) => (
              <li key={i} className="prop-card prop-card--file">
                <a href={file.url} download target="_blank" rel="noreferrer">
                  {file.name || file.url}
                </a>
              </li>
            ))}
          </ul>
        )}
      </div>
    </article>
  );
}
