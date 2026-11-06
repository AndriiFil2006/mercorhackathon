// Replaceable async boundaries. Swap these bodies for real server functions later.
// No AI backend is connected yet: outside the labeled demo scenarios, these return
// honest "not connected" responses rather than canned verdicts.
import { SCENARIOS } from "./scenarios";
import type {
  CheckerMessage,
  MainMessage,
  Report,
  Review,
  ScenarioId,
  TransferContext,
} from "./types";

const sleep = (ms: number, signal?: AbortSignal) =>
  new Promise<void>((res, rej) => {
    const t = setTimeout(res, ms);
    signal?.addEventListener("abort", () => {
      clearTimeout(t);
      rej(new DOMException("aborted", "AbortError"));
    });
  });

export interface GenerateReportInput {
  messages: MainMessage[];
  context: TransferContext;
  scenarioId: ScenarioId | null;
  /** True when this is the scenario's opening request (demo report allowed). */
  isScenarioOpening: boolean;
  onToken: (chunk: string) => void;
  signal?: AbortSignal;
}
export interface GenerateReportResult {
  content: string;
  /** Whether the response is a transfer report (greetings/clarifications are not). */
  isReport: boolean;
}

export async function generateReport(input: GenerateReportInput): Promise<GenerateReportResult> {
  const demo =
    input.scenarioId && input.isScenarioOpening ? SCENARIOS[input.scenarioId].report : null;
  const content =
    demo ??
    "The Transfer Assistant is not connected yet. Your request has been saved in this session.";
  const tokens = content.match(/\S+\s*/g) ?? [content];
  for (let i = 0; i < tokens.length; i += 4) {
    await sleep(18, input.signal);
    input.onToken(tokens.slice(i, i + 4).join(""));
  }
  return { content, isReport: demo !== null };
}

export interface ReviewReportInput {
  report: Report;
  requirements: TransferContext;
  scenarioId: ScenarioId | null;
  signal?: AbortSignal;
}

export async function reviewReport(input: ReviewReportInput): Promise<Omit<Review, "at">> {
  await sleep(1400, input.signal);
  const s = input.scenarioId ? SCENARIOS[input.scenarioId] : null;
  // Canned demo review applies only if the report is byte-identical to the demo report
  // and requirements haven't been changed by the user.
  if (s && s.report === input.report.text && input.requirements.changes.length === 0) {
    return {
      reportId: input.report.id,
      requirementsVersion: input.report.requirementsVersion,
      demo: true,
      ...s.review,
    };
  }
  return {
    reportId: input.report.id,
    requirementsVersion: input.report.requirementsVersion,
    status: "failed",
    summary: "The Plan Checker is not connected yet. Your report has been saved for review.",
    findings: [],
    checks: [],
  };
}

export interface AskCheckerInput {
  question: string;
  report: Report | null;
  review: Review | null;
  history: CheckerMessage[];
  context: TransferContext;
  signal?: AbortSignal;
}

/** Checker chat. Never forwarded to the Transfer Assistant and never triggers a new review. */
export async function askChecker(input: AskCheckerInput): Promise<string> {
  await sleep(600, input.signal);
  if (!input.report) {
    return "I need a report before I can assess one. Generate a plan with the Transfer Assistant, or use **Paste report** to add one here.";
  }
  if (input.review?.demo) {
    return `This is a labeled demo review of Report ${"#"}${input.report.id.slice(-4)}. The checker model isn't connected yet, so I can't answer free-form questions — open each finding above to see the quoted text, what was requested, and what the report proposes.`;
  }
  return "The Plan Checker isn't connected to a model yet, so I can't answer questions about this report.";
}
