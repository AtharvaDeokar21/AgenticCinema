"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import Backdrop from "@/components/chat/Backdrop";
import Composer from "@/components/chat/Composer";
import Message from "@/components/chat/Message";
import { sendToCrew } from "@/lib/chatApi";
import { TicketStub } from "@/components/props";

const OPENERS = [
  "Write me a 60-second explainer on UPI credit lines",
  "Plan the shots for the script we just wrote",
  "Here's my footage — where does the audio go?",
  "Check this script for rights problems",
];

let seq = 0;
const nextId = () => `m${++seq}`;

export default function ChatRoom() {
  const [messages, setMessages] = useState([]);
  const [busy, setBusy] = useState(false);
  const [drift, setDrift] = useState(0);
  const transcriptRef = useRef(null);
  const projectId = useRef(`proj_${Math.random().toString(36).slice(2, 9)}`);
  const objectUrls = useRef([]);

  /* Object URLs are for previewing what the creator attached; release them
     when the page goes away so the blobs are not held forever. */
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
        const history = messages
          .filter((m) => !m.pending && !m.error)
          .slice(-10)
          .map((m) => ({ role: m.role, text: m.text }));

        const reply = await sendToCrew({
          project_id: projectId.current,
          message: text,
          history,
          files,
        });

        setMessages((prev) =>
          prev.map((m) =>
            m.id === placeholder.id ? { ...m, ...reply, pending: false } : m
          )
        );
      } catch (error) {
        setMessages((prev) =>
          prev.map((m) =>
            m.id === placeholder.id
              ? { ...m, pending: false, error: error.message }
              : m
          )
        );
      } finally {
        setBusy(false);
      }
    },
    [messages]
  );

  return (
    <div className="room" style={{ "--drift": drift }}>
      <Backdrop />

      <header className="room__top">
        <Link href="/" className="room__back">
          <span aria-hidden="true">&#8592;</span> Back to the theatre
        </Link>
        <p className="room__title">The Green Room</p>
        <span className="room__file">{projectId.current}</span>
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
          <Composer onSend={send} busy={busy} />
        </div>
      </div>
    </div>
  );
}
