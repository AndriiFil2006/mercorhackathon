import { createFileRoute, Link } from "@tanstack/react-router";
import { ArrowRight, MessageSquare, Scale } from "lucide-react";
export const Route = createFileRoute("/")({
  head: () => ({
    meta: [
      { title: "CounselCheck — A clearer view of legal AI." },
      {
        name: "description",
        content: "Ask a legal question. Examine the answer. Find human expertise.",
      },
    ],
  }),
  component: Landing,
});
function Landing() {
  return (
    <main className="cc-landing cc-enter">
      <header>
        <Link to="/" className="cc-brand">
          <Scale />
          CounselCheck
        </Link>
        <Link to="/chats" search={{ chat: undefined }} className="cc-text-link">
          Chats
        </Link>
      </header>
      <section>
        <span className="cc-eyebrow">Human expertise. AI scrutiny.</span>
        <h1>
          Legal answers.
          <br />
          <span>A closer look.</span>
        </h1>
        <p>
          Ask your question. See the evidence.
          <br />
          Reach a lawyer when you need one.
        </p>
        <Link to="/workspace" className="cc-button">
          Begin an inquiry <ArrowRight size={17} />
        </Link>
      </section>
      <span className="cc-landing-note">CounselCheck</span>
    </main>
  );
}
