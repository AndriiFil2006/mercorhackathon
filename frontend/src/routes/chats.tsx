import { createFileRoute } from "@tanstack/react-router";
import { LawyerChats } from "@/components/legal/LawyerChats";
export const Route = createFileRoute("/chats")({
  validateSearch: (s: Record<string, unknown>) => ({
    chat: typeof s["chat"] === "string" ? s["chat"] : undefined,
  }),
  head: () => ({ meta: [{ title: "Chats — CounselCheck" }] }),
  component: () => {
    const { chat } = Route.useSearch();
    return <LawyerChats chatId={chat} />;
  },
});
