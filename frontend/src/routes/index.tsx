import { createFileRoute, Link } from "@tanstack/react-router";
import { ArrowRight, ArrowUpRight, Workflow } from "lucide-react";
import { Button } from "@/components/ui/button";

export const Route = createFileRoute("/")({
  head: () => ({
    meta: [
      { title: "Untitled — Transfer plans, considered." },
      { name: "description", content: "Plan your transfers. Check the details." },
      { property: "og:title", content: "Untitled" },
      { property: "og:description", content: "Plan your transfers. Check the details." },
    ],
  }),
  component: Index,
});

function Index() {
  return (
    <main className="landing-shell relative isolate flex min-h-dvh flex-col overflow-hidden">
      <header className="relative z-10 flex h-24 shrink-0 items-center px-7 sm:px-12 lg:px-20">
        <Link
          to="/"
          aria-label="Untitled home"
          className="inline-flex items-center gap-3 text-lg font-semibold tracking-tight"
        >
          <span className="flex size-9 items-center justify-center rounded-xl bg-primary text-primary-foreground">
            <Workflow className="size-5" strokeWidth={1.8} />
          </span>
          Untitled
          <span className="size-1.5 self-start rounded-full bg-primary" />
        </Link>
      </header>
      <div className="relative z-10 mx-auto grid w-full max-w-[1440px] flex-1 items-center gap-16 px-7 pb-24 pt-12 sm:px-12 lg:grid-cols-[1.2fr_0.8fr] lg:gap-24 lg:px-20 lg:pb-32 lg:pt-0">
        <div className="max-w-3xl">
          <h1 className="text-[clamp(3.25rem,7.3vw,7rem)] font-medium leading-[1.04] tracking-[-0.065em]">
            Every move.
            <br />
            <span className="text-lavender">Well considered.</span>
          </h1>
          <p className="mt-7 text-base leading-relaxed text-muted-foreground sm:text-lg">
            Plan your transfers. Check the details.
          </p>
          <Button
            asChild
            size="lg"
            className="mt-10 h-12 rounded-xl px-6 text-sm font-semibold shadow-none"
          >
            <Link to="/workspace">
              Get started <ArrowRight className="ml-5 size-4" />
            </Link>
          </Button>
        </div>
        <div
          aria-hidden="true"
          className="landing-object relative mx-auto hidden aspect-[4/5] w-full max-w-[390px] lg:block"
        >
          <div className="absolute inset-0 rounded-[32px] bg-primary" />
          <div className="absolute inset-x-8 top-8 flex items-center gap-2">
            <span className="size-2 rounded-full bg-background" />
            <span className="h-px w-10 bg-background/30" />
          </div>
          <div className="absolute inset-0 flex items-center justify-center">
            <ArrowUpRight className="size-56 text-primary-foreground" strokeWidth={0.8} />
          </div>
          <div className="absolute inset-x-8 bottom-8 flex justify-between">
            <span className="h-1.5 w-16 rounded-full bg-primary-foreground/70" />
            <span className="h-1.5 w-6 rounded-full bg-primary-foreground/30" />
          </div>
        </div>
      </div>
    </main>
  );
}
