"use client";
//path = frontend/components/chat/ChatRoom.jsx
import { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import Backdrop from "@/components/chat/BackDrop";
import Composer from "@/components/chat/Composer";
import Message from "@/components/chat/Message";
import { ensureProject, sendToCrew } from "@/lib/chatApi";

const OPENERS = [
  "Write a 3-beat script about a futuristic cyberpunk coffee brand.",
  "Find brand deals for a cinematic filmmaker.",
  "Translate the audio into Hindi.",
  "Generate audio for this script.",
];

const nextId = () => typeof crypto !== "undefined" && crypto.randomUUID ? crypto.randomUUID() : `m${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;

export default function ChatRoom() {
  const [messages, setMessages] = useState([]);
  const [busy, setBusy] = useState(false);
  const [drift, setDrift] = useState(0);
  const transcriptRef = useRef(null);
  const [projectId, setProjectId] = useState(null);
  const [status, setStatus] = useState("");
  const objectUrls = useRef([]);
  const bootstrapped = useRef(false);    

  /* Object URLs are for previewing what the creator attached; release them
     when the page goes away so the blobs are not held forever. */

    useEffect(() => {
    if (bootstrapped.current) return;
    bootstrapped.current = true;
    ensureProject("Agentic Cinema demo")
      .then(setProjectId)
      .catch((e) =>
        setMessages([{ id: nextId(), role: "crew", text: `Backend unreachable — ${e.message}` }])
      );
  }, []);

  useEffect(() => {
    const urls = objectUrls.current;
    return () => urls.forEach((url) => URL.revokeObjectURL(url));
  }, []);

  useEffect(() => {
    const el = transcriptRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [messages]);

  /* The transcript's own scroll nudges the backdrop, so the stage behind
     drifts as the conversation gets longer. */
  function onScroll(event) {
    const el = event.currentTarget;
    const max = el.scrollHeight - el.clientHeight;
    setDrift(max > 0 ? el.scrollTop / max : 0);
  }

  const send = useCallback(
    async (text, files) => {
      const attachments = files.map((file) => {
        const url = URL.createObjectURL(file);
        objectUrls.current.push(url);
        return { name: file.name, type: file.type, url };
      });

      const mine = { id: nextId(), role: "you", text: text || "(attachment only)", attachments };
      const placeholder = { id: nextId(), role: "crew", text: "", pending: true };

      setMessages((prev) => [...prev, mine, placeholder]);
      setBusy(true);

      try {
        const reply = await sendToCrew({
          project_id: projectId,
          message: text,
          files,
          onStatus: setStatus,
        });

        setMessages((prev) =>
          prev.map((m) =>
            m.id === placeholder.id ? { ...m, ...reply, pending: false } : m
          )
        );
            } catch (error) {
        let detail = error.message;
        try {
          const start = detail.indexOf("{");
          if (start !== -1) {
            const inner = JSON.parse(JSON.parse(detail.slice(start)));
            detail = `${inner.type}: ${inner.message}`;
          }
        } catch {}

        setMessages((prev) =>
          prev.map((m) =>
            m.id === placeholder.id
              ? { ...m, pending: false, error: detail }
              : m
          )
        );
      } finally {
        setBusy(false);
      }
    },
    [projectId]
  );

  return (
    <div className="room" style={{ "--drift": drift }}>
      <Backdrop />

      <header className="room__top">
        <Link href="/" className="room__back">
          <span aria-hidden="true">&#8592;</span> Back to the theatre
        </Link>
        <p className="room__title">The Green Room</p>
        <div className="room__file">
          <span className="room__file-id">{projectId ?? "creating workspace…"}</span>
          {projectId && (
            <button className="room__reset-btn" title="Start a new project" onClick={() => { import("@/lib/chatApi").then(api => { api.forgetProject(); window.location.reload(); }) }}>
              <span aria-hidden="true">↻</span> Reset Project
            </button>
          )}
        </div>
      </header>

      <div className="room__transcript" ref={transcriptRef} onScroll={onScroll}>
        <div className="room__column">
          {messages.length === 0 ? (
            <div className="callsheet-welcome">
              <span className="callsheet-welcome__ticket">
              </span>
              <h1>You&rsquo;re on the call sheet.</h1>
              <p>
                Type what you&rsquo;re making. Drop in footage, a voice note, a still, or a
                brand brief — the crew reads all of it, and hands the job to whichever
                agent it belongs to.
              </p>
              <ul className="openers">
                {OPENERS.map((line) => (
                  <li key={line}>
                    <button type="button" onClick={() => send(line, [])}>
                      {line}
                    </button>
                  </li>
                ))}
              </ul>
            </div>
          ) : (
            messages.map((message) => <Message key={message.id} message={message} />)
          )}
        </div>
      </div>

      <div className="room__desk">
        <div className="room__column">
          <Composer onSend={send} busy={busy || !projectId} />
        </div>
      </div>
    </div>
  );
}
