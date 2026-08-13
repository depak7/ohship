import type { Metadata } from "next";
import Link from "next/link";
import { Button } from "@/components/ui";
import { InstallCommand, INSTALL_COMMAND } from "@/components/install-command";
import { LandingRedirect } from "@/components/landing-redirect";

export const metadata: Metadata = {
  title: "Planlog — Plan → Approve → Done",
  description:
    "Markdown plans humans and coding agents share. Agents read the plan before coding and post Done when they ship.",
};

export default function LandingPage() {
  return (
    <div className="grain min-h-screen">
      <LandingRedirect />
      <header className="sticky top-0 z-20 border-b border-[var(--line)] bg-[color-mix(in_srgb,var(--bg)_88%,white)] backdrop-blur">
        <div className="mx-auto flex max-w-5xl items-center justify-between gap-4 px-4 py-3">
          <a href="#top" className="text-lg font-semibold tracking-tight">
            Planlog
          </a>
          <nav className="hidden items-center gap-5 text-sm text-[var(--muted)] sm:flex">
            <a href="#how" className="hover:text-[var(--ink)]">
              How it works
            </a>
            <a href="#install" className="hover:text-[var(--ink)]">
              Install
            </a>
            <a href="#use" className="hover:text-[var(--ink)]">
              Use
            </a>
          </nav>
          <div className="flex items-center gap-2">
            <Link href="/login?next=/plans">
              <Button variant="ghost">Sign in</Button>
            </Link>
            <Link href="/login?mode=signup&next=/plans">
              <Button>Get started</Button>
            </Link>
          </div>
        </div>
      </header>

      <main id="top" className="mx-auto max-w-5xl px-4">
        <section className="py-16 sm:py-24">
          <p className="text-sm uppercase tracking-[0.2em] text-[var(--accent)]">Planlog</p>
          <h1 className="mt-3 max-w-3xl text-4xl font-semibold tracking-tight sm:text-5xl">
            Plan → Approve → Done for humans and coding agents.
          </h1>
          <p className="mt-4 max-w-2xl text-lg text-[var(--muted)]">
            Markdown plans are the source of truth. Agents read them before coding and write Done
            when they ship — not chat history.
          </p>
          <div className="mt-8 flex flex-wrap items-center gap-3">
            <Link href="/login?mode=signup&next=/plans">
              <Button>Create account</Button>
            </Link>
            <a href="#install">
              <Button variant="outline">Copy install command</Button>
            </a>
          </div>
        </section>

        <section id="how" className="border-t border-[var(--line)] py-16">
          <h2 className="text-2xl font-semibold tracking-tight">How it works</h2>
          <p className="mt-2 max-w-2xl text-[var(--muted)]">
            One loop for the team and the agent. The plan stays in Planlog.
          </p>
          <ol className="mt-8 grid gap-4 sm:grid-cols-3">
            {[
              ["Plan", "Write intent, scope, and acceptance criteria in markdown. Project is required."],
              ["Approve", "Reviewers suggest changes or approve. Agents update only while the plan is a draft."],
              ["Done", "When shipped, post_done with summary and links. That record is permanent."],
            ].map(([title, body]) => (
              <li key={title} className="surface rounded-2xl p-5">
                <p className="text-sm uppercase tracking-[0.16em] text-[var(--accent)]">{title}</p>
                <p className="mt-2 text-sm text-[var(--muted)]">{body}</p>
              </li>
            ))}
          </ol>
        </section>

        <section id="install" className="border-t border-[var(--line)] py-16">
          <h2 className="text-2xl font-semibold tracking-tight">Install in any repo</h2>
          <p className="mt-2 max-w-2xl text-[var(--muted)]">
            One command. No Planlog clone. Works with Cursor, Claude Code, Copilot, Gemini — any
            agent that reads a markdown instruction file.
          </p>
          <InstallCommand className="mt-6 max-w-2xl" />
          <ul className="mt-6 max-w-2xl space-y-2 text-sm text-[var(--muted)]">
            <li>Grafts Planlog instructions into <code>AGENTS.md</code> / <code>CLAUDE.md</code></li>
            <li>Wires MCP to <code>https://planlog.depak.dev/mcp</code> (OAuth, same login)</li>
            <li>Installs a Cursor skill so agents <code>get_plan</code> before work and <code>post_done</code> when shipped</li>
          </ul>
          <p className="mt-4 text-sm text-[var(--muted)]">
            Paste this in your repo, reload MCP, then Allow access.
          </p>
        </section>

        <section id="use" className="border-t border-[var(--line)] py-16">
          <h2 className="text-2xl font-semibold tracking-tight">Use</h2>
          <ol className="mt-6 max-w-2xl list-decimal space-y-3 pl-5 text-[var(--muted)]">
            <li>Sign up → create an organization → write a markdown plan</li>
            <li>Run install in the repo; paste the <code>plan_id</code> in the agent</li>
            <li>
              Agent: <code>get_plan</code> → code → <code>post_done</code> (summary + links)
            </li>
            <li>Teammates: approve, suggest, or Notify on Done</li>
          </ol>

          <div className="mt-8 max-w-2xl overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead>
                <tr className="border-b border-[var(--line)] text-[var(--muted)]">
                  <th className="py-2 pr-4 font-medium">Do</th>
                  <th className="py-2 font-medium">Don&apos;t</th>
                </tr>
              </thead>
              <tbody className="text-[var(--ink)]">
                <tr className="border-b border-[var(--line)]">
                  <td className="py-3 pr-4">Read the plan before editing code</td>
                  <td className="py-3">Skip <code>get_plan</code> when a plan_id is known</td>
                </tr>
                <tr className="border-b border-[var(--line)]">
                  <td className="py-3 pr-4">
                    <code>post_done</code> with summary + links when finished
                  </td>
                  <td className="py-3">Use <code>add_suggestion</code> to record shipped work</td>
                </tr>
                <tr>
                  <td className="py-3 pr-4">Notify teammates for the next implementer</td>
                  <td className="py-3">Leave shipped work only in chat</td>
                </tr>
              </tbody>
            </table>
          </div>
        </section>

        <section className="border-t border-[var(--line)] py-16">
          <h2 className="text-2xl font-semibold tracking-tight">Why it sticks</h2>
          <ul className="mt-6 grid gap-4 sm:grid-cols-2">
            {[
              ["Done is history", "Permanent record — not a Slack thread that disappears."],
              ["Share links", "Team or Anyone links for people inside and outside the org."],
              ["Sent to me", "Handoffs land in a filter the next person actually opens."],
              ["Any coding agent", "Cursor, Claude Code, Copilot, Gemini — same markdown contract."],
            ].map(([title, body]) => (
              <li key={title} className="surface rounded-2xl p-5">
                <p className="font-medium">{title}</p>
                <p className="mt-1 text-sm text-[var(--muted)]">{body}</p>
              </li>
            ))}
          </ul>
        </section>
      </main>

      <footer className="border-t border-[var(--line)] py-10">
        <div className="mx-auto max-w-5xl space-y-3 px-4 text-sm text-[var(--muted)]">
          <p>
            MCP:{" "}
            <code className="text-[var(--ink)]">https://planlog.depak.dev/mcp</code>
          </p>
          <p>
            Install: <code className="text-[var(--ink)]">{INSTALL_COMMAND}</code>
          </p>
          <p>
            <a
              href="https://github.com/depak7/ohship"
              className="text-[var(--accent)] hover:underline"
            >
              GitHub
            </a>
            {" · "}
            <Link href="/login?next=/plans" className="text-[var(--accent)] hover:underline">
              Sign in
            </Link>
          </p>
        </div>
      </footer>
    </div>
  );
}
