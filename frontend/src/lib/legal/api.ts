import { reviewers, type ReviewerId, type Review, type Session } from "./types";
// All model/search secrets stay in backend/.env. VITE_* variables are public.
const base = (import.meta.env["VITE_COUNSELCHECK_API_URL"] || "http://127.0.0.1:8000").replace(
  /\/$/,
  "",
);
export const previewMode = import.meta.env["VITE_COUNSELCHECK_PREVIEW"] === "true";
export async function post(path: string, body: unknown, signal?: AbortSignal) {
  let response: Response;
  try {
    response = await fetch(`${base}/api/legal/${path}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
      signal: signal ?? AbortSignal.timeout(600000),
    });
  } catch (error) {
    throw new Error(
      error instanceof Error && ["TimeoutError", "AbortError"].includes(error.name)
        ? "The backend request timed out. Check the backend terminal before retrying."
        : "Cannot reach the backend. Start it on port 8000 and check VITE_COUNSELCHECK_API_URL.",
    );
  }
  if (!response.headers.get("content-type")?.includes("application/json"))
    throw new Error(
      "The backend returned a non-JSON response. Check the API URL and backend terminal.",
    );
  const data = await response.json();
  if (!response.ok) {
    const detail = data.detail;
    throw new Error(
      typeof detail === "string"
        ? detail
        : detail?.message ||
            (Array.isArray(detail)
              ? `Request validation failed: ${detail.map((v: { loc?: unknown[]; msg?: string }) => `${v.loc?.join(".")}: ${v.msg}`).join("; ")}`
              : "The backend could not complete this request."),
    );
  }
  return data;
}
export function parseReview(id: ReviewerId, data: unknown): Review {
  const d = data as Record<string, unknown> | null;
  const abstained = d?.["status"] === "abstained";
  if (
    !d ||
    (!abstained &&
      (typeof d["score"] !== "number" ||
        !Number.isFinite(d["score"]) ||
        d["score"] < 0 ||
        d["score"] > 100)) ||
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
      throw new Error("Invalid reviewer source URL.");
    return source;
  });
  const result = {
    ...d,
    id,
    status: abstained ? "abstained" : "complete",
    sources,
  } as unknown as Review;
  if (abstained) delete result.score;
  return result;
}
export type GeneratedAnswer = {
  answer: string;
  generationId?: string;
  model?: string;
  mode: "live" | "mock" | "preview";
};
export async function generateAnswer(
  session: Session,
  question: string,
  signal?: AbortSignal,
): Promise<GeneratedAnswer> {
  if (previewMode)
    return {
      answer:
        "### Preview answer\nIllustrative response only. No real model, legal research or citation verification was used.",
      mode: "preview",
      model: "Browser preview",
    };
  const data = await post(
    "answer",
    {
      question,
      jurisdiction: session.jurisdiction,
      lawDate: session.lawDate,
      messages: session.messages,
      externalConsent: session.externalConsent === true,
    },
    signal,
  );
  if (typeof data.answer !== "string" || !data.answer.trim())
    throw new Error("The assistant returned an empty answer.");
  return data;
}
export async function reviewAnswer(
  id: ReviewerId,
  request: {
    question: string;
    answer: string;
    jurisdiction: string;
    lawDate: string;
    generationId?: string;
    externalConsent?: boolean;
    force?: boolean;
  },
  signal?: AbortSignal,
): Promise<Review> {
  if (previewMode)
    return {
      id,
      status: "complete",
      model: "Browser preview fixture",
      mode: "preview",
      score: { authority: 58, jurisdiction: 72, reasoning: 64 }[id],
      explanation: "Illustrative score only; no research was performed.",
      findings: ["Browser-only preview"],
      sources: [],
    };
  return parseReview(id, await post("review", { reviewer: id, ...request }, signal));
}
export async function askScorer(input: {
  question: string;
  answer: string;
  jurisdiction: string;
  lawDate: string;
  reviews: Review[];
  history: { role: string; text: string }[];
  prompt: string;
  externalConsent: boolean;
}): Promise<string> {
  if (!input.answer.trim()) throw new Error("Generate or paste an answer first.");
  if (previewMode) return "Preview assessment conversation — no model or new research was used.";
  const result = await post("review-chat", input);
  if (typeof result.answer !== "string" || !result.answer.trim())
    throw new Error("The assessment team returned no response.");
  return result.answer;
}
export async function createHandoff(
  session: Session | undefined,
  evaluationId: string,
  consentProcessing: boolean,
  consentShareContext: boolean,
) {
  return post("handoff", {
    consentProcessing,
    consentShareContext,
    context: session
      ? {
          id: session.id,
          title: session.title,
          jurisdiction: session.jurisdiction,
          lawDate: session.lawDate,
          messages: session.messages,
          evaluations: session.evaluations,
          selectedEvaluationId: evaluationId,
        }
      : null,
  });
}
export async function askLegalAssistant(handoffToken: string, message: string) {
  return post("lawyer-chat", { handoffToken, message });
}
export async function endHandoff(handoffToken: string, revoke = false) {
  return post(revoke ? "handoff/revoke" : "handoff/close", { handoffToken });
}
