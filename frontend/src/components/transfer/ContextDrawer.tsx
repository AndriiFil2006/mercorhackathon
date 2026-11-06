import { Sheet, SheetContent, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import type { TransferContext } from "@/lib/transfer/types";

export function ContextDrawer({ open, onOpenChange, context }: { open: boolean; onOpenChange: (o: boolean) => void; context: TransferContext }) {
  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent className="w-full overflow-y-auto sm:max-w-lg">
        <SheetHeader><SheetTitle>Request & context</SheetTitle></SheetHeader>
        <div className="mt-6 flex flex-col gap-6 px-4 pb-8 text-sm">
          <Section title="Original request">
            {context.request ? <pre className="whitespace-pre-wrap font-sans">{context.request}</pre> : <Empty />}
          </Section>
          <Section title="Requirement changes">
            {context.changes.length ? (
              <ol className="flex flex-col gap-2">
                {context.changes.map((c, i) => (
                  <li key={c.id} className="rounded-md border border-border p-2.5">
                    <span className="mr-2 font-mono text-xs text-lavender">#{i + 1}</span>{c.text}
                  </li>
                ))}
              </ol>
            ) : <Empty />}
          </Section>
          <Section title="Supplied endpoints">
            {context.endpoints.length ? (
              <ul className="flex flex-col gap-2">
                {context.endpoints.map((e) => (
                  <li key={e.label} className="rounded-md border border-border p-2.5">
                    <div className="text-xs text-muted-foreground">{e.label} · {e.kind}</div>
                    <code className="font-mono text-xs text-lavender">{e.value}</code>
                  </li>
                ))}
              </ul>
            ) : <Empty />}
          </Section>
          <Section title="Example file inventories">
            {context.inventories.length ? context.inventories.map((inv) => (
              <div key={inv.label} className="mb-3">
                <div className="mb-1 text-xs text-muted-foreground">{inv.label}</div>
                <pre className="rounded-md border border-border bg-background p-2.5 font-mono text-xs">{inv.files.join("\n")}</pre>
              </div>
            )) : <Empty />}
          </Section>
        </div>
      </SheetContent>
    </Sheet>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section>
      <h3 className="mb-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground">{title}</h3>
      {children}
    </section>
  );
}
const Empty = () => <p className="text-muted-foreground">Nothing supplied.</p>;
