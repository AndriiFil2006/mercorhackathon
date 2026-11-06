import { act, renderHook, waitFor, cleanup } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { askChecker, generateReport, reviewReport } from "./api";
import { useTransferSession } from "./useSession";
import { createWorkspace, parseWorkspace, SESSION_STORAGE_KEY } from "./sessionStorage";
import type { GenerateReportResult } from "./api";

vi.mock("./api", () => ({
  generateReport: vi.fn(),
  reviewReport: vi.fn(),
  askChecker: vi.fn(),
}));

beforeEach(() => {
  localStorage.clear();
  vi.resetAllMocks();
  vi.mocked(generateReport).mockResolvedValue({
    content: "Saved assistant response",
    isReport: false,
  });
  vi.mocked(askChecker).mockResolvedValue("Saved checker response");
  vi.mocked(reviewReport).mockImplementation(async ({ report }) => ({
    reportId: report.id,
    status: "needs-info",
    summary: "More context needed",
    findings: [],
    checks: [],
    requirementsVersion: report.requirementsVersion,
  }));
});
afterEach(cleanup);

describe("Saved conversation sessions", () => {
  it("keeps the main conversation, checker conversation and report together after reloading", async () => {
    const first = renderHook(() => useTransferSession());
    await waitFor(() => expect(first.result.current.hydrated).toBe(true));
    const originalId = first.result.current.activeSessionId;
    act(() => first.result.current.sendMain("Copy the EFS inputs to S3"));
    await waitFor(() => expect(first.result.current.mainBusy).toBe(false));
    act(() => first.result.current.pasteReport("# Proposed routes\nEFS to S3"));
    await waitFor(() => expect(first.result.current.checkerFeed).toHaveLength(1));
    await act(() => first.result.current.sendChecker("Which route is this?"));
    expect(first.result.current.checkerFeed).toHaveLength(3);
    first.unmount();

    const restored = renderHook(() => useTransferSession());
    await waitFor(() => expect(restored.result.current.hydrated).toBe(true));
    expect(restored.result.current.activeSessionId).toBe(originalId);
    expect(restored.result.current.mainMessages[0]?.content).toBe("Copy the EFS inputs to S3");
    expect(restored.result.current.reports[0]?.text).toBe("# Proposed routes\nEFS to S3");
    expect(restored.result.current.checkerFeed).toHaveLength(3);
    expect(restored.result.current.title).toBe("Copy the EFS inputs to S3");
  });

  it("lets a background answer finish in its own session while another session is open", async () => {
    let finish!: (value: GenerateReportResult) => void;
    vi.mocked(generateReport).mockImplementationOnce(
      () =>
        new Promise((resolve) => {
          finish = resolve;
        }),
    );
    const { result } = renderHook(() => useTransferSession());
    await waitFor(() => expect(result.current.hydrated).toBe(true));
    const firstId = result.current.activeSessionId;
    act(() => result.current.sendMain("First request"));
    expect(result.current.mainBusy).toBe(true);
    act(() => {
      result.current.newSession();
    });
    const secondId = result.current.activeSessionId;
    expect(result.current.mainMessages).toHaveLength(0);
    await act(async () => {
      finish({ content: "Only for the first session", isReport: true });
    });
    expect(result.current.activeSessionId).toBe(secondId);
    expect(result.current.mainMessages).toHaveLength(0);
    expect(result.current.reports).toHaveLength(0);
    act(() => result.current.selectSession(firstId));
    expect(result.current.mainMessages.at(-1)?.content).toBe("Only for the first session");
    expect(result.current.reports).toHaveLength(1);
  });

  it("renames, switches and deletes sessions without clearing another conversation", async () => {
    const { result } = renderHook(() => useTransferSession());
    await waitFor(() => expect(result.current.hydrated).toBe(true));
    const firstId = result.current.activeSessionId;
    act(() => result.current.sendMain("Keep these messages"));
    await waitFor(() => expect(result.current.mainBusy).toBe(false));
    act(() => result.current.renameSession(firstId, "My dataset"));
    act(() => {
      result.current.newSession();
    });
    const secondId = result.current.activeSessionId;
    act(() => result.current.selectSession(firstId));
    expect(result.current.title).toBe("My dataset");
    expect(result.current.mainMessages).toHaveLength(2);
    act(() => result.current.deleteSession(secondId));
    expect(result.current.mainMessages).toHaveLength(2);
    act(() => result.current.deleteSession(firstId));
    expect(result.current.sessions).toHaveLength(1);
    expect(result.current.title).toBe("New session");
    expect(result.current.mainMessages).toHaveLength(0);
  });

  it("persists the collapsed sidebar preference", async () => {
    const first = renderHook(() => useTransferSession());
    await waitFor(() => expect(first.result.current.hydrated).toBe(true));
    act(() => first.result.current.setSidebarCollapsed(true));
    first.unmount();
    const next = renderHook(() => useTransferSession());
    await waitFor(() => expect(next.result.current.hydrated).toBe(true));
    expect(next.result.current.sidebarCollapsed).toBe(true);
    expect(JSON.parse(localStorage.getItem(SESSION_STORAGE_KEY)!).sidebarCollapsed).toBe(true);
  });
});

describe("History recovery", () => {
  it("recovers interrupted requests without restoring permanent loading states", () => {
    const workspace = createWorkspace();
    const s = workspace.sessions[0]!;
    s.mainBusy = true;
    s.mainMessages = [
      { id: "m", role: "assistant", content: "Partial text", streaming: true, at: 1 },
    ];
    s.reports = [
      { id: "r", messageId: "m", text: "A report", index: 1, requirementsVersion: 0, at: 1 },
    ];
    s.reviews = { r: { status: "reviewing", reportId: "r" } };
    const recovered = parseWorkspace(JSON.stringify(workspace))!.sessions[0]!;
    expect(recovered.mainBusy).toBe(false);
    expect(recovered.mainMessages[0]?.streaming).toBe(false);
    expect(recovered.mainMessages[0]?.content).toContain("interrupted");
    expect(recovered.reviews["r"]?.status).toBe("failed");
  });

  it("rejects malformed history and restores a valid active session when its pointer is stale", () => {
    expect(parseWorkspace("{broken")).toBeNull();
    expect(parseWorkspace(JSON.stringify({ schemaVersion: 1, sessions: [{}] }))).toBeNull();
    const workspace = createWorkspace();
    workspace.activeSessionId = "no-longer-present";
    expect(parseWorkspace(JSON.stringify(workspace))!.activeSessionId).toBe(
      workspace.sessions[0]!.id,
    );
  });
});
