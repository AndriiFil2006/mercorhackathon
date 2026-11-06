import { useEffect, useRef, useState } from "react";
import {
  AlertTriangle,
  CheckCircle2,
  ClipboardPaste,
  HelpCircle,
  Loader2,
  ShieldCheck,
  XCircle,
  Hourglass,
  History,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import type { TransferSession } from "@/lib/transfer/useSession";
import type { Review, ReviewStatus } from "@/lib/transfer/types";
import { cn } from "@/lib/utils";
import { Composer, Markdown, highlightInMessage } from "./shared";

const STATUS: Record<ReviewStatus, { label: string; icon: typeof Loader2; cls: string }> = {
  waiting: {
    label: "Waiting for report",
    icon: Hourglass,
    cls: "text-muted-foreground border-border",
  },
  reviewing: { label: "Reviewing", icon: Loader2, cls: "text-lavender border-lavender/40" },
  issues: { label: "Issues found", icon: XCircle, cls: "text-danger border-danger/40" },
  clean: { label: "No issues found", icon: CheckCircle2, cls: "text-success border-success/40" },
  "needs-info": {
    label: "Needs information",
    icon: HelpCircle,
    cls: "text-warning border-warning/40",
  },
  failed: {
    label: "Review failed",
    icon: AlertTriangle,
    cls: "text-muted-foreground border-border",
  },
};

export function StatusBadge({ status }: { status: ReviewStatus }) {
  const s = STATUS[status];
  const Icon = s.icon;
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-xs font-medium",
        s.cls,
      )}
    >
      <Icon className={cn("h-3.5 w-3.5", status === "reviewing" && "animate-spin")} />
      {s.label}
    </span>
  );
}

export function useCurrentStatus(s: TransferSession): ReviewStatus {
  const r = s.reports.at(-1);
  if (!r) return "waiting";
  return s.reviews[r.id]?.status ?? "reviewing";
}

function ReviewCard({
  s,
  reportId,
  onFocusReport,
}: {
  s: TransferSession;
  reportId: string;
  onFocusReport?: (() => void) | undefined;
}) {
  const report = s.reports.find((r) => r.id === reportId);
  const rv = s.reviews[reportId];
  if (!report || !rv) return null;
  const done = "at" in rv ? (rv as Review) : null;
  const stale = done && !done.superseded && done.requirementsVersion < s.requirementsVersion;
  const isLatest = s.reports.at(-1)?.id === reportId;

  const focus = (quote: string) => {
    onFocusReport?.();
    setTimeout(() => highlightInMessage(report.messageId, quote), 60);
  };

  return (
    <div className={cn("rounded-xl border border-border bg-card p-4", !isLatest && "opacity-75")}>
      <div className="flex flex-wrap items-center gap-2">
        <span className="font-mono text-xs text-lavender">Review · Report {report.index}</span>
        <StatusBadge status={rv.status} />
        {done?.demo && (
          <span className="rounded border border-border px-1.5 text-[10px] uppercase tracking-wide text-muted-foreground">
            Demo
          </span>
        )}
      </div>
      {stale && (
        <p className="mt-3 flex items-center gap-1.5 rounded-md bg-warning/10 px-2.5 py-1.5 text-xs text-warning">
          <History className="h-3.5 w-3.5" /> Requirements changed since this review.
        </p>
      )}
      {!done ? (
        <p className="mt-3 text-sm text-muted-foreground">
          Checking Report {report.index} against the request and supplied context…
        </p>
      ) : (
        <>
          <p className="mt-3 text-sm">{done.summary}</p>
          {done.findings.length > 0 && (
            <ul className="mt-4 flex flex-col gap-3">
              {done.findings.map((f) => (
                <li key={f.id}>
                  <button
                    onClick={() => focus(f.quote)}
                    className={cn(
                      "w-full rounded-lg border bg-background p-3 text-left transition-colors hover:border-lavender/60",
                      f.kind === "contradiction"
                        ? f.severity === "high"
                          ? "border-danger/40"
                          : "border-warning/40"
                        : "border-warning/30",
                    )}
                  >
                    <div className="flex items-center gap-2">
                      <span
                        className={cn(
                          "h-2 w-2 rounded-full",
                          f.kind === "contradiction" && f.severity === "high"
                            ? "bg-danger"
                            : "bg-warning",
                        )}
                      />
                      <span className="text-sm font-medium">{f.title}</span>
                      <span className="ml-auto text-[10px] uppercase tracking-wide text-muted-foreground">
                        {f.kind === "contradiction" ? "Contradiction" : "Missing evidence"}
                      </span>
                    </div>
                    <blockquote className="mt-2 border-l-2 border-warning/60 pl-2 font-mono text-xs text-muted-foreground">
                      “{f.quote}”
                    </blockquote>
                    <p className="mt-2 text-sm text-muted-foreground">{f.explanation}</p>
                    <dl className="mt-2 grid grid-cols-[auto_1fr] gap-x-3 gap-y-1 text-xs">
                      <dt className="text-muted-foreground">Requested</dt>
                      <dd className="text-success">{f.requested}</dd>
                      <dt className="text-muted-foreground">Proposed</dt>
                      <dd className="text-danger">{f.proposed}</dd>
                      <dt className="text-muted-foreground">Source</dt>
                      <dd>{f.reference}</dd>
                    </dl>
                  </button>
                </li>
              ))}
            </ul>
          )}
          {done.checks.length > 0 && (
            <details className="mt-3 text-xs text-muted-foreground">
              <summary className="cursor-pointer">Checks performed ({done.checks.length})</summary>
              <ul className="mt-2 list-disc pl-5">
                {done.checks.map((c) => (
                  <li key={c}>{c}</li>
                ))}
              </ul>
            </details>
          )}
          {done.status === "clean" && (
            <p className="mt-3 text-xs text-muted-foreground">
              Applies only to the supplied information and the checks listed.
            </p>
          )}
        </>
      )}
      {done?.status === "failed" && !done.superseded && (
        <Button
          variant="outline"
          size="sm"
          className="mt-3"
          onClick={() => s.retryReview(reportId)}
        >
          Retry review
        </Button>
      )}
    </div>
  );
}

