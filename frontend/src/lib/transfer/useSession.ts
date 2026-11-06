import { useCallback, useEffect, useRef, useState } from "react";
import { askChecker, generateReport, reviewReport } from "./api";
import { SCENARIOS } from "./scenarios";
import {
  createSession,
  createWorkspace,
  newId,
  parseWorkspace,
  SESSION_STORAGE_KEY,
  titleFromRequest,
} from "./sessionStorage";
import type { SavedTransferSession, SavedWorkspace } from "./sessionStorage";
import type { MainMessage, Report, Review, ScenarioId, TransferContext } from "./types";

export function useTransferSession() {
  const [workspace, setWorkspace] = useState<SavedWorkspace>(() => createWorkspace(true));
  const [hydrated, setHydrated] = useState(false);
  const [storageError, setStorageError] = useState<string | null>(null);
  const stateRef = useRef(workspace);
  const mounted = useRef(true);
  const requests = useRef(new Map<string, Set<AbortController>>());

  const commit = useCallback((fn: (state: SavedWorkspace) => SavedWorkspace) => {
    if (!mounted.current) return;
    const next = fn(stateRef.current);
    stateRef.current = next;
    setWorkspace(next);
  }, []);

  const updateSession = useCallback(
    (id: string, fn: (session: SavedTransferSession) => SavedTransferSession) => {
      commit((state) => ({
        ...state,
        sessions: state.sessions.map((session) => (session.id === id ? fn(session) : session)),
      }));
    },
    [commit],
  );

  const persist = useCallback(() => {
    try {
      window.localStorage.setItem(SESSION_STORAGE_KEY, JSON.stringify(stateRef.current));
      setStorageError(null);
    } catch {
      setStorageError("Session history could not be saved on this device.");
    }
  }, []);

  useEffect(() => {
    mounted.current = true;
    const activeRequests = requests.current;
    try {
      commit(
        () => parseWorkspace(window.localStorage.getItem(SESSION_STORAGE_KEY)) ?? createWorkspace(),
      );
    } catch {
      commit(() => createWorkspace());
      setStorageError("Session history is unavailable in this browser.");
    }
    setHydrated(true);
    return () => {
      mounted.current = false;
      activeRequests.forEach((controllers) =>
        controllers.forEach((controller) => controller.abort()),
      );
    };
  }, [commit]);

  useEffect(() => {
    if (!hydrated) return;
    const timer = window.setTimeout(persist, 150);
    return () => window.clearTimeout(timer);
  }, [workspace, hydrated, persist]);

  useEffect(() => {
    if (!hydrated) return;
    window.addEventListener("pagehide", persist);
    window.addEventListener("beforeunload", persist);
    return () => {
      window.removeEventListener("pagehide", persist);
      window.removeEventListener("beforeunload", persist);
      try {
        window.localStorage.setItem(SESSION_STORAGE_KEY, JSON.stringify(stateRef.current));
      } catch {
        /* Storage error is already reported in the workspace. */
      }
    };
  }, [hydrated, persist]);

  const request = useCallback((sessionId: string) => {
    const controller = new AbortController();
    const controllers = requests.current.get(sessionId) ?? new Set<AbortController>();
    controllers.add(controller);
    requests.current.set(sessionId, controllers);
    return {
      signal: controller.signal,
      finish: () => {
        controllers.delete(controller);
        if (!controllers.size) requests.current.delete(sessionId);
      },
    };
  }, []);

  const startReview = useCallback(
    async (
      sessionId: string,
      report: Report,
      context: TransferContext,
      scenarioId: ScenarioId | null,
    ) => {
      const pending = request(sessionId);
      updateSession(sessionId, (s) => ({
        ...s,
        reviews: { ...s.reviews, [report.id]: { status: "reviewing", reportId: report.id } },
        checkerFeed: s.checkerFeed.some(
          (item) => item.kind === "review" && item.reportId === report.id,
        )
          ? s.checkerFeed
          : [...s.checkerFeed, { kind: "review", reportId: report.id, at: Date.now() }],
      }));
      let result: Omit<Review, "at">;
      try {
        result = await reviewReport({
          report,
          requirements: context,
          scenarioId,
          signal: pending.signal,
        });
      } catch (error) {
        if (pending.signal.aborted) {
          pending.finish();
          return;
        }
        result = {
          reportId: report.id,
          status: "failed",
          summary: "Review failed: " + (error as Error).message,
          findings: [],
          checks: [],
          requirementsVersion: report.requirementsVersion,
        };
      }
      pending.finish();
      updateSession(sessionId, (s) => ({
        ...s,
        updatedAt: Date.now(),
        reviews: {
          ...s.reviews,
          [report.id]:
            s.reports.at(-1)?.id !== report.id
              ? {
                  ...result,
                  status: "failed",
                  findings: [],
                  superseded: true,
                  summary: "A newer report arrived before this review finished.",
                  at: Date.now(),
                }
              : { ...result, at: Date.now() },
        },
      }));
    },
    [request, updateSession],
  );

  const addReport = useCallback(
    (
      sessionId: string,
      messageId: string,
      text: string,
      context: TransferContext,
      version: number,
      scenarioId: ScenarioId | null,
    ) => {
      const session = stateRef.current.sessions.find((s) => s.id === sessionId);
      const report: Report = {
        id: newId("rpt"),
        messageId,
        text,
        index: (session?.reports.length ?? 0) + 1,
        requirementsVersion: version,
        at: Date.now(),
      };
      updateSession(sessionId, (s) => ({ ...s, reports: [...s.reports, report] }));
      void startReview(sessionId, report, context, scenarioId);
      return report;
    },
    [startReview, updateSession],
  );

  const runMain = useCallback(
    async (
      sessionId: string,
      history: MainMessage[],
      context: TransferContext,
      version: number,
      scenarioId: ScenarioId | null,
      opening: boolean,
    ) => {
      const pending = request(sessionId);
      const messageId = newId("msg");
      updateSession(sessionId, (s) => ({
        ...s,
        mainBusy: true,
        mainMessages: [
          ...s.mainMessages,
          { id: messageId, role: "assistant", content: "", streaming: true, at: Date.now() },
        ],
      }));
      try {
        const response = await generateReport({
          messages: history,
          context,
          scenarioId,
          isScenarioOpening: opening,
          signal: pending.signal,
          onToken: (chunk) => {
            if (pending.signal.aborted) return;
            updateSession(sessionId, (s) => ({
              ...s,
              mainMessages: s.mainMessages.map((m) =>
                m.id === messageId ? { ...m, content: m.content + chunk } : m,
              ),
            }));
          },
        });
        if (pending.signal.aborted) return;
        const report = response.isReport
          ? addReport(sessionId, messageId, response.content, context, version, scenarioId)
          : null;
        updateSession(sessionId, (s) => ({
          ...s,
          updatedAt: Date.now(),
          mainMessages: s.mainMessages.map((m) =>
            m.id === messageId
              ? {
                  ...m,
                  content: response.content,
                  streaming: false,
                  ...(report ? { reportId: report.id } : {}),
                }
              : m,
          ),
        }));
      } catch (error) {
        if (!pending.signal.aborted)
          updateSession(sessionId, (s) => ({
            ...s,
            mainMessages: s.mainMessages.map((m) =>
              m.id === messageId
                ? {
                    ...m,
                    content: "Unable to respond: " + (error as Error).message,
                    streaming: false,
                  }
                : m,
            ),
          }));
      } finally {
        pending.finish();
        updateSession(sessionId, (s) => ({ ...s, mainBusy: false }));
      }
    },
    [addReport, request, updateSession],
  );

  const newSession = useCallback(() => {
    const session = createSession();
    commit((state) => ({
      ...state,
      activeSessionId: session.id,
      sessions: [session, ...state.sessions],
    }));
    return session.id;
  }, [commit]);

  const selectSession = useCallback(
    (id: string) => {
      commit((state) =>
        state.sessions.some((s) => s.id === id) ? { ...state, activeSessionId: id } : state,
      );
    },
    [commit],
  );

  const renameSession = useCallback(
    (id: string, title: string) => {
      if (title.trim()) updateSession(id, (s) => ({ ...s, title: title.trim().slice(0, 80) }));
    },
    [updateSession],
  );

  const deleteSession = useCallback(
    (id: string) => {
      requests.current.get(id)?.forEach((controller) => controller.abort());
      requests.current.delete(id);
      commit((state) => {
        const remaining = state.sessions.filter((s) => s.id !== id);
        const sessions = remaining.length ? remaining : [createSession()];
        return {
          ...state,
          sessions,
          activeSessionId:
            state.activeSessionId === id
              ? [...sessions].sort((a, b) => b.updatedAt - a.updatedAt)[0]!.id
              : state.activeSessionId,
        };
      });
    },
    [commit],
  );

  const setSidebarCollapsed = useCallback(
    (collapsed: boolean) => {
      commit((state) => ({ ...state, sidebarCollapsed: collapsed }));
    },
    [commit],
  );

  const loadScenario = useCallback(
    (scenarioId: ScenarioId) => {
      const id = newSession();
      const context = structuredClone(SCENARIOS[scenarioId].context);
      const message: MainMessage = {
        id: newId("msg"),
        role: "user",
        content: context.request,
        at: Date.now(),
      };
      updateSession(id, (s) => ({
        ...s,
        scenarioId,
        context,
        title: titleFromRequest(context.request),
        mainMessages: [message],
      }));
      void runMain(id, [message], context, 0, scenarioId, true);
    },
    [newSession, runMain, updateSession],
  );

  const sendMain = useCallback(
    (text: string) => {
      const session = stateRef.current.sessions.find(
        (s) => s.id === stateRef.current.activeSessionId,
      );
      if (!session || session.mainBusy || !text.trim()) return;
      const message: MainMessage = {
        id: newId("msg"),
        role: "user",
        content: text,
        at: Date.now(),
      };
      const version = session.context.request
        ? session.requirementsVersion + 1
        : session.requirementsVersion;
      const context = session.context.request
        ? {
            ...session.context,
            changes: [...session.context.changes, { id: message.id, text, at: message.at }],
          }
        : { ...session.context, request: text };
      const history = [...session.mainMessages, message];
      updateSession(session.id, (s) => ({
        ...s,
        context,
        requirementsVersion: version,
        mainMessages: history,
        updatedAt: Date.now(),
        title: s.title === "New session" ? titleFromRequest(text) : s.title,
      }));
      void runMain(session.id, history, context, version, session.scenarioId, false);
    },
    [runMain, updateSession],
  );

  const pasteReport = useCallback(
    (text: string) => {
      const s = stateRef.current.sessions.find(
        (session) => session.id === stateRef.current.activeSessionId,
      );
      if (!s || !text.trim()) return;
      const message: MainMessage = {
        id: newId("msg"),
        role: "assistant",
        content: text,
        pasted: true,
        at: Date.now(),
      };
      const report = addReport(
        s.id,
        message.id,
        text,
        s.context,
        s.requirementsVersion,
        s.scenarioId,
      );
      updateSession(s.id, (session) => ({
        ...session,
        updatedAt: Date.now(),
        title: session.title === "New session" ? "Report review" : session.title,
        mainMessages: [...session.mainMessages, { ...message, reportId: report.id }],
      }));
    },
    [addReport, updateSession],
  );

  const sendChecker = useCallback(
    async (text: string) => {
      const s = stateRef.current.sessions.find(
        (session) => session.id === stateRef.current.activeSessionId,
      );
      if (!s || s.checkerBusy || !text.trim()) return;
      const pending = request(s.id);
      const message = { id: newId("chk"), role: "user" as const, content: text, at: Date.now() };
      updateSession(s.id, (session) => ({
        ...session,
        checkerBusy: true,
        updatedAt: Date.now(),
        checkerFeed: [...session.checkerFeed, { kind: "chat", message }],
        title: session.title === "New session" ? titleFromRequest(text) : session.title,
      }));
      const report = s.reports.at(-1) ?? null;
      const rv = report ? s.reviews[report.id] : null;
      try {
        const content = await askChecker({
          question: text,
          report,
          review: rv && "at" in rv ? rv : null,
          history: s.checkerFeed.flatMap((item) => (item.kind === "chat" ? [item.message] : [])),
          context: s.context,
          signal: pending.signal,
        });
        if (!pending.signal.aborted)
          updateSession(s.id, (session) => ({
            ...session,
            updatedAt: Date.now(),
            checkerFeed: [
              ...session.checkerFeed,
              {
                kind: "chat",
                message: { id: newId("chk"), role: "assistant", content, at: Date.now() },
              },
            ],
          }));
      } catch (error) {
        if (!pending.signal.aborted)
          updateSession(s.id, (session) => ({
            ...session,
            checkerFeed: [
              ...session.checkerFeed,
              {
                kind: "chat",
                message: {
                  id: newId("chk"),
                  role: "assistant",
                  content: "Unable to respond: " + (error as Error).message,
                  at: Date.now(),
                },
              },
            ],
          }));
      } finally {
        pending.finish();
        updateSession(s.id, (session) => ({ ...session, checkerBusy: false }));
      }
    },
    [request, updateSession],
  );

  const retryReview = useCallback(
    (reportId: string) => {
      const session = stateRef.current.sessions.find(
        (s) => s.id === stateRef.current.activeSessionId,
      );
      const report = session?.reports.find((r) => r.id === reportId);
      if (session && report)
        void startReview(
          session.id,
          { ...report, requirementsVersion: session.requirementsVersion },
          session.context,
          session.scenarioId,
        );
    },
    [startReview],
  );

  const active =
    workspace.sessions.find((s) => s.id === workspace.activeSessionId) ?? workspace.sessions[0]!;
  return {
    ...active,
    hydrated,
    storageError,
    sessions: [...workspace.sessions].sort((a, b) => b.updatedAt - a.updatedAt),
    activeSessionId: workspace.activeSessionId,
    sidebarCollapsed: workspace.sidebarCollapsed,
    newSession,
    selectSession,
    renameSession,
    deleteSession,
    setSidebarCollapsed,
    loadScenario,
    reset: newSession,
    sendMain,
    sendChecker,
    pasteReport,
    retryReview,
  };
}

export type TransferSession = ReturnType<typeof useTransferSession>;
