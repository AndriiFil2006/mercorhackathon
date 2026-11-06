import { reviewers, type ReviewerId, type Review, type Session } from "./types";
// The backend owns model credentials, online research and authoritative citation checks.
const base = (import.meta.env["VITE_COUNSELCHECK_API_URL"] || "").replace(/\/$/, "");
export const previewMode = import.meta.env["VITE_COUNSELCHECK_PREVIEW"] === "true";
async function post(path: string, body: unknown, signal?: AbortSignal) {
  const response = await fetch(`${base}/api/legal/${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
    signal: signal ?? AbortSignal.timeout(60000),
  });
  if (!response.ok || !response.headers.get("content-type")?.includes("application/json"))
    throw new Error(
      "The legal service is unavailable. Connect the backend or enable preview mode for a UI walkthrough.",
    );
  return response.json();
}
export function parseReview(id: ReviewerId, data: unknown): Review {
  const d = data as Record<string, unknown> | null;
  if (
    !d ||
    typeof d["score"] !== "number" ||
    !Number.isFinite(d["score"]) ||
    d["score"] < 0 ||
    d["score"] > 100 ||
    typeof d["explanation"] !== "string" ||
    !d["explanation"].trim() ||
    typeof d["model"] !== "string" ||
    !d["model"].trim() ||
    !Array.isArray(d["findings"]) ||
    !d["findings"].every((f) => typeof f === "string") ||
    !Array.isArray(d["sources"])
  )
    throw new Error("Reviewer returned an invalid assessment. Retry this reviewer.");
  const sources = d["sources"].map((s: unknown) => {
    const source = s as { title: string; url: string };
    if (
      typeof source?.title !== "string" ||
      typeof source?.url !== "string" ||
      !/^https?:\/\//i.test(source.url)
    )
      throw new Error("Reviewer returned an invalid source link.");
    return source;
  });
  return {
    id,
    status: "complete",
    score: d["score"],
    explanation: d["explanation"],
    model: d["model"],
    findings: d["findings"] as string[],
    sources,
  };
}
export async function generateAnswer(
  session: Session,
  question: string,
  signal?: AbortSignal,
): Promise<string> {
  if (previewMode) {
    await new Promise((r) => setTimeout(r, 650));
    return "### Preview answer\nThis is an illustrative assistant response for checking the interface. A complete legal answer would apply the law of the selected jurisdiction as of the specified date, identify relevant authorities, discuss exceptions, and explain how those rules apply to your facts.\n\nThis preview contains no researched legal conclusions. Connect the legal backend to generate a substantive answer.";
  }
  const d = await post(
    "answer",
    {
      question,
      jurisdiction: session.jurisdiction,
      lawDate: session.lawDate,
      messages: session.messages,
    },
    signal,
  );
  if (typeof d.answer !== "string" || !d.answer.trim())
    throw new Error("The assistant returned an empty answer.");
  return d.answer;
}
export async function reviewAnswer(
  id: ReviewerId,
  request: { question: string; answer: string; jurisdiction: string; lawDate: string },
  signal?: AbortSignal,
): Promise<Review> {
  if (previewMode) {
    await new Promise((r) => setTimeout(r, 800 + reviewers.findIndex((r) => r.id === id) * 550));
    return {
      id,
      status: "complete",
      model: "Preview fixture",
      score: { authority: 58, jurisdiction: 72, reasoning: 64 }[id],
      explanation: "Illustrative assessment only. No model or online search was run.",
      findings: [
        id === "authority"
          ? "A live reviewer would verify that cited authorities exist and support the answer."
          : id === "jurisdiction"
            ? "A live reviewer would check the jurisdiction and effective date."
            : "A live reviewer would examine missing conditions, exceptions and the conclusion.",
      ],
      sources: [],
    };
  }
  return parseReview(id, await post("review", { reviewer: id, ...request }, signal));
}
