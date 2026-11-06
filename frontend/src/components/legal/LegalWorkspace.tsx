import { useEffect, useState } from "react";
import { Link } from "@tanstack/react-router";
import {
  ArrowUp,
  ChevronDown,
  ExternalLink,
  FileDown,
  LoaderCircle,
  MessageSquare,
  PanelLeftClose,
  PanelLeftOpen,
  Plus,
  RotateCcw,
  Scale,
  ShieldCheck,
  Trash2,
} from "lucide-react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { useLegal } from "@/lib/legal/store";
import { ScorerChat } from "./ScorerChat";
import { generateAnswer, previewMode, reviewAnswer } from "@/lib/legal/api";
import {
  categories,
  newSession,
  overall,
  reviewers,
  uid,
  type Evaluation,
  type Feedback,
  type Review,
  type Session,
} from "@/lib/legal/types";
export function Brand() {
  return (
    <Link to="/" className="cc-brand">
      <Scale size={22} />
      CounselCheck
    </Link>
  );
}
export function Markdown({ text }: { text: string }) {
  return (
    <div className="prose-report">
      <ReactMarkdown remarkPlugins={[remarkGfm]}>{text}</ReactMarkdown>
    </div>
  );
}
export function ExportButton({
  session,
  evaluation,
}: {
  session: Session;
  evaluation: Evaluation;
}) {
  function download() {
    const row = {
      domain: "legal",
      jurisdiction: session.jurisdiction,
      law_date: session.lawDate,
      question: evaluation.question,
      ai_response: evaluation.answer,
      generated_at: evaluation.createdAt,
      provenance: evaluation.mode,
      automated_assessments: evaluation.reviews,
      overall_score: overall(evaluation.reviews),
      expert_feedback: evaluation.feedback ?? null,
      review_status: evaluation.feedback?.submittedAt
        ? "expert_feedback_submitted"
        : "awaiting_expert_review",
      expert_identity_verified: false,
    };
    const url = URL.createObjectURL(
      new Blob([JSON.stringify(row) + "\n"], { type: "application/x-ndjson" }),
    );
    const a = document.createElement("a");
    a.href = url;
    a.download = `counselcheck-${evaluation.id}.jsonl`;
    a.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }
  return (
    <button
      className="cc-icon"
      onClick={download}
      title="Export evaluation as JSONL"
      aria-label="Export evaluation as JSONL"
    >
      <FileDown size={17} />
    </button>
  );
}
export function LegalWorkspace() {
  const { data, setData, ready, storageError } = useLegal();
  const [mobileOpen, setMobileOpen] = useState(false),
    [tab, setTab] = useState("answer"),
    [input, setInput] = useState(""),
    [selected, setSelected] = useState<string>(),
    [paste, setPaste] = useState(false),
    [pasted, setPasted] = useState("");
  const session = data.sessions.find((s) => s.id === data.activeId) ?? data.sessions[0];
  const evaluation =
    session?.evaluations.find((e) => e.id === selected) ?? session?.evaluations.at(-1);
  useEffect(() => {
    setInput("");
    setSelected(undefined);
    setPaste(false);
    setPasted("");
  }, [session?.id]);
  const update = (sid: string, fn: (s: Session) => Session) =>
    setData((d) => ({ ...d, sessions: d.sessions.map((s) => (s.id === sid ? fn(s) : s)) }));
  const updateReview = (sid: string, eid: string, r: Review) =>
    update(sid, (s) => ({
      ...s,
      evaluations: s.evaluations.map((e) =>
        e.id === eid ? { ...e, reviews: e.reviews.map((v) => (v.id === r.id ? r : v)) } : e,
      ),
    }));
  async function runReview(s: Session, e: Evaluation, id: Review["id"]) {
    updateReview(s.id, e.id, { id, status: "searching" });
    try {
      updateReview(
        s.id,
        e.id,
        await reviewAnswer(id, {
          question: e.question,
          answer: e.answer,
          jurisdiction: s.jurisdiction,
          lawDate: s.lawDate,
        }),
      );
    } catch (error) {
      updateReview(s.id, e.id, {
        id,
        status: "error",
        error: error instanceof Error ? error.message : "Review failed.",
      });
    }
  }
  function addEvaluation(s: Session, question: string, answer: string) {
    const e: Evaluation = {
      id: uid(),
      question,
      answer,
      reviews: reviewers.map((r) => ({ id: r.id, status: "queued" })),
      mode: previewMode ? "preview" : "live",
      createdAt: new Date().toISOString(),
    };
    update(s.id, (v) => ({
      ...v,
      evaluations: [...v.evaluations, e],
      busy: false,
      messages: [...v.messages, { id: uid(), role: "assistant", text: answer }],
    }));
    setSelected(e.id);
    void Promise.all(reviewers.map((r) => runReview(s, e, r.id)));
  }
  async function submit(event: React.FormEvent) {
    event.preventDefault();
    if (
      !session ||
      session.busy ||
      !input.trim() ||
      !session.jurisdiction.trim() ||
      !session.lawDate
    )
      return;
    const q = input.trim();
    setInput("");
    update(session.id, (s) => ({
      ...s,
      busy: true,
      error: undefined,
      title: s.messages.length ? s.title : q.slice(0, 55),
      messages: [...s.messages, { id: uid(), role: "user", text: q }],
    }));
    try {
      addEvaluation(session, q, await generateAnswer(session, q));
    } catch (error) {
      update(session.id, (s) => ({
        ...s,
        busy: false,
        error: error instanceof Error ? error.message : "Answer failed.",
      }));
    }
  }
  function create() {
    const s = newSession();
    setData((d) => ({ ...d, sessions: [s, ...d.sessions], activeId: s.id }));
    setMobileOpen(false);
  }
  function remove(s: Session) {
    if (s.busy || !window.confirm("Delete this inquiry? Linked lawyer chats will remain saved."))
      return;
    setData((d) => {
      const rest = d.sessions.filter((x) => x.id !== s.id);
      if (!rest.length) rest.push(newSession());
      return { ...d, sessions: rest, activeId: d.activeId === s.id ? rest[0]!.id : d.activeId };
    });
  }
  if (!ready)
    return (
      <div className="cc-loading">
        <LoaderCircle className="cc-spin" />
        Opening workspace…
      </div>
    );
  if (!session)
    return (
      <div className="cc-empty">
        <p>{storageError || "Start your first inquiry."}</p>
        <button className="cc-button" onClick={create}>
          New inquiry
        </button>
      </div>
    );
  const score = evaluation ? overall(evaluation.reviews) : null;
  return (
    <div className="cc-app cc-enter">
      {mobileOpen && (
        <button
          className="cc-overlay"
          aria-label="Close navigation"
          onClick={() => setMobileOpen(false)}
        />
      )}
      <aside
        className={`cc-sidebar ${data.collapsed ? "cc-collapsed" : ""} ${mobileOpen ? "cc-mobile-open" : ""}`}
      >
        <div className="cc-sidebar-head">
          <Brand />
          <button
            className="cc-icon"
            aria-label="Collapse sidebar"
            onClick={() => {
              setData((d) => ({ ...d, collapsed: true }));
              setMobileOpen(false);
            }}
          >
            <PanelLeftClose size={18} />
          </button>
        </div>
        <button className="cc-button cc-new" onClick={create}>
          <Plus size={17} />
          New inquiry
        </button>
        <Link to="/chats" search={{ chat: undefined }} className="cc-nav">
          <MessageSquare size={17} />
          Chats <span>{data.chats.length || ""}</span>
        </Link>
        <p className="cc-eyebrow cc-history-label">Your inquiries</p>
        <div className="cc-session-list">
          {data.sessions.map((s) => (
            <div className={`cc-session ${session.id === s.id ? "active" : ""}`} key={s.id}>
              <button
                onClick={() => {
                  setData((d) => ({ ...d, activeId: s.id }));
                  setMobileOpen(false);
                }}
              >
                {s.title}
              </button>
              <button
                className="cc-icon"
                disabled={s.busy}
                aria-label={`Delete ${s.title}`}
                onClick={() => remove(s)}
              >
                <Trash2 size={14} />
              </button>
            </div>
          ))}
        </div>
        <div className="cc-sidebar-foot">
          <span className="cc-avatar">CC</span>
          <div>
            CounselCheck<small>Legal intelligence workspace</small>
          </div>
        </div>
      </aside>
      <main className="cc-workspace">
        <header className="cc-topbar">
          <button
            className="cc-icon"
            aria-label="Open navigation"
            onClick={() => {
              setData((d) => ({ ...d, collapsed: false }));
              setMobileOpen(true);
            }}
          >
            <PanelLeftOpen size={19} />
          </button>
          <span className="cc-title">{session.title}</span>
          {previewMode && <span className="cc-badge">Preview mode</span>}
          <Link to="/chats" search={{ chat: undefined }} className="cc-quiet">
            <MessageSquare size={16} />
            Chats
          </Link>
        </header>
        {storageError && (
          <div className="cc-alert" role="alert">
            {storageError}
          </div>
        )}
        <div className="cc-mobile-tabs" role="tablist" aria-label="Workspace panels">
          {["answer", "assessment"].map((t) => (
            <button
              key={t}
              role="tab"
              aria-selected={tab === t}
              aria-controls={`cc-${t}`}
              onClick={() => setTab(t)}
            >
              {t === "answer" ? "Legal assistant" : "Three-agent assessment"}
            </button>
          ))}
        </div>
        <div className="cc-panels">
          <section
            id="cc-answer"
            className={`cc-answer ${tab !== "answer" ? "cc-mobile-hidden" : ""}`}
          >
            <div className="cc-panel-heading">
              <Scale size={18} />
              <h2>Legal assistant</h2>
              <span>Ask. Explore. Understand.</span>
            </div>
            <div className="cc-context">
              <label>
                Jurisdiction
                <input
                  value={session.jurisdiction}
                  placeholder="e.g. United States · California"
                  disabled={session.busy || !!session.evaluations.length}
                  onChange={(e) =>
                    update(session.id, (s) => ({ ...s, jurisdiction: e.target.value }))
                  }
                />
              </label>
              <label>
                Law as of
                <input
                  type="date"
                  value={session.lawDate}
                  disabled={session.busy || !!session.evaluations.length}
                  onChange={(e) => update(session.id, (s) => ({ ...s, lawDate: e.target.value }))}
                />
              </label>
            </div>
            <div className="cc-messages">
              {!session.messages.length ? (
                <div className="cc-empty cc-question-empty">
                  <span className="cc-emblem">
                    <Scale size={30} />
                  </span>
                  <h1>What needs a closer look?</h1>
                  <p>
                    Choose a jurisdiction and ask your legal question.
                    <br />
                    Three reviewers will examine the answer.
                  </p>
                </div>
              ) : (
                session.messages.map((m) => (
                  <article key={m.id} className={`cc-message ${m.role}`}>
                    <div className="cc-message-label">
                      {m.role === "user" ? "You" : "CounselCheck"}
                    </div>
                    <Markdown text={m.text} />
                  </article>
                ))
              )}
              {session.busy && (
                <p className="cc-progress" role="status">
                  <LoaderCircle size={16} className="cc-spin" />
                  Preparing your answer…
                </p>
              )}
              {session.error && (
                <div className="cc-alert" role="alert">
                  {session.error}
                  <button
                    className="cc-quiet"
                    onClick={() =>
                      setInput(session.messages.filter((m) => m.role === "user").at(-1)?.text ?? "")
                    }
                  >
                    Restore question
                  </button>
                </div>
              )}
            </div>
            <div className="cc-composer-area">
              <form className="cc-composer" onSubmit={submit}>
                <textarea
                  aria-label="Legal question"
                  placeholder="Ask a legal question…"
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  rows={2}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) {
                      e.preventDefault();
                      e.currentTarget.form?.requestSubmit();
                    }
                  }}
                />
                <button
                  className="cc-send"
                  aria-label="Send legal question"
                  disabled={
                    session.busy ||
                    !input.trim() ||
                    !session.jurisdiction.trim() ||
                    !session.lawDate
                  }
                >
                  {session.busy ? (
                    <LoaderCircle size={18} className="cc-spin" />
                  ) : (
                    <ArrowUp size={18} />
                  )}
                </button>
              </form>
              <div className="cc-composer-note">
                <span>AI answers need independent review.</span>
                <button onClick={() => setPaste((v) => !v)} className="cc-text-link">
                  Review an existing answer
                </button>
              </div>
              {paste && (
                <form
                  className="cc-paste cc-enter"
                  onSubmit={(e) => {
                    e.preventDefault();
                    const q =
                      input.trim() ||
                      session.messages.filter((m) => m.role === "user").at(-1)?.text;
                    if (!q || !pasted.trim()) return;
                    addEvaluation(session, q, pasted.trim());
                    setPaste(false);
                    setPasted("");
                    setInput("");
                  }}
                >
                  <label>
                    Enter the original question above, then paste the answer
                    <textarea
                      aria-label="Existing legal answer"
                      rows={4}
                      value={pasted}
                      onChange={(e) => setPasted(e.target.value)}
                    />
                  </label>
                  <button
                    className="cc-button"
                    disabled={
                      session.busy ||
                      !pasted.trim() ||
                      !session.jurisdiction.trim() ||
                      !session.lawDate ||
                      !(input.trim() || session.messages.some((m) => m.role === "user"))
                    }
                  >
                    Assess answer
                  </button>
                </form>
              )}
            </div>
          </section>
          <section
            id="cc-assessment"
            className={`cc-assessment ${tab !== "assessment" ? "cc-mobile-hidden" : ""}`}
          >
            <div className="cc-panel-heading">
              <ShieldCheck size={18} />
              <h2>Independent assessment</h2>
              <span>3 reviewers</span>
            </div>
            <div className="cc-review-scroll" key={evaluation?.id ?? "empty"}>
              {!evaluation ? (
                <div className="cc-empty">
                  <ShieldCheck size={32} />
                  <h3>Evidence before confidence.</h3>
                  <p>Your answer will be examined for authority, jurisdiction and reasoning.</p>
                </div>
              ) : (
                <>
                  <div className="cc-review-toolbar">
                    <label>
                      Answer
                      <select value={evaluation.id} onChange={(e) => setSelected(e.target.value)}>
                        {session.evaluations.map((e, i) => (
                          <option key={e.id} value={e.id}>
                            Answer {i + 1} · {e.question.slice(0, 35)}
                          </option>
                        ))}
                      </select>
                    </label>
                    <ExportButton session={session} evaluation={evaluation} />
                  </div>
                  <div className="cc-score-card cc-enter">
                    <div>
                      <span className="cc-eyebrow">Overall assessment</span>
                      <p className="cc-score">
                        {score ?? "—"}
                        <small>/100</small>
                      </p>
                    </div>
                    <span className="cc-score-caption">
                      {evaluation.mode === "preview"
                        ? "Illustrative scores · no research performed"
                        : score === null
                          ? "Waiting for all three reviewers"
                          : "Average of three reviewer scores"}
                    </span>
                  </div>
                  {reviewers.map((r) => {
                    const result = evaluation.reviews.find((v) => v.id === r.id);
                    return (
                      <div className="cc-review-card cc-enter" key={r.id}>
                        <header>
                          <span className="cc-review-icon">
                            <ShieldCheck size={17} />
                          </span>
                          <div>
                            <h3>{r.name}</h3>
                            <small>{result?.model || r.focus}</small>
                          </div>
                          <strong>
                            {result?.status === "complete" ? (
                              `${result.score}/100`
                            ) : result?.status === "searching" || result?.status === "queued" ? (
                              <LoaderCircle size={17} className="cc-spin" />
                            ) : (
                              "—"
                            )}
                          </strong>
                        </header>
                        <div aria-live="polite">
                          {result?.status === "searching" || result?.status === "queued" ? (
                            <p className="cc-muted">
                              {previewMode
                                ? "Preparing preview assessment…"
                                : "Researching authorities and assessing the answer…"}
                            </p>
                          ) : result?.status === "error" ? (
                            <div className="cc-alert">
                              <p>{result.error}</p>
                              <button
                                className="cc-quiet"
                                onClick={() => void runReview(session, evaluation, r.id)}
                              >
                                <RotateCcw size={13} />
                                Retry reviewer
                              </button>
                            </div>
                          ) : (
                            <>
                              <p>{result?.explanation}</p>
                              {!!result?.findings?.length && (
                                <ul>
                                  {result.findings.map((f, i) => (
                                    <li key={i}>{f}</li>
                                  ))}
                                </ul>
                              )}
                              {!!result?.sources?.length ? (
                                <details>
                                  <summary>
                                    View {result.sources.length} sources <ChevronDown size={13} />
                                  </summary>
                                  {result.sources.map((s, i) => (
                                    <a
                                      className="cc-source"
                                      key={i}
                                      href={s.url}
                                      target="_blank"
                                      rel="noreferrer"
                                    >
                                      {s.title}
                                      <ExternalLink size={12} />
                                    </a>
                                  ))}
                                </details>
                              ) : (
                                <small className="cc-muted">
                                  {evaluation.mode === "preview"
                                    ? "Preview · no sources searched"
                                    : "No source links supplied by this reviewer."}
                                </small>
                              )}
                            </>
                          )}
                        </div>
                      </div>
                    );
                  })}
                  <ScorerChat
                    session={session}
                    evaluation={evaluation}
                    onSave={(scorerMessages) =>
                      update(session.id, (s) => ({
                        ...s,
                        evaluations: s.evaluations.map((e) =>
                          e.id === evaluation.id ? { ...e, scorerMessages } : e,
                        ),
                      }))
                    }
                  />
                  <div
                    className={`cc-counsel-cta ${score !== null && score < 70 ? "emphasized" : ""}`}
                  >
                    <h3>
                      {score !== null && score < 70
                        ? "A lawyer can help clarify this."
                        : "Want a professional perspective?"}
                    </h3>
                    <p>
                      {score !== null && score < 70
                        ? "The assessment is below 70. Consult a lawyer about the answer and your circumstances."
                        : "Explore the answer with a lawyer whenever you need to."}
                    </p>
                    <Link
                      className={score !== null && score < 70 ? "cc-button" : "cc-quiet"}
                      to="/connect"
                      search={{ session: session.id, evaluation: evaluation.id }}
                    >
                      Connect to a lawyer <MessageSquare size={15} />
                    </Link>
                  </div>
                  <ExpertFeedback
                    evaluation={evaluation}
                    onSave={(feedback) =>
                      update(session.id, (s) => ({
                        ...s,
                        evaluations: s.evaluations.map((e) =>
                          e.id === evaluation.id ? { ...e, feedback } : e,
                        ),
                      }))
                    }
                  />
                  <p className="cc-fineprint">
                    Assessment scores reflect reviewer judgments, not the probability of legal
                    correctness.
                  </p>
                </>
              )}
            </div>
          </section>
        </div>
      </main>
    </div>
  );
}
const blank: Feedback = {
  verdict: "",
  categories: [],
  explanation: "",
  correction: "",
  authority: "",
  confidence: "",
  reviewer: "",
};
function ExpertFeedback({
  evaluation,
  onSave,
}: {
  evaluation: Evaluation;
  onSave: (f: Feedback) => void;
}) {
  const [f, setF] = useState<Feedback>(evaluation.feedback ?? blank),
    [saved, setSaved] = useState(false);
  useEffect(() => {
    setF(evaluation.feedback ?? blank);
    setSaved(false);
  }, [evaluation.id]);
  function change<K extends keyof Feedback>(key: K, value: Feedback[K]) {
    setF((v) => ({ ...v, [key]: value }));
    setSaved(false);
  }
  return (
    <details className="cc-feedback">
      <summary>
        Expert evaluation <ChevronDown size={15} />
      </summary>
      <form
        onSubmit={(e) => {
          e.preventDefault();
          onSave({ ...f, submittedAt: new Date().toISOString() });
          setSaved(true);
        }}
      >
        <p className="cc-muted">Capture an independent review with supporting authority.</p>
        <label>
          Reviewer name
          <input required value={f.reviewer} onChange={(e) => change("reviewer", e.target.value)} />
        </label>
        <label>
          Verdict
          <select
            required
            aria-label="Verdict"
            value={f.verdict}
            onChange={(e) => change("verdict", e.target.value)}
          >
            <option value="">Select a verdict</option>
            {[
              "Accurate",
              "Partially accurate",
              "Inaccurate / incomplete",
              "Requires further research",
            ].map((v) => (
              <option key={v}>{v}</option>
            ))}
          </select>
        </label>
        <fieldset>
          <legend>Error categories</legend>
          {categories.map((c) => (
            <label className="cc-checkbox" key={c}>
              <input
                type="checkbox"
                checked={f.categories.includes(c)}
                onChange={(e) =>
                  change(
                    "categories",
                    e.target.checked ? [...f.categories, c] : f.categories.filter((x) => x !== c),
                  )
                }
              />
              {c}
            </label>
          ))}
        </fieldset>
        <label>
          Explain your evaluation
          <textarea
            required
            rows={3}
            value={f.explanation}
            onChange={(e) => change("explanation", e.target.value)}
          />
        </label>
        <label>
          Corrected answer
          <textarea
            required={f.verdict === "Partially accurate" || f.verdict === "Inaccurate / incomplete"}
            rows={3}
            value={f.correction}
            onChange={(e) => change("correction", e.target.value)}
          />
        </label>
        <label>
          Supporting authority
          <textarea
            required
            rows={2}
            value={f.authority}
            onChange={(e) => change("authority", e.target.value)}
          />
        </label>
        <label>
          Confidence
          <select
            required
            aria-label="Confidence"
            value={f.confidence}
            onChange={(e) => change("confidence", e.target.value)}
          >
            <option value="">Select confidence</option>
            {["High", "Moderate", "Low"].map((c) => (
              <option key={c}>{c}</option>
            ))}
          </select>
        </label>
        <button className="cc-button">{saved ? "Evaluation saved" : "Save evaluation"}</button>
        <small className="cc-muted">
          Saved locally. Reviewer identity is not authenticated in this frontend.
        </small>
      </form>
    </details>
  );
}
