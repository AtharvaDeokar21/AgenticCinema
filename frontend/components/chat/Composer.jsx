"use client";

import { useEffect, useRef, useState } from "react";
import { Clapper } from "@/components/props";

/* The composer is shaped like a clapperboard: striped stick along the top,
   slate body underneath. Attachments and a voice note sit on the stick. */
const ACCEPT = {
  image: "image/*",
  video: "video/*",
  audio: "audio/*",
  file: ".txt,.md,.pdf,.doc,.docx,.srt,.json,.csv",
};

export default function Composer({ onSend, busy }) {
  const [text, setText] = useState("");
  const [files, setFiles] = useState([]);
  const [recording, setRecording] = useState(false);
  const textareaRef = useRef(null);
  const inputRefs = useRef({});
  const recorderRef = useRef(null);

  /* Grow the slate with the text instead of scrolling a two-line box. */
  useEffect(() => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, 190)}px`;
  }, [text]);

  function attach(event) {
    const picked = Array.from(event.target.files || []);
    if (picked.length) setFiles((prev) => [...prev, ...picked]);
    event.target.value = "";
  }

  function drop(event) {
    event.preventDefault();
    const dropped = Array.from(event.dataTransfer.files || []);
    if (dropped.length) setFiles((prev) => [...prev, ...dropped]);
  }

  async function toggleRecording() {
    if (recording) {
      recorderRef.current?.stop();
      return;
    }
    if (!navigator.mediaDevices?.getUserMedia || typeof MediaRecorder === "undefined") {
      alert("This browser will not record audio. Attach an audio file instead.");
      return;
    }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const recorder = new MediaRecorder(stream);
      const chunks = [];
      recorder.ondataavailable = (e) => e.data.size && chunks.push(e.data);
      recorder.onstop = () => {
        stream.getTracks().forEach((t) => t.stop());
        const blob = new Blob(chunks, { type: recorder.mimeType || "audio/webm" });
        const stamp = new Date().toISOString().slice(11, 19).replace(/:/g, "");
        setFiles((prev) => [...prev, new File([blob], `voice-note-${stamp}.webm`, { type: blob.type })]);
        setRecording(false);
      };
      recorderRef.current = recorder;
      recorder.start();
      setRecording(true);
    } catch {
      setRecording(false);
    }
  }

  function send() {
    if (busy) return;
    if (!text.trim() && files.length === 0) return;
    onSend(text.trim(), files);
    setText("");
    setFiles([]);
  }

  function onKeyDown(event) {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      send();
    }
  }

  return (
    <div className="composer" onDrop={drop} onDragOver={(e) => e.preventDefault()}>
      {/* the clapper stick */}
      <div className="composer__stick">
        <div className="composer__attach">
          {Object.entries(ACCEPT).map(([kind, accept]) => (
            <button
              key={kind}
              type="button"
              className="attach"
              onClick={() => inputRefs.current[kind]?.click()}
              aria-label={`Attach ${kind}`}
              title={`Attach ${kind}`}
            >
              <AttachIcon kind={kind} />
              <span>{kind}</span>
            </button>
          ))}
          <button
            type="button"
            className={`attach attach--rec${recording ? " is-on" : ""}`}
            onClick={toggleRecording}
            aria-pressed={recording}
            title={recording ? "Stop recording" : "Record a voice note"}
          >
            <AttachIcon kind="mic" />
            <span>{recording ? "stop" : "voice"}</span>
          </button>
        </div>
        <span className="composer__slug">SCENE 01 · TAKE 1</span>
      </div>

      {/* the slate */}
      <div className="composer__slate">
        {files.length > 0 && (
          <ul className="pending">
            {files.map((file, i) => (
              <li key={`${file.name}-${i}`}>
                <span>{file.name}</span>
                <button
                  type="button"
                  onClick={() => setFiles((prev) => prev.filter((_, k) => k !== i))}
                  aria-label={`Remove ${file.name}`}
                >
                  ×
                </button>
              </li>
            ))}
          </ul>
        )}

        <div className="composer__row">
          <textarea
            ref={textareaRef}
            rows={1}
            value={text}
            placeholder="Tell the crew what you're making. Drop in footage, a voice note, or a brand brief."
            onChange={(e) => setText(e.target.value)}
            onKeyDown={onKeyDown}
            aria-label="Message the crew"
          />
          <button
            type="button"
            className="roll"
            onClick={send}
            disabled={busy || (!text.trim() && files.length === 0)}
          >
            <span className={busy ? "roll__art is-busy" : "roll__art"}>
              <Clapper />
            </span>
            {busy ? "Rolling" : "Action"}
          </button>
        </div>
      </div>

      {Object.entries(ACCEPT).map(([kind, accept]) => (
        <input
          key={kind}
          ref={(el) => (inputRefs.current[kind] = el)}
          type="file"
          accept={accept}
          multiple
          hidden
          onChange={attach}
        />
      ))}
    </div>
  );
}

function AttachIcon({ kind }) {
  const paths = {
    image: "M3 4h18v16H3Zm3 11 4-5 3 4 3-2 5 6",
    video: "M3 5h13v14H3Zm13 5 5-3v10l-5-3",
    audio: "M6 9v6h4l5 4V5l-5 4Zm12-1a6 6 0 0 1 0 8",
    file: "M6 3h8l4 4v14H6Zm8 0v4h4M9 12h6M9 16h6",
    mic: "M12 3a3 3 0 0 1 3 3v6a3 3 0 0 1-6 0V6a3 3 0 0 1 3-3Zm-6 8a6 6 0 0 0 12 0M12 17v4",
  };
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d={paths[kind]} fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinejoin="round" strokeLinecap="round" />
    </svg>
  );
}
