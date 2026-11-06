export type Message = { id: string; role: "user" | "assistant"; text: string };
export const reviewers = [
  { id: "authority", name: "Authority reviewer", focus: "Citations & supporting law" },
  { id: "jurisdiction", name: "Jurisdiction reviewer", focus: "Location & date of law" },
  { id: "reasoning", name: "Reasoning reviewer", focus: "Application & completeness" },
] as const;
export type ReviewerId = (typeof reviewers)[number]["id"];
export type Review = {
  id: ReviewerId;
  status: "queued" | "searching" | "complete" | "error";
  model?: string;
  score?: number;
  explanation?: string;
  findings?: string[];
  sources?: { title: string; url: string }[];
  error?: string | undefined;
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
  mode: "live" | "preview";
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
  preview: true;
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
