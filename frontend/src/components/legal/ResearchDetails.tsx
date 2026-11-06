import type { Review } from "@/lib/legal/types";
const names: Record<string, string> = {
  authority: "Authority",
  jurisdiction: "Jurisdiction & date",
  interpretation: "Interpretation",
  completeness: "Completeness",
  clarity: "Clarity",
};
export function ResearchDetails({ review }: { review: Review }) {
  const r = review.research;
  if (!r) return null;
  return (
    <details className="cc-research">
      <summary>Research, evidence and score breakdown</summary>
      <p>{r.research_summary}</p>
      <h4>How this score was calculated</h4>
      <p className="cc-muted">{review.formula}</p>
      <table>
        <thead>
          <tr>
            <th>Criterion</th>
            <th>Score</th>
            <th>Weight</th>
          </tr>
        </thead>
        <tbody>
          {Object.entries(r.criteria).map(([key, value]) => (
            <tr key={key}>
              <td>{names[key] ?? key}</td>
              <td>{value.score}/100</td>
              <td>{review.weights?.[key] ?? "—"}%</td>
            </tr>
          ))}
        </tbody>
      </table>
      {Object.entries(r.criteria).map(([key, value]) => (
        <section key={key}>
          <h4>{names[key]}</h4>
          <p>{value.reason}</p>
        </section>
      ))}
      {review.status === "abstained" && (
        <p className="cc-alert">No overall reviewer score: {r.abstention_reason}</p>
      )}
      <h4>Claims checked against the main AI answer</h4>
      {r.claim_checks.map((c, i) => (
        <article key={i}>
          <blockquote>{c.claim}</blockquote>
          <strong>{c.verdict}</strong>
          <p>{c.explanation}</p>
          {c.evidence.map((e, j) => (
            <blockquote key={j}>
              <span>{e.source_id}</span> “{e.quote}”
            </blockquote>
          ))}
        </article>
      ))}
      <h4>Jurisdiction</h4>
      <p>{r.jurisdiction_analysis}</p>
      <h4>Relevant law date</h4>
      <p>{r.date_analysis}</p>
      <h4>Suggested correction / further research</h4>
      <p>{r.suggested_correction}</p>
      <h4>Research limitations</h4>
      <ul>
        {[...r.limitations, ...(review.researchWarnings ?? [])].map((v, i) => (
          <li key={i}>{v}</li>
        ))}
      </ul>
      <h4>Searches performed</h4>
      {review.queries?.length ? (
        <ul>
          {review.queries.map((q, i) => (
            <li key={i}>{q}</li>
          ))}
        </ul>
      ) : (
        <p>No live searches in this assessment.</p>
      )}
      <h4>Retrieved source record</h4>
      {review.sources?.map((s, i) => (
        <details key={i}>
          <summary>
            {s.id ?? i + 1} · {s.title}
          </summary>
          <a href={s.url} target="_blank" rel="noreferrer">
            Open source
          </a>
          <p>
            {s.evidence_type ?? "Source link"} · Retrieved {s.retrieved_at ?? "Unknown"}
            {s.truncated ? " · excerpt capped for model context" : ""}
          </p>
          {s.published_date && (
            <p>Reported publication date: {s.published_date} (not proof of legal effective date)</p>
          )}
          <pre>{s.text ?? "Source text not stored in this older assessment."}</pre>
        </details>
      ))}
      <small className="cc-muted">
        {review.cached ? "Cached audit · source timestamps preserved" : "New audit"}. Evidence
        checks establish provenance, not legal correctness.
      </small>
    </details>
  );
}
export function AssessmentSummary({ reviews }: { reviews: Review[] }) {
  const finished = reviews.filter((r) => r.status === "complete" && typeof r.score === "number");
  if (finished.length !== 3)
    return (
      <p className="cc-fineprint">
        Overall score remains pending until all three reviewers finish without error or abstention.
        Review individual research gaps below.
      </p>
    );
  const numbers = finished.map((r) => r.score!);
  const spread = Math.max(...numbers) - Math.min(...numbers);
  return (
    <div className="cc-aggregate-explanation">
      <details>
        <summary>Compare the reviewers' conclusions</summary>
        {finished.map((review) => (
          <section key={review.id}>
            <strong>
              {review.model ?? review.id} · {review.score}/100
            </strong>
            <p>{review.explanation}</p>
          </section>
        ))}
      </details>
      <p>
        The overall score is the rounded average of {numbers.join(", ")}. Reviewers{" "}
        {spread >= 20
          ? `differ by ${spread} points; inspect the conflicting claim findings before relying on the answer.`
          : `are within ${spread} points of each other; shared model or source errors can still occur.`}
      </p>
      <p>
        The 80 boundary controls the recommendation to seek a real lawyer. It is not a probability
        or expert certification.
      </p>
    </div>
  );
}
