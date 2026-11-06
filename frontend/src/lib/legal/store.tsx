import { createContext, useContext, useEffect, useState, type ReactNode } from "react";
import { newSession, type Store } from "./types";
const KEY = "counselcheck:v1";
const Context = createContext<{
  data: Store;
  setData: React.Dispatch<React.SetStateAction<Store>>;
  ready: boolean;
  storageError: string;
  clearError: () => void;
} | null>(null);
export function LegalProvider({ children }: { children: ReactNode }) {
  const [data, setData] = useState<Store>({
    sessions: [],
    activeId: "",
    chats: [],
    collapsed: false,
  });
  const [ready, setReady] = useState(false),
    [storageError, setError] = useState("");
  useEffect(() => {
    try {
      const raw = localStorage.getItem(KEY);
      if (raw) {
        const d = JSON.parse(raw);
        if (
          !Array.isArray(d.sessions) ||
          !Array.isArray(d.chats) ||
          d.sessions.some(
            (s: any) => !s.id || !Array.isArray(s.messages) || !Array.isArray(s.evaluations),
          ) ||
          d.chats.some((c: any) => !c.id || !Array.isArray(c.messages))
        )
          throw new Error();
        d.sessions.forEach((s: any) => {
          s.busy = false;
          s.evaluations.forEach((e: any) =>
            e.reviews.forEach((r: any) => {
              if (r.status === "searching" || r.status === "queued") {
                r.status = "error";
                r.error = "Review interrupted. Retry to finish.";
              }
            }),
          );
        });
        d.chats.forEach((c: any) => {
          c.busy = false;
        });
        setData(d);
      } else {
        const s = newSession();
        setData({ sessions: [s], activeId: s.id, chats: [], collapsed: false });
      }
    } catch {
      setError(
        "Saved conversations could not be loaded. Existing browser data has been preserved. Clear this site's storage to start again.",
      );
    } finally {
      setReady(true);
    }
  }, []);
  useEffect(() => {
    if (!ready || storageError) return;
    try {
      localStorage.setItem(KEY, JSON.stringify(data));
    } catch {
      setError(
        "Browser storage is full or unavailable. New changes may not survive a refresh. Export your evaluations before leaving.",
      );
    }
  }, [data, ready, storageError]);
  return (
    <Context.Provider
      value={{ data, setData, ready, storageError, clearError: () => setError("") }}
    >
      {children}
    </Context.Provider>
  );
}
export function useLegal() {
  const c = useContext(Context);
  if (!c) throw new Error("LegalProvider is missing");
  return c;
}
