import { useEffect, useState } from "react";
import { Link, useNavigate } from "@tanstack/react-router";
import {
  ArrowLeft,
  ArrowRight,
  ArrowUp,
  LoaderCircle,
  LogOut,
  MessageSquare,
  Scale,
} from "lucide-react";
import { useLegal } from "@/lib/legal/store";
import { createHandoff, askLegalAssistant, endHandoff } from "@/lib/legal/api";
import { uid, overall, type Chat } from "@/lib/legal/types";
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
  const [processing, setProcessing] = useState(false),
    [sharing, setSharing] = useState(false),
    [busy, setBusy] = useState(false),
    [error, setError] = useState("");
  const session = data.sessions.find((s) => s.id === sessionId);
  const evaluation = session?.evaluations.find((e) => e.id === evaluationId);
  async function connect(event: React.FormEvent) {
    event.preventDefault();
    if (!processing || busy) return;
    setBusy(true);
    setError("");
    try {
      const result = await createHandoff(
        sharing ? session : undefined,
        evaluationId,
        processing,
        sharing,
      );
      const chat: Chat = {
        id: uid(),
        ...(session ? { sessionId: session.id } : {}),
        ...(evaluation ? { evaluationId: evaluation.id } : {}),
        lawyer: "AI legal assistant",
        status: "active",
        createdAt: new Date().toISOString(),
        messages: [],
        preview: false,
        handoffToken: result.handoffToken,
        handoffId: result.handoffId,
        consentedAt: result.consentedAt,
        contextShared: result.contextShared,
      };
      setData((d) => ({ ...d, chats: [chat, ...d.chats] }));
      void navigate({ to: "/chats", search: { chat: chat.id } });
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not create a consented connection.");
    } finally {
      setBusy(false);
    }
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
          className="cc-quiet"
          to="/workspace"
          onClick={() => {
            if (session) setData((d) => ({ ...d, activeId: session.id }));
          }}
        >
          <ArrowLeft size={15} />
          Back to workspace
        </Link>
        {!ready ? (
          <p>Loading…</p>
        ) : (
          <form className="cc-connection-card cc-enter" onSubmit={connect}>
            <span className="cc-eyebrow">Lawyer service preview</span>
            <h1>A conversation with more context.</h1>
            <p className="cc-muted">
              For now you will talk to an AI legal assistant using the same Gemini service as the
              main assistant. No real lawyer is connected.
            </p>
            {session && (
              <div className="cc-context-summary">
                <span>
                  {session.jurisdiction} · {session.lawDate}
                </span>
                <h3>{evaluation?.question ?? session.title}</h3>
                <p>
                  {session.messages.length} inquiry messages · {session.evaluations.length} answer
                  assessments, including all reviewer research and scorer conversations.
                </p>
                {evaluation && (
                  <small>Selected assessment: {overall(evaluation.reviews) ?? "Pending"}</small>
                )}
              </div>
            )}
            <label className="cc-consent">
              <input
                type="checkbox"
                checked={processing}
                onChange={(e) => setProcessing(e.target.checked)}
              />
              <span>I agree to send my messages to the configured external AI service.</span>
            </label>
            {session && (
              <label className="cc-consent">
                <input
                  type="checkbox"
                  checked={sharing}
                  onChange={(e) => setSharing(e.target.checked)}
                />
                <span>
                  Share this entire inquiry, main AI answers, all reviewer scores, sources, findings
                  and scorer conversations with the AI legal assistant. Leaving this unchecked
                  starts without that context.
                </span>
              </label>
            )}
            <p className="cc-fineprint">
              Shared context is a snapshot taken when you continue; later inquiry changes are not
              shared automatically. You can revoke it from the chat. Use fictional or public
              information in this demo.
            </p>
            {error && (
              <p className="cc-alert" role="alert">
                {error}
              </p>
            )}
            <button className="cc-button" disabled={!processing || busy}>
              {busy ? <LoaderCircle size={16} className="cc-spin" /> : <MessageSquare size={16} />}
              Open AI legal assistant chat <ArrowRight size={15} />
            </button>
          </form>
        )}
      </main>
    </div>
  );
}

