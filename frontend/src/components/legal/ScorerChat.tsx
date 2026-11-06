import { useState } from "react";
import { ArrowUp, LoaderCircle, MessageSquareMore } from "lucide-react";
import { askScorer, previewMode } from "@/lib/legal/api";
import { reviewers, uid, type Evaluation, type Session } from "@/lib/legal/types";
import { Markdown } from "./LegalWorkspace";

export function ScorerChat({
  session,
  evaluation,
  onSave,
}: {
  session: Session;
  evaluation: Evaluation;
  onSave: (messages: NonNullable<Evaluation["scorerMessages"]>) => void;
}) {
  const [prompt, setPrompt] = useState(""),
    [busy, setBusy] = useState(false),
    [error, setError] = useState("");
  const history = evaluation.scorerMessages ?? [];
  const hasEvidence =
    evaluation.answer.trim().length > 0 && evaluation.reviews.some((r) => r.status === "complete");
  async function send(event: React.FormEvent) {
    event.preventDefault();
    const question = prompt.trim();
    if (!question || busy || !hasEvidence) return;
    setPrompt("");
    setError("");
    setBusy(true);
    const next = [...history, { id: uid(), role: "user" as const, text: question }];
    onSave(next);
    try {
      const reply = await askScorer({
        question: evaluation.question,
        answer: evaluation.answer,
        jurisdiction: session.jurisdiction,
        lawDate: session.lawDate,
        reviews: evaluation.reviews,
        history,
        prompt: question,
      });
      onSave([...next, { id: uid(), role: "assistant", text: reply }]);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Scorer chat is unavailable.");
    } finally {
      setBusy(false);
    }
  }
  return (
    <section className="cc-scorer-chat">
      <header>
        <MessageSquareMore size={17} />
        <div>
          <h3>Ask the assessment team</h3>
          <small>
            {previewMode
              ? "Placeholder replies · based on this answer and findings"
              : "Follow up on this answer and reviewer findings"}
          </small>
        </div>
      </header>
      {!hasEvidence ? (
        <p className="cc-muted">
          The scorers need an answer and at least one completed assessment before they can respond.
        </p>
      ) : (
        <>
          <div className="cc-scorer-history">
            {history.map((m) => (
              <article className={m.role === "user" ? "question" : "reply"} key={m.id}>
                <b>{m.role === "user" ? "You" : "Assessment team"}</b>
                <Markdown text={m.text} />
              </article>
            ))}
            {busy && (
              <p className="cc-muted">
                <LoaderCircle className="cc-spin" size={14} /> Reviewing the existing answer and
                findings…
              </p>
            )}
          </div>
          <form onSubmit={send}>
            <input
              aria-label="Ask the assessment team"
              placeholder="Ask why a reviewer flagged something…"
              value={prompt}
              onChange={(e) => setPrompt(e.target.value)}
            />
            <button
              className="cc-send"
              disabled={!prompt.trim() || busy}
              aria-label="Send scorer question"
            >
              {busy ? <LoaderCircle size={16} className="cc-spin" /> : <ArrowUp size={16} />}
            </button>
          </form>
          {error && (
            <p className="cc-alert" role="alert">
              {error}
              <button onClick={() => setError("")}>Dismiss</button>
            </p>
          )}
        </>
      )}
    </section>
  );
}
