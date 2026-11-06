export type Message = { id: string; role: "user" | "assistant"; text: string };
export const reviewers = [
  { id: "authority", name: "Authority reviewer", focus: "Citations & supporting law" },
  { id: "jurisdiction", name: "Jurisdiction reviewer", focus: "Location & date of law" },
  { id: "reasoning", name: "Reasoning reviewer", focus: "Application & completeness" },
] as const;
export type ReviewerId = (typeof reviewers)[number]["id"];
export type Review = {
  id: ReviewerId;
  status: "queued" | "searching" | "complete" | "abstained" | "error";
  model?: string;
  score?: number;
  explanation?: string;
  findings?: string[];
  sources?: (Partial<ResearchSource> & { title: string; url: string })[];
  error?: string | undefined;
  reportId?: string;
  generationId?: string | null;
  mode?: "live" | "mock" | "preview";
  research?: ResearchReport;
  queries?: string[];
  weights?: Record<string, number>;
  formula?: string;
  researchWarnings?: string[];
  cached?: boolean;
};
export type ResearchSource = {
  id: string;
  title: string;
  url: string;
  text: string;
  retrieved_at: string;
  evidence_type: "extracted_page" | "search_excerpt" | "mock";
  truncated: boolean;
  published_date?: string | null;
};
export type ResearchReport = {
  criteria: Record<
    "authority" | "jurisdiction" | "interpretation" | "completeness" | "clarity",
    { score: number; reason: string }
  >;
  research_summary: string;
  jurisdiction_analysis: string;
  date_analysis: string;
  claim_checks: {
    claim: string;
    verdict: string;
    explanation: string;
    evidence: { source_id: string; quote: string }[];
  }[];
  limitations: string[];
  suggested_correction: string;
  conclusion: string;
  abstain: boolean;
  abstention_reason: string;
};
export const categories = [
  "Hallucinated law",
  "Outdated law",
  "Wrong jurisdiction",
  "Misinterpretation",
  "Missing precedent",
  "Incomplete answer",
  "Incorrect conclusion",
];
export type Feedback = {
  verdict: string;
  categories: string[];
  explanation: string;
  correction: string;
  authority: string;
  confidence: string;
  reviewer: string;
  submittedAt?: string;
};
export type Evaluation = {
  id: string;
  question: string;
  answer: string;
  reviews: Review[];
  mode: "live" | "mock" | "preview";
  generationId?: string;
  answerModel?: string;
  createdAt: string;
  feedback?: Feedback;
  scorerMessages?: Message[];
};
export type Session = {
  id: string;
  title: string;
  jurisdiction: string;
  lawDate: string;
  messages: Message[];
  evaluations: Evaluation[];
  externalConsent?: boolean;
  busy?: boolean;
  error?: string | undefined;
};
export type Chat = {
  id: string;
  sessionId?: string;
  evaluationId?: string;
  lawyer: string;
  status: "active" | "closed";
  messages: Message[];
  createdAt: string;
  preview?: boolean;
  handoffToken?: string;
  handoffId?: string;
  consentedAt?: string;
  contextShared?: boolean;
  busy?: boolean;
  error?: string | undefined;
  backendMode?: string;
};
export type Store = { sessions: Session[]; activeId: string; chats: Chat[]; collapsed: boolean };
export function overall(reviews: Review[]): number | null {
  if (
    reviews.length !== 3 ||
    !reviewers.every((r) => reviews.some((v) => v.id === r.id)) ||
    reviews.some(
      (r) =>
        r.status !== "complete" ||
        typeof r.score !== "number" ||
        !Number.isFinite(r.score) ||
        r.score < 0 ||
        r.score > 100,
    )
  )
    return null;
  return Math.round(reviews.reduce((n, r) => n + r.score!, 0) / 3);
}
export const uid = () => crypto.randomUUID();
export function newSession(): Session {
  return {
    id: uid(),
    title: "New inquiry",
    jurisdiction: "",
    lawDate: new Date().toISOString().slice(0, 10),
    messages: [],
    evaluations: [],
  };
}
