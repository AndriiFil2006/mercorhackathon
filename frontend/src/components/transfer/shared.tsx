import { useEffect, useRef, useState, type KeyboardEvent } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { ArrowUp } from "lucide-react";
import { Button } from "@/components/ui/button";

export function Markdown({ children }: { children: string }) {
  return (
    <div className="prose-report break-words">
      <ReactMarkdown remarkPlugins={[remarkGfm]}>{children}</ReactMarkdown>
    </div>
  );
}

export function Composer({
  placeholder,
  onSend,
  disabled,
  hint,
  autoFocus = false,
}: {
  placeholder: string;
  onSend: (t: string) => void;
  disabled?: boolean;
  hint?: string;
  autoFocus?: boolean;
}) {
  const [value, setValue] = useState("");
  const ref = useRef<HTMLTextAreaElement>(null);
  const initiallyFocused = useRef(false);
  useEffect(() => {
    if (autoFocus && !disabled && !initiallyFocused.current) {
      ref.current?.focus({ preventScroll: true });
      initiallyFocused.current = true;
    }
  }, [autoFocus, disabled]);
  useEffect(() => {
    const field = ref.current;
    if (!field) return;
    field.style.height = "auto";
    field.style.height = Math.min(field.scrollHeight, 160) + "px";
  }, [value]);
  const submit = () => {
    const t = value.trim();
    if (!t || disabled) return;
    onSend(t);
    setValue("");
  };
  const onKey = (e: KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) {
      e.preventDefault();
      submit();
    }
  };
  return (
    <div className="shrink-0 px-4 pb-4 pt-2 sm:px-5 sm:pb-5">
      {hint && <p className="mb-2 px-1 text-xs text-muted-foreground">{hint}</p>}
      <div className="flex items-end gap-2 rounded-2xl border border-input bg-secondary p-2 transition-colors focus-within:border-primary">
        <textarea
          ref={ref}
          rows={1}
          value={value}
          onChange={(e) => setValue(e.target.value)}
          onKeyDown={onKey}
          placeholder={placeholder}
          aria-label={placeholder}
          className="max-h-40 min-h-9 flex-1 resize-none bg-transparent px-2 py-1.5 text-sm text-foreground outline-none placeholder:text-muted-foreground"
        />
        <Button
          size="icon"
          className="size-9 shrink-0 rounded-xl shadow-none"
          onClick={submit}
          disabled={disabled || !value.trim()}
          aria-label="Send"
        >
          <ArrowUp className="h-4 w-4" />
        </Button>
      </div>
    </div>
  );
}

/** Highlight `quote` inside the element for message `messageId` using the CSS Custom Highlight API. */
export function highlightInMessage(messageId: string, quote: string) {
  const el = document.querySelector<HTMLElement>(`[data-message-id="${messageId}"] .prose-report`);
  if (!el) return false;
  const walker = document.createTreeWalker(el, NodeFilter.SHOW_TEXT);
  const nodes: { node: Text; start: number }[] = [];
  let full = "";
  while (walker.nextNode()) {
    const n = walker.currentNode as Text;
    nodes.push({ node: n, start: full.length });
    full += n.data;
  }
  const idx = full.indexOf(quote);
  if (idx < 0) {
    el.scrollIntoView({ behavior: "smooth", block: "center" });
    return false;
  }
  const end = idx + quote.length;
  const locate = (pos: number) => {
    const hit = [...nodes].reverse().find((n) => n.start <= pos)!;
    return { node: hit.node, offset: pos - hit.start };
  };
  const a = locate(idx);
  const b = locate(end);
  const range = document.createRange();
  range.setStart(a.node, a.offset);
  range.setEnd(b.node, Math.min(b.offset, b.node.length));
  const reg = (globalThis as unknown as { CSS?: { highlights?: Map<string, unknown> } }).CSS
    ?.highlights;
  const HL = (globalThis as unknown as { Highlight?: new (r: Range) => unknown }).Highlight;
  if (reg && HL) reg.set("finding-hl", new HL(range));
  (range.startContainer.parentElement ?? el).scrollIntoView({
    behavior: "smooth",
    block: "center",
  });
  return true;
}
