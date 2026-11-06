import { createFileRoute } from "@tanstack/react-router";
import { LawyerConnection } from "@/components/legal/LawyerChats";
export const Route = createFileRoute("/connect")({
  validateSearch: (s: Record<string, unknown>) => ({
    session: typeof s["session"] === "string" ? s["session"] : "",
    evaluation: typeof s["evaluation"] === "string" ? s["evaluation"] : "",
  }),
  head: () => ({ meta: [{ title: "Connect with counsel — CounselCheck" }] }),
  component: () => {
    const s = Route.useSearch();
    return <LawyerConnection sessionId={s["session"]} evaluationId={s["evaluation"]} />;
  },
});
