import { useEffect, useState } from "react";
import { Link, useNavigate } from "@tanstack/react-router";
import {
  ArrowLeft,
  ArrowRight,
  ArrowUp,
  Check,
  LoaderCircle,
  LogOut,
  MessageSquare,
  Scale,
} from "lucide-react";
import { useLegal } from "@/lib/legal/store";
import { uid, overall } from "@/lib/legal/types";
import { Brand, Markdown } from "./LegalWorkspace";
export function LawyerConnection({
  sessionId,
  evaluationId,
}: {
  sessionId: string;
  evaluationId: string;
}) {
  const { data, setData, ready } = useLegal();
  const navigate = useNavigate();
  const [matching, setMatching] = useState(true);
  const s = data.sessions.find((s) => s.id === sessionId),
    e = s?.evaluations.find((e) => e.id === evaluationId);
  useEffect(() => {
    const timer = setTimeout(() => setMatching(false), 900);
    return () => clearTimeout(timer);
  }, []);
  function connect() {
    const existing =
      s && e
        ? data.chats.find(
            (c) => c.sessionId === s.id && c.evaluationId === e.id && c.status === "active",
          )
        : data.chats.find((c) => !c.sessionId && c.status === "active");
    const id = existing?.id ?? uid();
    if (!existing)
      setData((d) => ({
        ...d,
        chats: [
          {
            id,
            ...(s && e ? { sessionId: s.id, evaluationId: e.id } : {}),
            lawyer: "Alex Morgan",
            status: "active",
            createdAt: new Date().toISOString(),
            messages: [],
            preview: true,
          },
          ...d.chats,
        ],
      }));
    void navigate({ to: "/chats", search: { chat: id } });
  }
  return (
    <div className="cc-page cc-enter">
      <header className="cc-topbar">
        <Brand />
        <Link className="cc-quiet" to="/chats" search={{ chat: undefined }}>
          <MessageSquare size={16} />
          Chats
        </Link>
      </header>
      <main className="cc-connection">
        <Link
          to="/workspace"
          className="cc-quiet"
          onClick={() => {
            if (s) setData((d) => ({ ...d, activeId: s.id }));
          }}
        >
          <ArrowLeft size={15} />
          Back to inquiry
        </Link>
        {!ready ? (
          <p>Opening connection…</p>
        ) : (
          <div className="cc-connection-card cc-enter">
            <span className="cc-eyebrow">A professional perspective</span>
            <h1>{matching ? "Finding your next step…" : "Meet your legal contact."}</h1>
            <p className="cc-muted">
              {s && e
                ? "Keep your inquiry, assessment and conversation together."
                : "Start a conversation whenever you want professional legal help."}
            </p>
            <div className="cc-match-profile">
              <span className="cc-avatar cc-avatar-large">
                {matching ? <LoaderCircle className="cc-spin" /> : "AM"}
              </span>
              <div>
                <h2>{matching ? "Preparing connection" : "Alex Morgan"}</h2>
                <span className="cc-badge">Placeholder lawyer · preview</span>
              </div>
              {!matching && <Check className="cc-gold" size={22} />}
            </div>
            <p className="cc-muted">
              {matching
                ? "Preparing a preview conversation…"
                : "Preview connection ready. No real lawyer has been contacted. Messages in this prototype are saved on this browser."}
            </p>
            {s && e && (
              <div className="cc-context-summary">
                <span>
                  {s.jurisdiction} · {s.lawDate}
                </span>
                <h3>{e.question}</h3>
                <small>
                  Assessment: {overall(e.reviews) ?? "Pending"}
                  {overall(e.reviews) !== null ? "/100" : ""}
                </small>
              </div>
            )}
            <button className="cc-button" disabled={matching} onClick={connect}>
              Open chat <ArrowRight size={16} />
            </button>
          </div>
        )}
      </main>
    </div>
  );
}
export function LawyerChats({ chatId }: { chatId?: string | undefined }) {
  const { data, setData, ready, storageError } = useLegal();
  const [input, setInput] = useState("");
  const c = data.chats.find((c) => c.id === chatId);
  const s = data.sessions.find((s) => s.id === c?.sessionId),
    e = s?.evaluations.find((e) => e.id === c?.evaluationId);
  useEffect(() => setInput(""), [chatId]);
  function send(event: React.FormEvent) {
    event.preventDefault();
    if (!c || !input.trim() || c.status === "closed") return;
    const text = input.trim();
    setData((d) => ({
      ...d,
      chats: d.chats.map((v) =>
        v.id === c.id ? { ...v, messages: [...v.messages, { id: uid(), role: "user", text }] } : v,
      ),
    }));
    setInput("");
  }
  function leave() {
    if (!c || !window.confirm("End this conversation? Your messages will remain in Chats.")) return;
    setData((d) => ({
      ...d,
      chats: d.chats.map((v) => (v.id === c.id ? { ...v, status: "closed" } : v)),
    }));
  }
  return (
    <div className="cc-page cc-enter">
      <header className="cc-topbar">
        <Brand />
        <Link to="/workspace" className="cc-quiet">
          <ArrowLeft size={15} />
          Workspace
        </Link>
      </header>
      {storageError && (
        <p className="cc-alert" role="alert">
          {storageError}
        </p>
      )}
      <main className={`cc-chat-layout ${c ? "cc-chat-selected" : ""}`}>
        <aside className="cc-chat-list">
          <div className="cc-chat-list-title">
            <h1>Chats</h1>
            <span className="cc-muted">{data.chats.length} conversations</span>
          </div>
          {!ready ? (
            <p>Loading chats…</p>
          ) : (
            <>
              <h2 className="cc-chat-section-title">Legal assistant inquiries</h2>
              {data.sessions.length ? (
                data.sessions.map((inquiry) => (
                  <Link
                    key={inquiry.id}
                    to="/workspace"
                    onClick={() => setData((d) => ({ ...d, activeId: inquiry.id }))}
                    className="cc-chat-link"
                  >
                    <span className="cc-avatar">AI</span>
                    <div>
                      <strong>{inquiry.title}</strong>
                      <p>{inquiry.messages.at(-1)?.text ?? "No messages yet"}</p>
                      <small>Legal assistant · {inquiry.messages.length} messages</small>
                    </div>
                  </Link>
                ))
              ) : (
                <p className="cc-muted">No assistant inquiries yet.</p>
              )}
              <h2 className="cc-chat-section-title">Lawyer conversations</h2>
              {data.chats.length ? (
                data.chats.map((v) => (
                  <Link
                    key={v.id}
                    to="/chats"
                    search={{ chat: v.id }}
                    className={`cc-chat-link ${v.id === c?.id ? "active" : ""}`}
                  >
                    <span className="cc-avatar">AM</span>
                    <div>
                      <strong>{v.lawyer}</strong>
                      <p>{v.messages.at(-1)?.text || "No messages yet"}</p>
                      <small>
                        {v.status === "closed" ? "Ended" : "Preview conversation"} ·{" "}
                        {new Date(v.createdAt).toLocaleDateString()}
                      </small>
                    </div>
                  </Link>
                ))
              ) : (
                <p className="cc-muted cc-chat-empty-note">
                  No lawyer conversations yet.{" "}
                  <Link to="/connect" search={{ session: "", evaluation: "" }}>
                    Connect directly
                  </Link>
                </p>
              )}
            </>
          )}
        </aside>
        <section className="cc-chat-detail" key={c?.id ?? "none"}>
          {!c ? (
            <div className="cc-empty">
              <Scale size={34} />
              <h2>{chatId ? "Conversation unavailable" : "Your conversations, together."}</h2>
              <p>Select a saved chat to pick up where you left off.</p>
            </div>
          ) : (
            <>
              <div className="cc-chat-header">
                <Link
                  to="/chats"
                  search={{ chat: undefined }}
                  className="cc-icon cc-mobile-back"
                  aria-label="All chats"
                >
                  <ArrowLeft size={18} />
                </Link>
                <span className="cc-avatar">AM</span>
                <div>
                  <h2>{c.lawyer}</h2>
                  <small>
                    Placeholder lawyer ·{" "}
                    {c.status === "closed" ? "Conversation ended" : "Preview conversation"}
                  </small>
                </div>
                {c.status === "active" && (
                  <button className="cc-quiet" onClick={leave}>
                    <LogOut size={15} />
                    Leave
                  </button>
                )}
              </div>
              {s ? (
                <Link
                  to="/workspace"
                  className="cc-chat-context"
                  onClick={() => setData((d) => ({ ...d, activeId: s.id }))}
                >
                  Original inquiry: {e?.question ?? s.title}
                  <ArrowRight size={14} />
                </Link>
              ) : (
                <p className="cc-chat-context">
                  The original inquiry was deleted. Your chat remains saved.
                </p>
              )}
              <div className="cc-messages cc-enter">
                {!c.messages.length ? (
                  <div className="cc-empty">
                    <MessageSquare size={28} />
                    <h3>Your chat is ready.</h3>
                    <p>This is a local preview. No messages are sent to a lawyer.</p>
                  </div>
                ) : (
                  c.messages.map((m) => (
                    <article className={`cc-message ${m.role}`} key={m.id}>
                      <div className="cc-message-label">{m.role === "user" ? "You" : c.lawyer}</div>
                      <Markdown text={m.text} />
                      <small className="cc-muted">Saved locally · not delivered</small>
                    </article>
                  ))
                )}
              </div>
              <div className="cc-composer-area">
                {c.status === "closed" ? (
                  <p className="cc-fineprint">
                    Conversation ended. Your history remains available.
                  </p>
                ) : (
                  <>
                    <form className="cc-composer" onSubmit={send}>
                      <textarea
                        aria-label="Message to lawyer"
                        placeholder="Write a message…"
                        rows={2}
                        value={input}
                        onChange={(ev) => setInput(ev.target.value)}
                      />
                      <button
                        className="cc-send"
                        aria-label="Save message"
                        disabled={!input.trim()}
                      >
                        <ArrowUp size={18} />
                      </button>
                    </form>
                    <p className="cc-fineprint">Preview chat · messages stay on this browser.</p>
                  </>
                )}
              </div>
            </>
          )}
        </section>
      </main>
    </div>
  );
}
