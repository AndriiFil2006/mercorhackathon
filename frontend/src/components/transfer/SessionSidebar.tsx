import { useState } from "react";
import { Link } from "@tanstack/react-router";
import {
  Check,
  Loader2,
  MessageSquare,
  MoreHorizontal,
  PanelLeftClose,
  Pencil,
  Plus,
  Trash2,
  Workflow,
  X,
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
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";
import { useIsMobile } from "@/hooks/use-mobile";
import { cn } from "@/lib/utils";
import type { TransferSession } from "@/lib/transfer/useSession";

interface Props {
  s: TransferSession;
  mobileOpen: boolean;
  onMobileOpenChange: (open: boolean) => void;
}

export function SessionSidebar({ s, mobileOpen, onMobileOpenChange }: Props) {
  const mobile = useIsMobile();
  const collapsed = !mobile && s.sidebarCollapsed;
  const [action, setAction] = useState<{
    kind: "rename" | "delete";
    id: string;
    title: string;
  } | null>(null);
  const [name, setName] = useState("");
  const closeMobile = () => onMobileOpenChange(false);
  const content = (
    <div className="flex h-full min-h-0 flex-col">
      <div
        className={cn(
          "flex h-16 shrink-0 items-center px-4",
          collapsed ? "justify-center px-0" : "gap-3",
        )}
      >
        <Link
          to="/"
          aria-label="Untitled home"
          className="flex min-w-0 items-center gap-2.5 text-sm font-semibold tracking-tight"
        >
          <Workflow className="size-5 shrink-0 text-lavender" strokeWidth={1.8} />
          {!collapsed && <span>Untitled</span>}
        </Link>
        {!collapsed && (
          <Button
            variant="ghost"
            size="icon"
            className="ml-auto size-7 text-muted-foreground"
            aria-label={mobile ? "Close sessions" : "Collapse sidebar"}
            onClick={() => (mobile ? closeMobile() : s.setSidebarCollapsed(true))}
          >
            {mobile ? <X /> : <PanelLeftClose />}
          </Button>
        )}
      </div>
      <div className={cn("px-3 pb-7 pt-3", collapsed && "px-2")}>
        <Button
          variant={collapsed ? "ghost" : "secondary"}
          className={cn(
            "h-10 w-full justify-start gap-3 rounded-lg font-medium shadow-none",
            collapsed && "justify-center px-0",
          )}
          aria-label="New session"
          onClick={() => {
            s.newSession();
            closeMobile();
          }}
        >
          <Plus className="size-4" />
          {!collapsed && "New session"}
        </Button>
      </div>
      {!collapsed && (
        <nav aria-label="Saved sessions" className="min-h-0 flex-1 overflow-y-auto px-2 pb-5">
          <p className="mb-3 px-3 text-[11px] font-medium tracking-wide text-muted-foreground">
            Recent sessions
          </p>
          <div className="space-y-1">
            {s.sessions.map((session) => (
              <div
                key={session.id}
                className={cn(
                  "group flex items-center rounded-lg transition-colors",
                  s.activeSessionId === session.id
                    ? "bg-sidebar-accent text-sidebar-accent-foreground"
                    : "text-muted-foreground hover:bg-secondary hover:text-foreground",
                )}
              >
                <button
                  className="flex h-10 min-w-0 flex-1 items-center gap-2.5 pl-3 text-left text-[13px]"
                  aria-current={s.activeSessionId === session.id ? "page" : undefined}
                  title={session.title}
                  onClick={() => {
                    s.selectSession(session.id);
                    closeMobile();
                  }}
                >
                  {session.mainBusy || session.checkerBusy ? (
                    <Loader2 className="size-3.5 shrink-0 animate-spin" />
                  ) : (
                    <MessageSquare className="size-3.5 shrink-0 opacity-70" />
                  )}
                  <span className="truncate">{session.title}</span>
                </button>
                <DropdownMenu>
                  <DropdownMenuTrigger asChild>
                    <Button
                      variant="ghost"
                      size="icon"
                      className="mr-1 size-7 shrink-0 text-muted-foreground opacity-100 focus:opacity-100 sm:opacity-0 sm:group-hover:opacity-100 data-[state=open]:opacity-100"
                      aria-label={"Session options for " + session.title}
                    >
                      <MoreHorizontal />
                    </Button>
                  </DropdownMenuTrigger>
                  <DropdownMenuContent align="start" side="bottom" className="w-40">
                    <DropdownMenuItem
                      onSelect={() => {
                        setName(session.title);
                        setAction({ kind: "rename", id: session.id, title: session.title });
                      }}
                    >
                      <Pencil className="mr-2 size-3.5" />
                      Rename
                    </DropdownMenuItem>
                    <DropdownMenuItem
                      className="text-danger focus:text-danger"
                      onSelect={() =>
                        setAction({ kind: "delete", id: session.id, title: session.title })
                      }
                    >
                      <Trash2 className="mr-2 size-3.5" />
                      Delete
                    </DropdownMenuItem>
                  </DropdownMenuContent>
                </DropdownMenu>
              </div>
            ))}
          </div>
        </nav>
      )}
    </div>
  );

  return (
    <>
      {mobile ? (
        <Sheet open={mobileOpen} onOpenChange={onMobileOpenChange}>
          <SheetContent
            side="left"
            className="w-72 border-sidebar-border bg-sidebar p-0 [&>button]:hidden"
          >
            <SheetHeader className="sr-only">
              <SheetTitle>Sessions</SheetTitle>
              <SheetDescription>Your saved conversations</SheetDescription>
            </SheetHeader>
            {content}
          </SheetContent>
        </Sheet>
      ) : (
        <aside
          aria-label="Session sidebar"
          className={cn(
            "h-full shrink-0 overflow-hidden border-r border-sidebar-border bg-sidebar transition-[width] duration-200",
            collapsed ? "w-16" : "w-60",
          )}
        >
          {content}
        </aside>
      )}
      <Dialog
        open={action?.kind === "rename"}
        onOpenChange={(open) => {
          if (!open) setAction(null);
        }}
      >
        <DialogContent className="max-w-sm">
          <DialogHeader>
            <DialogTitle>Rename session</DialogTitle>
            <DialogDescription>Give this conversation a name.</DialogDescription>
          </DialogHeader>
          <form
            onSubmit={(event) => {
              event.preventDefault();
              if (action && name.trim()) {
                s.renameSession(action.id, name);
                setAction(null);
              }
            }}
          >
            <input
              aria-label="Session name"
              maxLength={80}
              autoFocus
              value={name}
              onChange={(event) => setName(event.target.value)}
              className="h-11 w-full rounded-lg border border-input bg-background px-3 text-sm outline-none focus:border-primary"
            />
            <DialogFooter className="mt-5">
              <Button type="button" variant="ghost" onClick={() => setAction(null)}>
                Cancel
              </Button>
              <Button type="submit" disabled={!name.trim()}>
                <Check className="size-4" />
                Save
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
      <AlertDialog
        open={action?.kind === "delete"}
        onOpenChange={(open) => {
          if (!open) setAction(null);
        }}
      >
        <AlertDialogContent className="max-w-sm">
          <AlertDialogHeader>
            <AlertDialogTitle>Delete this session?</AlertDialogTitle>
            <AlertDialogDescription>
              This removes “{action?.title}” and its messages from this browser.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
              onClick={() => {
                if (action) s.deleteSession(action.id);
                setAction(null);
              }}
            >
              Delete
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  );
}
