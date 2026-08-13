"""Install Planlog MCP + agent instructions into any project (no Planlog repo required)."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from dataclasses import dataclass, field
from importlib import resources
from pathlib import Path

from planlog.constants import PUBLIC_INSTALL_URL

MARKER = "<!-- planlog:begin -->"
DEFAULT_API_URL = "http://localhost:8000"
INSTALL_SCRIPT_URL = PUBLIC_INSTALL_URL
GIT_PACKAGE = "git+https://github.com/depak7/ohship#subdirectory=backend"

AGENT_MD_TARGETS: tuple[tuple[str, str], ...] = (
    ("AGENTS.md", "# Agent guide\n\n"),
    ("CLAUDE.md", "# Claude Code\n\n"),
    ("GEMINI.md", "# Gemini\n\n"),
    (".github/copilot-instructions.md", "# Copilot instructions\n\n"),
)


@dataclass
class InstallOptions:
    repo: Path
    api_url: str = DEFAULT_API_URL
    mode: str = "oauth"
    api_key: str = ""
    org_id: str = ""
    all_agents: bool = False
    global_skill: bool = True
    agents: set[str] = field(default_factory=set)
    always_apply: bool = False


def _template(name: str) -> str:
    return resources.files("planlog.agent.templates").joinpath(name).read_text(encoding="utf-8")


def _render_snippet(opts: InstallOptions) -> str:
    raw = _template("AGENTS.snippet.md")
    return raw.format(api_url=opts.api_url.rstrip("/"), install_url=INSTALL_SCRIPT_URL)


def _render_skill(opts: InstallOptions) -> str:
    return _template("SKILL.md").format(api_url=opts.api_url.rstrip("/"))


def detect_agents(repo: Path) -> set[str]:
    home = Path.home()
    found: set[str] = {"universal"}

    if (repo / ".cursor").is_dir() or (home / ".cursor").is_dir():
        found.add("cursor")
    if (repo / "CLAUDE.md").is_file() or shutil.which("claude"):
        found.add("claude")
    if (repo / "GEMINI.md").is_file():
        found.add("gemini")
    if (repo / ".github").is_dir() or (repo / ".github/copilot-instructions.md").is_file():
        found.add("copilot")

    return found


def resolve_agent_md_targets(opts: InstallOptions) -> list[tuple[str, str]]:
    if opts.all_agents:
        return list(AGENT_MD_TARGETS)

    targets: list[tuple[str, str]] = [AGENT_MD_TARGETS[0]]
    for rel, header in AGENT_MD_TARGETS[1:]:
        if (opts.repo / rel).is_file():
            targets.append((rel, header))
    return targets


def graft_snippet(target: Path, header: str, snippet: str) -> str:
    if target.is_file() and MARKER in target.read_text(encoding="utf-8"):
        return "skipped"

    target.parent.mkdir(parents=True, exist_ok=True)
    if not target.is_file():
        target.write_text(header, encoding="utf-8")
    else:
        with target.open("a", encoding="utf-8") as fh:
            fh.write("\n")
    with target.open("a", encoding="utf-8") as fh:
        fh.write(snippet)
    return "appended"


def merge_mcp(path: Path, entry: dict) -> None:
    data: dict = {"mcpServers": {}}
    if path.is_file():
        data = json.loads(path.read_text(encoding="utf-8"))
    data.setdefault("mcpServers", {})["planlog"] = entry
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def oauth_mcp_entry(api_url: str) -> dict:
    return {"url": f"{api_url.rstrip('/')}/mcp"}


def stdio_mcp_entry(opts: InstallOptions) -> dict:
    return {
        "command": "uvx",
        "args": ["--from", GIT_PACKAGE, "planlog-mcp"],
        "env": {
            "PLANLOG_API_URL": opts.api_url.rstrip("/"),
            "PLANLOG_API_KEY": opts.api_key,
            "PLANLOG_ORG_ID": opts.org_id,
        },
    }


def install_instructions(opts: InstallOptions) -> list[str]:
    lines: list[str] = []
    snippet = _render_snippet(opts)
    print("Grafting Planlog instructions…")
    for rel, header in resolve_agent_md_targets(opts):
        target = opts.repo / rel
        status = graft_snippet(target, header, snippet)
        lines.append(f"  {target} — {status}")
        print(lines[-1])
    return lines


def install_cursor_mcp(opts: InstallOptions) -> list[str]:
    lines: list[str] = []
    entry = stdio_mcp_entry(opts) if opts.mode == "stdio" else oauth_mcp_entry(opts.api_url)
    mcp_path = opts.repo / ".cursor" / "mcp.json"
    merge_mcp(mcp_path, entry)
    msg = f"  {mcp_path} — planlog MCP merged"
    lines.append(msg)
    print(msg)

    rules_dir = opts.repo / ".cursor" / "rules"
    rules_dir.mkdir(parents=True, exist_ok=True)
    rule_dst = rules_dir / "planlog.mdc"
    rule_text = _template("planlog.mdc")
    if opts.always_apply:
        rule_text = rule_text.replace("alwaysApply: false", "alwaysApply: true")
    rule_dst.write_text(rule_text, encoding="utf-8")
    msg = f"  {rule_dst} — installed"
    lines.append(msg)
    print(msg)
    return lines


def install_claude_mcp(opts: InstallOptions) -> list[str]:
    entry = stdio_mcp_entry(opts) if opts.mode == "stdio" else oauth_mcp_entry(opts.api_url)
    mcp_path = opts.repo / ".mcp.json"
    merge_mcp(mcp_path, entry)
    msg = f"  {mcp_path} — planlog MCP merged (Claude Code)"
    print(msg)
    return [msg]


def install_global_skill(opts: InstallOptions) -> list[str]:
    skill_dir = Path.home() / ".cursor" / "skills" / "planlog"
    skill_dir.mkdir(parents=True, exist_ok=True)
    skill_path = skill_dir / "SKILL.md"
    skill_path.write_text(_render_skill(opts), encoding="utf-8")
    msg = f"  {skill_path} — Cursor skill installed (all projects)"
    print(msg)
    return [msg]


def run_install(opts: InstallOptions) -> int:
    if opts.mode == "stdio" and (not opts.api_key or not opts.org_id):
        print("stdio mode requires --api-key and --org-id", file=sys.stderr)
        return 1

    opts.repo = opts.repo.resolve()
    if not opts.repo.is_dir():
        print(f"Repo path not found: {opts.repo}", file=sys.stderr)
        return 1

    detected = detect_agents(opts.repo)
    active = opts.agents or detected
    print(f"Detected agents: {', '.join(sorted(active))}")

    install_instructions(opts)

    if "cursor" in active:
        install_cursor_mcp(opts)
        if opts.global_skill:
            install_global_skill(opts)

    if "claude" in active:
        install_claude_mcp(opts)

    print()
    print("Planlog agent setup complete.")
    print()
    print("Any coding agent:")
    print('  Search for "planlog:begin" in AGENTS.md / CLAUDE.md in this project.')
    print("  Before coding on a plan: get_plan. When shipped: post_done.")
    print()
    if "cursor" in active:
        print("Cursor: reload MCP, authenticate planlog (OAuth browser flow).")
    if "claude" in active:
        print("Claude Code: reload or run `claude mcp list` — authenticate planlog.")
    print()
    print(f"MCP endpoint: {opts.api_url.rstrip('/')}/mcp")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="planlog-agent",
        description="Wire Planlog MCP + instructions for any coding agent (no repo clone required).",
    )
    p.add_argument(
        "command",
        nargs="?",
        default="install",
        choices=["install"],
        help="Command (default: install)",
    )
    p.add_argument("--repo", type=Path, default=Path("."), help="Target project directory")
    p.add_argument("--api-url", default=os.environ.get("PLANLOG_API_URL", DEFAULT_API_URL))
    p.add_argument("--oauth", action="store_true", default=True, help="OAuth MCP (default)")
    p.add_argument("--stdio", action="store_true", help="stdio MCP via uvx + API key")
    p.add_argument("--api-key", default=os.environ.get("PLANLOG_API_KEY", ""))
    p.add_argument("--org-id", default=os.environ.get("PLANLOG_ORG_ID", ""))
    p.add_argument("--all-agents", action="store_true", help="Create all standard agent MD files")
    p.add_argument("--no-global-skill", action="store_true", help="Skip ~/.cursor/skills/planlog")
    p.add_argument("--always-apply", action="store_true", help="Cursor rule alwaysApply: true")
    p.add_argument(
        "--agent",
        action="append",
        choices=["cursor", "claude", "copilot", "gemini", "universal"],
        help="Force specific agent(s); default auto-detect",
    )
    return p


def main(argv: list[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    opts = InstallOptions(
        repo=args.repo,
        api_url=args.api_url,
        mode="stdio" if args.stdio else "oauth",
        api_key=args.api_key,
        org_id=args.org_id,
        all_agents=args.all_agents,
        global_skill=not args.no_global_skill,
        agents=set(args.agent or []),
        always_apply=args.always_apply,
    )
    raise SystemExit(run_install(opts))


if __name__ == "__main__":
    main()