export function CheckerPanel({
  s,
  onFocusReport,
}: {
  s: TransferSession;
  onFocusReport?: (() => void) | undefined;
}) {
  const [pasteOpen, setPasteOpen] = useState(false);
  const [draft, setDraft] = useState("");
  const status = useCurrentStatus(s);
  const scroller = useRef<HTMLDivElement>(null);
  useEffect(() => {
    scroller.current?.scrollTo({ top: scroller.current.scrollHeight, behavior: "smooth" });
  }, [s.checkerFeed.length, status]);

  return (
    <section className="flex h-full min-h-0 flex-col bg-card">
      <header className="flex h-16 shrink-0 items-center gap-2.5 border-b border-border px-5">
        <ShieldCheck className="h-4 w-4 text-lavender" />
        <h2 className="whitespace-nowrap text-sm font-semibold">Plan Checker</h2>
        <div className="ml-auto flex items-center gap-2">
          <StatusBadge status={status} />
          <Button
            variant="ghost"
            size="sm"
            onClick={() => setPasteOpen(true)}
            aria-label="Paste report"
          >
            <ClipboardPaste className="h-3.5 w-3.5" />
          </Button>
        </div>
      </header>
      <div ref={scroller} className="min-h-0 flex-1 overflow-y-auto px-4 py-5">
        <div className="flex flex-col gap-4">
          {s.reports.length === 0 && (
            <div className="mx-auto flex min-h-72 max-w-xs flex-col items-center justify-center px-4 py-10 text-center">
              <span className="flex size-11 items-center justify-center rounded-2xl bg-secondary">
                <ShieldCheck className="size-5 text-lavender" strokeWidth={1.5} />
              </span>
              <p className="mt-5 text-base font-medium tracking-tight">A second look.</p>
              <p className="mt-1 text-sm text-muted-foreground">
                Your report review will appear here.
              </p>
              <Button
                variant="outline"
                size="sm"
                className="mt-4"
                onClick={() => setPasteOpen(true)}
              >
                <ClipboardPaste className="h-3.5 w-3.5" /> Paste report
              </Button>
            </div>
          )}
          {s.checkerFeed.map((item) =>
            item.kind === "review" ? (
              <ReviewCard
                key={item.reportId}
                s={s}
                reportId={item.reportId}
                onFocusReport={onFocusReport}
              />
            ) : item.message.role === "user" ? (
              <div
                key={item.message.id}
                className="ml-auto max-w-[90%] whitespace-pre-wrap rounded-2xl rounded-tr-sm bg-secondary px-3.5 py-2.5 text-sm"
              >
                {item.message.content}
              </div>
            ) : (
              <div key={item.message.id} className="text-sm">
                <Markdown>{item.message.content}</Markdown>
              </div>
            ),
          )}
          {s.checkerBusy && (
            <span className="animate-pulse-soft text-sm text-muted-foreground">
              Checker is thinking…
            </span>
          )}
        </div>
      </div>
      <Composer
        placeholder="Ask about your report…"
        onSend={(t) => void s.sendChecker(t)}
        disabled={s.checkerBusy || !s.hydrated}
      />
      <Dialog open={pasteOpen} onOpenChange={setPasteOpen}>
        <DialogContent className="max-w-2xl">
          <DialogHeader>
            <DialogTitle>Paste a transfer report</DialogTitle>
            <DialogDescription>Add the report you want to review.</DialogDescription>
          </DialogHeader>
          <textarea
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            placeholder="Paste Markdown or plain text…"
            aria-label="Report text"
            className="h-72 w-full resize-none rounded-lg border border-border bg-background p-3 font-mono text-xs outline-none focus:border-lavender/60"
          />
          <DialogFooter>
            <Button
              disabled={!draft.trim()}
              onClick={() => {
                s.pasteReport(draft.trim());
                setDraft("");
                setPasteOpen(false);
              }}
            >
              Add report & review
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </section>
  );
}