export function LawyerChats({ chatId }: { chatId?: string | undefined }) {
  const { data, setData, ready, storageError } = useLegal();
  const [input, setInput] = useState("");
  const chat = data.chats.find((c) => c.id === chatId);
  const session = data.sessions.find((s) => s.id === chat?.sessionId);
  const evaluation = session?.evaluations.find((e) => e.id === chat?.evaluationId);
  useEffect(() => setInput(""), [chatId]);
  function update(id: string, fn: (c: Chat) => Chat) {
    setData((d) => ({ ...d, chats: d.chats.map((c) => (c.id === id ? fn(c) : c)) }));
  }
  async function send(event: React.FormEvent) {
    event.preventDefault();
    if (!chat || !chat.handoffToken || chat.status !== "active" || chat.busy || !input.trim())
      return;
    const text = input.trim(),
      id = chat.id;
    setInput("");
    update(id, (c) => ({
      ...c,
      busy: true,
      error: undefined,
      messages: [...c.messages, { id: uid(), role: "user", text }],
    }));
    try {
      const result = await askLegalAssistant(chat.handoffToken, text);
      update(id, (c) =>
        c.status !== "active"
          ? c
          : {
              ...c,
              backendMode: result.mode,
              messages: [...c.messages, { id: uid(), role: "assistant", text: result.answer }],
            },
      );
    } catch (e) {
      update(id, (c) => ({
        ...c,
        error: e instanceof Error ? e.message : "The AI assistant could not respond.",
      }));
    } finally {
      update(id, (c) => ({ ...c, busy: false }));
    }
  }
  async function leave(revoke = false) {
    if (
      !chat ||
      !window.confirm(
        revoke
          ? "Revoke future use of shared context and end this conversation? Already processed information cannot be recalled from providers."
          : "End this conversation? Its history will remain saved.",
      )
    )
      return;
    try {
      if (chat.handoffToken) await endHandoff(chat.handoffToken, revoke);
      update(chat.id, (c) => ({
        ...c,
        status: "closed",
        busy: false,
        ...(revoke ? { contextShared: false } : {}),
        error: undefined,
      }));
    } catch (e) {
      update(chat.id, (c) => ({
        ...c,
        error: e instanceof Error ? e.message : "Could not end the backend conversation. Retry.",
      }));
    }
  }
  return (
    <div className="cc-page cc-enter">
      <header className="cc-topbar">
        <Brand />
        <Link to="/connect" search={{ session: "", evaluation: "" }} className="cc-quiet">
          <MessageSquare size={15} />
          New AI legal assistant chat
        </Link>
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
      <main className={`cc-chat-layout ${chat ? "cc-chat-selected" : ""}`}>
        <aside className="cc-chat-list">
          <div className="cc-chat-list-title">
            <h1>Chats</h1>
            <span className="cc-muted">Assistant inquiries and legal assistant conversations</span>
          </div>
          {!ready ? (
            <p>Loading…</p>
          ) : (
            <>
              <h2 className="cc-chat-section-title">Legal assistant inquiries</h2>
              {data.sessions.map((s) => (
                <Link
                  key={s.id}
                  to="/workspace"
                  onClick={() => setData((d) => ({ ...d, activeId: s.id }))}
                  className="cc-chat-link"
                >
                  <span className="cc-avatar">AI</span>
                  <div>
                    <strong>{s.title}</strong>
                    <p>{s.messages.at(-1)?.text ?? "No messages yet"}</p>
                    <small>{s.messages.length} messages</small>
                  </div>
                </Link>
              ))}
              <h2 className="cc-chat-section-title">Lawyer service · AI placeholder</h2>
              {data.chats.map((c) => (
                <Link
                  key={c.id}
                  to="/chats"
                  search={{ chat: c.id }}
                  className={`cc-chat-link ${c.id === chat?.id ? "active" : ""}`}
                >
                  <span className="cc-avatar">AI</span>
                  <div>
                    <strong>AI legal assistant</strong>
                    <p>{c.messages.at(-1)?.text ?? "No messages yet"}</p>
                    <small>
                      {c.status === "closed"
                        ? "Ended"
                        : c.handoffToken
                          ? "Connected to AI"
                          : "Consent needed"}{" "}
                      · {new Date(c.createdAt).toLocaleDateString()}
                    </small>
                  </div>
                </Link>
              ))}
              {!data.chats.length && (
                <p className="cc-chat-empty-note cc-muted">
                  No legal assistant chats yet. You can connect directly without an inquiry.
                </p>
              )}
            </>
          )}
        </aside>
        <section className="cc-chat-detail" key={chat?.id ?? "empty"}>
          {!chat ? (
            <div className="cc-empty">
              <Scale size={34} />
              <h2>Your conversations, together.</h2>
              <p>Select a saved chat or start a direct AI legal assistant conversation.</p>
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
                <span className="cc-avatar">AI</span>
                <div>
                  <h2>AI legal assistant</h2>
                  <small>
                    Model-backed placeholder · not a real lawyer
                    {chat.backendMode === "mock" ? " · mock mode" : ""}
                  </small>
                </div>
                {chat.status === "active" && (
                  <button className="cc-quiet" disabled={chat.busy} onClick={() => void leave()}>
                    <LogOut size={15} />
                    Leave
                  </button>
                )}
              </div>
              {session ? (
                <Link
                  to="/workspace"
                  className="cc-chat-context"
                  onClick={() => setData((d) => ({ ...d, activeId: session.id }))}
                >
                  Original inquiry: {evaluation?.question ?? session.title}
                  <ArrowRight size={14} />
                </Link>
              ) : (
                <p className="cc-chat-context">
                  {chat.sessionId
                    ? "The original inquiry was deleted; the consented backend snapshot remains until revoked."
                    : "Direct AI legal assistant conversation · no inquiry attached"}
                </p>
              )}
              {chat.handoffToken && (
                <div className="cc-handoff-status">
                  <span>
                    {chat.contextShared
                      ? "Full inquiry/reviewer snapshot shared with your consent"
                      : "No inquiry context shared"}{" "}
                    · {chat.consentedAt ? new Date(chat.consentedAt).toLocaleString() : ""}
                  </span>
                  {chat.status === "active" && (
                    <button className="cc-text-link" onClick={() => void leave(true)}>
                      Revoke consent & end
                    </button>
                  )}
                </div>
              )}
              <div className="cc-messages cc-enter">
                {!chat.messages.length ? (
                  <div className="cc-empty">
                    <MessageSquare size={28} />
                    <h3>Ask your next question.</h3>
                    <p>
                      {chat.contextShared
                        ? "The backend has saved your consented inquiry and reviewer snapshot for this AI conversation."
                        : "This AI conversation has no shared inquiry context."}
                    </p>
                  </div>
                ) : (
                  chat.messages.map((m) => (
                    <article key={m.id} className={`cc-message ${m.role}`}>
                      <div className="cc-message-label">
                        {m.role === "user" ? "You" : "AI legal assistant"}
                      </div>
                      <Markdown text={m.text} />
                    </article>
                  ))
                )}
                {chat.busy && (
                  <p className="cc-progress" role="status">
                    <LoaderCircle className="cc-spin" size={15} />
                    Considering the conversation and consented context…
                  </p>
                )}
                {chat.error && (
                  <div className="cc-alert" role="alert">
                    {chat.error}
                    <button
                      className="cc-quiet"
                      onClick={() =>
                        setInput(chat.messages.filter((m) => m.role === "user").at(-1)?.text ?? "")
                      }
                    >
                      Restore last question
                    </button>
                  </div>
                )}
              </div>
              <div className="cc-composer-area">
                {chat.status === "closed" ? (
                  <p className="cc-fineprint">Conversation ended. History remains saved.</p>
                ) : !chat.handoffToken ? (
                  <Link
                    className="cc-button"
                    to="/connect"
                    search={{ session: chat.sessionId ?? "", evaluation: chat.evaluationId ?? "" }}
                  >
                    Reconnect with consent
                  </Link>
                ) : (
                  <>
                    <form className="cc-composer" onSubmit={send}>
                      <textarea
                        aria-label="Message to AI legal assistant"
                        placeholder="Write a message…"
                        value={input}
                        rows={2}
                        onChange={(e) => setInput(e.target.value)}
                      />
                      <button
                        className="cc-send"
                        aria-label="Send to AI legal assistant"
                        disabled={!input.trim() || chat.busy}
                      >
                        <ArrowUp size={18} />
                      </button>
                    </form>
                    <p className="cc-fineprint">
                      AI legal assistant · no human lawyer is connected. Messages are saved locally
                      and on this backend.
                    </p>
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
