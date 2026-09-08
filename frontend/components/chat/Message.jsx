"use client";
//path = frontend/components/chat/Message.jsx
import { Clapper, DirectorsChair } from "@/components/props";
import { useState, useRef, useEffect } from "react";

function CustomAudioPlayer({ src }) {
  const [isPlaying, setIsPlaying] = useState(false);
  const [duration, setDuration] = useState(0);
  const [currentTime, setCurrentTime] = useState(0);
  const audioRef = useRef(null);

  const togglePlay = () => {
    if (isPlaying) {
      audioRef.current.pause();
    } else {
      audioRef.current.play();
    }
    setIsPlaying(!isPlaying);
  };

  const formatTime = (time) => {
    if (time && !isNaN(time)) {
      const minutes = Math.floor(time / 60);
      const seconds = Math.floor(time % 60);
      return `${minutes}:${seconds < 10 ? '0' : ''}${seconds}`;
    }
    return '0:00';
  };

  return (
    <div className="custom-audio">
      <audio
        ref={audioRef}
        src={src}
        onTimeUpdate={() => setCurrentTime(audioRef.current.currentTime)}
        onLoadedMetadata={() => setDuration(audioRef.current.duration)}
        onEnded={() => setIsPlaying(false)}
      />
      <button className="custom-audio__play" onClick={togglePlay} aria-label={isPlaying ? "Pause" : "Play"}>
        {isPlaying ? (
          <svg viewBox="0 0 24 24" width="24" height="24" fill="currentColor"><path d="M6 19h4V5H6v14zm8-14v14h4V5h-4z"/></svg>
        ) : (
          <svg viewBox="0 0 24 24" width="24" height="24" fill="currentColor"><path d="M8 5v14l11-7z"/></svg>
        )}
      </button>
      <span className="custom-audio__time">{formatTime(currentTime)}</span>
      <input
        type="range"
        className="custom-audio__slider"
        min="0"
        max={duration || 0}
        value={currentTime}
        onChange={(e) => {
          const newTime = Number(e.target.value);
          audioRef.current.currentTime = newTime;
          setCurrentTime(newTime);
        }}
      />
      <span className="custom-audio__time">{formatTime(duration)}</span>
      <a href={src} download className="custom-audio__download" aria-label="Download">
        <svg viewBox="0 0 24 24" width="24" height="24" fill="currentColor"><path d="M19 9h-4V3H9v6H5l7 7 7-7zM5 18v2h14v-2H5z"/></svg>
      </a>
    </div>
  );
}
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
                {kindOf(file.type) === "audio" && <CustomAudioPlayer src={file.url} />}
                <span className="prop-card__name">{file.name}</span>
              </li>
            ))}
          </ul>
        )}

        {message.thumbnails?.length > 0 && (
          <div className="line__sources" style={{ marginTop: "1rem", marginBottom: "1rem" }}>
            <p style={{ fontWeight: "600", marginBottom: "0.75rem", color: "var(--color-text)", fontSize: "0.9em" }}>Global Video Thumbnails</p>
            <ul className="stills">
              {message.thumbnails.map((image, i) => (
                <li key={i}>
                  {/* eslint-disable-next-line @next/next/no-img-element */}
                  <img src={image.url || image} alt={image.caption || "Generated thumbnail"}
                  onError={(e) => { e.currentTarget.style.display = "none"; }} />
                  {image.caption && <span>{image.caption}</span>}
                  <div className="download-actions">
                    <a href={image.url || image} download={`thumbnail_${i+1}.png`} target="_blank" rel="noreferrer">Download Thumbnail</a>
                  </div>
                </li>
              ))}
            </ul>
          </div>
        )}

        {message.images?.length > 0 && (
          <div className="line__sources" style={{ marginTop: "1rem" }}>
            <p style={{ fontWeight: "600", marginBottom: "0.75rem", color: "var(--color-text)", fontSize: "0.9em" }}>Storyboard Shots</p>
            <ul className="stills">
              {message.images.map((image, i) => (
                <li key={i}>
                  {/* eslint-disable-next-line @next/next/no-img-element */}
                  <img src={image.url || image} alt={image.caption || "Generated still"}
                  onError={(e) => { e.currentTarget.style.display = "none"; }} />
                  {image.caption && <span>{image.caption}</span>}
                  <div className="download-actions">
                    <a href={image.url || image} download={`shot_${i+1}.png`} target="_blank" rel="noreferrer">Download Shot</a>
                  </div>
                </li>
              ))}
            </ul>
          </div>
        )}

        {message.audio?.length > 0 && (
          <ul className="tracks">
            {message.audio.map((track, i) => (
              <li key={i}>
                <span>{track.label || `Track ${i + 1}`}</span>
                <CustomAudioPlayer src={track.url || track} />
              </li>
            ))}
          </ul>
        )}

        {message.files?.length > 0 && (
          <ul className="props-strip">
            {message.files.map((file, i) => (
              <li key={i} className="prop-card prop-card--file">
                <a href={file.url} download={file.name} target="_blank" rel="noreferrer">
                  {file.name || file.url}
                </a>
              </li>
            ))}
          </ul>
        )}

        {message.sources?.length > 0 && (
          <div className="line__sources" style={{ marginTop: "1.5rem", fontSize: "0.9em", color: "var(--color-dim)" }}>
            <p style={{ fontWeight: "600", marginBottom: "0.75rem", color: "var(--color-text)" }}>Useful research sources</p>
            <ul style={{ listStyle: "none", padding: 0, margin: 0, display: "flex", flexDirection: "column", gap: "0.5rem" }}>
              {message.sources.map((src, i) => (
                <li key={i}>
                  • <a href={src.url} target="_blank" rel="noreferrer" style={{ color: "inherit", textDecoration: "underline", textUnderlineOffset: "3px" }}>{src.title}</a>
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>
    </article>
  );
}
