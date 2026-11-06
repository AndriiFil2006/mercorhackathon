import { z } from "zod";
import type {
  CheckerFeedItem,
  MainMessage,
  Report,
  Review,
  ScenarioId,
  TransferContext,
} from "./types";

export const SESSION_STORAGE_KEY = "transfer-workspace:v1";
export const newId = (prefix: string) =>
  prefix + "_" + Date.now().toString(36) + Math.random().toString(36).slice(2, 9);

export interface SavedTransferSession {
  id: string;
  title: string;
  createdAt: number;
  updatedAt: number;
  scenarioId: ScenarioId | null;
  context: TransferContext;
  requirementsVersion: number;
  mainMessages: MainMessage[];
  reports: Report[];
  reviews: Record<string, Review | { status: "reviewing"; reportId: string }>;
  checkerFeed: CheckerFeedItem[];
  mainBusy: boolean;
  checkerBusy: boolean;
}

export interface SavedWorkspace {
  schemaVersion: 1;
  activeSessionId: string;
  sidebarCollapsed: boolean;
  sessions: SavedTransferSession[];
}

const at = z.number().finite();
const message = z.object({
  id: z.string(),
  role: z.enum(["user", "assistant"]),
  content: z.string(),
  at,
});
const report = z.object({
  id: z.string(),
  messageId: z.string(),
  text: z.string(),
  index: z.number(),
  requirementsVersion: z.number(),
  at,
});
const review = z.object({
  reportId: z.string(),
  status: z.enum(["reviewing", "issues", "clean", "needs-info", "failed"]),
  summary: z.string(),
  requirementsVersion: z.number(),
  at,
  demo: z.boolean().optional(),
  superseded: z.boolean().optional(),
  findings: z.array(
    z.object({
      id: z.string(),
      severity: z.enum(["high", "medium"]),
      kind: z.enum(["contradiction", "missing-evidence"]),
      title: z.string(),
      quote: z.string(),
      explanation: z.string(),
      requested: z.string(),
      proposed: z.string(),
      reference: z.string(),
    }),
  ),
  checks: z.array(z.string()),
});
const workspaceSchema = z.object({
  schemaVersion: z.literal(1),
  activeSessionId: z.string(),
  sidebarCollapsed: z.boolean(),
  sessions: z
    .array(
      z.object({
        id: z.string(),
        title: z.string(),
        createdAt: at,
        updatedAt: at,
        scenarioId: z.enum(["correct", "wrong-route", "insufficient"]).nullable(),
        context: z.object({
          request: z.string(),
          changes: z.array(z.object({ id: z.string(), text: z.string(), at })),
          endpoints: z.array(z.object({ label: z.string(), kind: z.string(), value: z.string() })),
          inventories: z.array(z.object({ label: z.string(), files: z.array(z.string()) })),
        }),
        requirementsVersion: z.number(),
        mainMessages: z.array(
          message.extend({
            reportId: z.string().optional(),
            streaming: z.boolean().optional(),
            pasted: z.boolean().optional(),
          }),
        ),
        reports: z.array(report),
        reviews: z.record(
          z.union([review, z.object({ status: z.literal("reviewing"), reportId: z.string() })]),
        ),
        checkerFeed: z.array(
          z.union([
            z.object({ kind: z.literal("review"), reportId: z.string(), at }),
            z.object({ kind: z.literal("chat"), message }),
          ]),
        ),
        mainBusy: z.boolean(),
        checkerBusy: z.boolean(),
      }),
    )
    .min(1),
});

export function createSession(id = newId("session"), now = Date.now()): SavedTransferSession {
  return {
    id,
    title: "New session",
    createdAt: now,
    updatedAt: now,
    scenarioId: null,
    context: { request: "", changes: [], endpoints: [], inventories: [] },
    requirementsVersion: 0,
    mainMessages: [],
    reports: [],
    reviews: {},
    checkerFeed: [],
    mainBusy: false,
    checkerBusy: false,
  };
}

export function createWorkspace(initial = false): SavedWorkspace {
  const session = initial ? createSession("initial", 0) : createSession();
  return {
    schemaVersion: 1,
    activeSessionId: session.id,
    sidebarCollapsed: false,
    sessions: [session],
  };
}

export function parseWorkspace(raw: string | null): SavedWorkspace | null {
  if (!raw) return null;
  let value: unknown;
  try {
    value = JSON.parse(raw);
  } catch {
    return null;
  }
  const result = workspaceSchema.safeParse(value);
  if (!result.success) return null;
  const workspace = result.data as SavedWorkspace;
  // Reloads cannot resume a network request. Keep its text and allow a fresh attempt.
  workspace.sessions = workspace.sessions.map((session) => ({
    ...session,
    mainBusy: false,
    checkerBusy: false,
    mainMessages: session.mainMessages.map((m) =>
      m.streaming
        ? {
            ...m,
            streaming: false,
            content:
              (m.content ? m.content + "\n\n" : "") +
              "Response interrupted. Send your message again to continue.",
          }
        : m,
    ),
    reviews: Object.fromEntries(
      Object.entries(session.reviews).map(([id, rv]) => [
        id,
        rv.status === "reviewing"
          ? {
              reportId: id,
              status: "failed",
              summary: "This review was interrupted. Retry it to continue.",
              requirementsVersion:
                session.reports.find((r) => r.id === id)?.requirementsVersion ??
                session.requirementsVersion,
              findings: [],
              checks: [],
              at: Date.now(),
            }
          : rv,
      ]),
    ),
  }));
  if (!workspace.sessions.some((s) => s.id === workspace.activeSessionId)) {
    workspace.activeSessionId = workspace.sessions[0]!.id;
  }
  return workspace;
}

export function titleFromRequest(text: string) {
  const title = text.replace(/\s+/g, " ").trim();
  return title.length > 48 ? title.slice(0, 48).trimEnd() + "…" : title || "New session";
}
