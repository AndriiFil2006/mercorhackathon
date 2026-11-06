// Shared types. Main chat, checker chat, reports, context and reviews are kept separate.

export type ScenarioId = "correct" | "wrong-route" | "insufficient";

export interface TransferContext {
  request: string;
  changes: { id: string; text: string; at: number }[];
  endpoints: { label: string; kind: string; value: string }[];
  inventories: { label: string; files: string[] }[];
}

export interface MainMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  /** Set only when this message is a transfer report (not greetings/clarifications). */
  reportId?: string;
  streaming?: boolean;
  pasted?: boolean;
  at: number;
}

export interface Report {
  id: string;
  messageId: string;
  text: string;
  index: number;
  requirementsVersion: number;
  at: number;
}

export type ReviewStatus =
  | "waiting"
  | "reviewing"
  | "issues"
  | "clean"
  | "needs-info"
  | "failed";

export type FindingKind = "contradiction" | "missing-evidence";

export interface Finding {
  id: string;
  severity: "high" | "medium";
  kind: FindingKind;
  title: string;
  /** Exact text that appears in the report (rendered). */
  quote: string;
  explanation: string;
  requested: string;
  proposed: string;
  reference: string;
}

export interface Review {
  reportId: string;
  status: Exclude<ReviewStatus, "waiting">;
  summary: string;
  findings: Finding[];
  checks: string[];
  requirementsVersion: number;
  superseded?: boolean;
  demo?: boolean;
  at: number;
}

export interface CheckerMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  at: number;
}

export type CheckerFeedItem =
  | { kind: "review"; reportId: string; at: number }
  | { kind: "chat"; message: CheckerMessage };
