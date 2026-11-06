import { useEffect, useRef } from "react";
import { ArrowUpRight, Bot, ClipboardCopy, Download, User } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import type { TransferSession } from "@/lib/transfer/useSession";
import { Composer, Markdown } from "./shared";

export function MainPanel({ s }: { s: TransferSession }) {
  const scroller = useRef<HTMLDivElement>(null);
  const last = s.mainMessages.at(-1);
  useEffect(() => {
    scroller.current?.scrollTo({ top: scroller.current.scrollHeight });
  }, [s.mainMessages.length, last?.content.length]);

  const copy = async (t: string) => {
    try {
      await navigator.clipboard.writeText(t);
      toast.success("Copied to clipboard");
    } catch {
      toast.error("Clipboard access is unavailable. Select the text to copy it.");
    }
  };
  const exportMd = (t: string, n: number) => {
    const url = URL.createObjectURL(new Blob([t], { type: "text/markdown" }));
    const a = Object.assign(document.createElement("a"), {
      href: url,
      download: `transfer-plan-report-${n}.md`,
    });
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <section className="flex h-full min-h-0 flex-col bg-background">
      <header className="flex h-16 shrink-0 items-center gap-2.5 border-b border-border px-6">
        <Bot className="h-4 w-4 text-lavender" />
        <h2 className="text-sm font-semibold">Transfer Assistant</h2>
      </header>
      <div ref={scroller} className="min-h-0 flex-1 overflow-y-auto px-6 py-8">
        {s.mainMessages.length === 0 ? (
          <div className="mx-auto flex h-full max-w-md flex-col items-center justify-center pb-12 text-center">
            <span className="flex size-12 items-center justify-center rounded-2xl bg-secondary">
              <ArrowUpRight className="size-6 text-lavender" strokeWidth={1.5} />
            </span>
            <p className="mt-6 text-2xl font-medium tracking-tight">What are we planning?</p>
            <p className="mt-2 text-sm text-muted-foreground">
              Tell me where your data needs to go.
            </p>
          </div>
        ) : (
          <div className="mx-auto flex max-w-3xl flex-col gap-6">
            {s.mainMessages.map((m) => {
              const report = m.reportId ? s.reports.find((r) => r.id === m.reportId) : undefined;
              return m.role === "user" ? (
                <div key={m.id} className="flex justify-end gap-3">
                  <div className="max-w-[85%] whitespace-pre-wrap rounded-2xl rounded-tr-sm bg-secondary px-4 py-3 text-sm">
                    {m.content}
                  </div>
                  <User className="mt-2 h-4 w-4 shrink-0 text-muted-foreground" />
                </div>
              ) : (
                <article key={m.id} data-message-id={m.id} className="group">
                  {report && (
                    <div className="mb-2 flex items-center gap-2 text-xs text-muted-foreground">
                      <span className="rounded-md border border-lavender/40 px-1.5 py-0.5 font-mono text-lavender">
                        Report {report.index}
                      </span>
                      {m.pasted && <span>pasted by you</span>}
                    </div>
                  )}
                  {m.content ? (
                    <Markdown>{m.content}</Markdown>
                  ) : (
                    <span className="animate-pulse-soft text-sm text-muted-foreground">
                      Thinking…
                    </span>
                  )}
                  {m.streaming && m.content && (
                    <span className="ml-1 inline-block h-4 w-1.5 animate-pulse-soft bg-lavender align-middle" />
                  )}
                  {!m.streaming && m.content && (
                    <div className="mt-3 flex gap-1 opacity-70 transition-opacity group-hover:opacity-100">
                      <Button variant="ghost" size="sm" onClick={() => copy(m.content)}>
                        <ClipboardCopy className="h-3.5 w-3.5" /> Copy
                      </Button>
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => exportMd(m.content, report?.index ?? 0)}
                      >
                        <Download className="h-3.5 w-3.5" /> Export .md
                      </Button>
                    </div>
                  )}
                </article>
              );
            })}
          </div>
        )}
      </div>
      <Composer
        placeholder="Describe your transfer…"
        onSend={s.sendMain}
        disabled={s.mainBusy || !s.hydrated}
        autoFocus
      />
    </section>
  );
}
