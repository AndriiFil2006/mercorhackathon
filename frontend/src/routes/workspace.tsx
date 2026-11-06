import { createFileRoute } from "@tanstack/react-router";
import { LegalWorkspace } from "@/components/legal/LegalWorkspace";
export const Route = createFileRoute("/workspace")({
  head: () => ({ meta: [{ title: "Legal workspace — CounselCheck" }] }),
  component: LegalWorkspace,
});
