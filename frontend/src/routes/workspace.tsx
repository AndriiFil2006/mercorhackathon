import { useEffect, useState } from "react";
import { createFileRoute } from "@tanstack/react-router";
import { PanelLeft } from "lucide-react";
import { Button } from "@/components/ui/button";
import { ResizableHandle, ResizablePanel, ResizablePanelGroup } from "@/components/ui/resizable";
import { useIsMobile } from "@/hooks/use-mobile";
import { useTransferSession } from "@/lib/transfer/useSession";
import { MainPanel } from "@/components/transfer/MainPanel";
import { CheckerPanel } from "@/components/transfer/CheckerPanel";
import { SessionSidebar } from "@/components/transfer/SessionSidebar";
import { cn } from "@/lib/utils";

export const Route = createFileRoute("/workspace")({
  head: () => ({
    meta: [
      { title: "Workspace — Untitled" },
      { name: "description", content: "Plan your transfers. Check the details." },
      { property: "og:title", content: "Workspace — Untitled" },
      { property: "og:description", content: "Plan your transfers. Check the details." },
    ],
  }),
  component: Workspace,
});

function Workspace() {
  const s = useTransferSession();
  const mobile = useIsMobile();
  const [compact, setCompact] = useState(false);
  const [mobileSidebarOpen, setMobileSidebarOpen] = useState(false);
  const [tab, setTab] = useState<"main" | "checker">("main");

  useEffect(() => {
    const query = window.matchMedia("(max-width: 1099px)");
    const update = () => setCompact(query.matches);
    update();
    query.addEventListener("change", update);
    return () => query.removeEventListener("change", update);
  }, []);

  return (
    <div className="flex h-dvh overflow-hidden bg-background">
      <SessionSidebar
        s={s}
        mobileOpen={mobileSidebarOpen}
        onMobileOpenChange={setMobileSidebarOpen}
      />
      <main className="flex min-w-0 flex-1 flex-col">
        <header className="flex h-16 shrink-0 items-center gap-3 border-b border-border px-4 sm:px-6">
          {(mobile || s.sidebarCollapsed) && (
            <Button
              variant="ghost"
              size="icon"
              aria-label="Open sessions"
              className="size-8 shrink-0 text-muted-foreground"
              onClick={() => (mobile ? setMobileSidebarOpen(true) : s.setSidebarCollapsed(false))}
            >
              <PanelLeft />
            </Button>
          )}
          <h1 title={s.title} className="truncate text-sm font-medium">
            {s.title}
          </h1>
          <span className="ml-auto text-xs text-muted-foreground">Workspace</span>
        </header>
        {s.storageError && (
          <p role="status" className="border-b border-border px-5 py-2 text-xs text-warning">
            {s.storageError}
          </p>
        )}
        <div key={s.activeSessionId} className="flex min-h-0 flex-1 flex-col">
          {compact ? (
            <>
              <div
                className="grid shrink-0 grid-cols-2 border-b border-border px-4 text-sm"
                role="tablist"
                aria-label="Assistants"
              >
                {(["main", "checker"] as const).map((t) => (
                  <button
                    key={t}
                    role="tab"
                    aria-selected={tab === t}
                    aria-controls={"panel-" + t}
                    id={"tab-" + t}
                    onClick={() => setTab(t)}
                    className={cn(
                      "flex min-h-12 items-center justify-center whitespace-nowrap border-b-2 text-[13px] transition-colors",
                      tab === t
                        ? "border-primary text-foreground"
                        : "border-transparent text-muted-foreground",
                    )}
                  >
                    {t === "main" ? "Transfer Assistant" : "Plan Checker"}
                  </button>
                ))}
              </div>
              <div className="relative min-h-0 flex-1">
                <div
                  id="panel-main"
                  role="tabpanel"
                  aria-labelledby="tab-main"
                  className={cn("absolute inset-0", tab !== "main" && "hidden")}
                >
                  <MainPanel s={s} />
                </div>
                <div
                  id="panel-checker"
                  role="tabpanel"
                  aria-labelledby="tab-checker"
                  className={cn("absolute inset-0", tab !== "checker" && "hidden")}
                >
                  <CheckerPanel s={s} onFocusReport={() => setTab("main")} />
                </div>
              </div>
            </>
          ) : (
            <ResizablePanelGroup orientation="horizontal" className="min-h-0 flex-1">
              <ResizablePanel id="assistant" defaultSize="64%" minSize="40%">
                <MainPanel s={s} />
              </ResizablePanel>
              <ResizableHandle className="transition-colors hover:bg-primary" />
              <ResizablePanel id="checker" defaultSize="36%" minSize={300}>
                <CheckerPanel s={s} />
              </ResizablePanel>
            </ResizablePanelGroup>
          )}
        </div>
      </main>
    </div>
  );
}
