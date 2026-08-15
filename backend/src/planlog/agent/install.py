"""Install Planlog MCP + agent instructions into any project (no Planlog repo required).

Interactive by default: asks *where* (this project vs. laptop-wide) and *which agents*,
then writes the correct config file for each selected agent. Falls back to auto-detect
when there is no terminal (e.g. plain `curl … | bash` with no /dev/tty).
"""

from __future__ import annotations

import argparse
import io
import json
import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from importlib import resources
from pathlib import Path

from planlog.constants import PUBLIC_INSTALL_URL

MARKER_BEGIN = "<!-- planlog:begin -->"
MARKER_END = "<!-- planlog:end -->"
MARKER = MARKER_BEGIN  # backwards-compat
DEFAULT_API_URL = "http://localhost:8000"
INSTALL_SCRIPT_URL = PUBLIC_INSTALL_URL
GIT_PACKAGE = "git+https://github.com/depak7/ohship#subdirectory=backend"

HOME = Path.home()


# --------------------------------------------------------------------------- options


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
    scope: str = "project"  # "project" | "global"
    interactive: bool = True

    @property
    def is_global(self) -> bool:
        return self.scope == "global"

    @property
    def mcp_url(self) -> str:
        return f"{self.api_url.rstrip('/')}/mcp"


# --------------------------------------------------------------------------- templates


def _template(name: str) -> str:
    return resources.files("planlog.agent.templates").joinpath(name).read_text(encoding="utf-8")


def _render_snippet(opts: InstallOptions) -> str:
    raw = _template("AGENTS.snippet.md")
    return raw.format(api_url=opts.api_url.rstrip("/"), install_url=INSTALL_SCRIPT_URL)


def _render_skill(opts: InstallOptions) -> str:
    return _template("SKILL.md").format(api_url=opts.api_url.rstrip("/"))


def _render_rule(opts: InstallOptions) -> str:
    text = _template("planlog.mdc")
    if opts.always_apply:
        text = text.replace("alwaysApply: false", "alwaysApply: true")
    return text


# --------------------------------------------------------------------------- file helpers

_results: list[str] = []


def _note(msg: str) -> None:
    _results.append(msg)
    print(msg)


class UnsafeToRewrite(Exception):
    """The config parses only as JSONC — rewriting it would drop the user's comments."""


_LINE_COMMENT = re.compile(r"(^|\s)//.*$", re.MULTILINE)
_BLOCK_COMMENT = re.compile(r"/\*.*?\*/", re.DOTALL)
_TRAILING_COMMA = re.compile(r",(\s*[}\]])")


def _strip_jsonc(raw: str) -> str:
    text = _BLOCK_COMMENT.sub("", raw)
    text = _LINE_COMMENT.sub(r"\1", text)
    return _TRAILING_COMMA.sub(r"\1", text)


def _read_json(path: Path) -> dict:
    """Read a config we intend to rewrite.

    Several of these files are JSONC by spec — VS Code's `mcp.json` allows comments, and
    opencode's schema sets `allowComments`. Round-tripping those through `json.dumps` would
    silently delete the user's comments, so refuse instead and let the caller print the
    snippet to paste. Genuinely corrupt files still get backed up and replaced.
    """
    if not path.is_file():
        return {}
    raw = path.read_text(encoding="utf-8").strip()
    if not raw:
        return {}
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        try:
            json.loads(_strip_jsonc(raw))
        except json.JSONDecodeError:
            backup = path.with_suffix(path.suffix + ".planlog-bak")
            shutil.copyfile(path, backup)
            print(f"  ! {path} is not valid JSON — backed up to {backup.name}, rewriting")
            return {}
        raise UnsafeToRewrite(str(path))
    return data if isinstance(data, dict) else {}


def _write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def merge_mcp(path: Path, entry: dict, key: str = "mcpServers") -> None:
    data = _read_json(path)
    servers = data.get(key)
    if not isinstance(servers, dict):
        servers = {}
    servers["planlog"] = entry
    data[key] = servers
    _write_json(path, data)


def merge_mcp_safe(path: Path, entry: dict, key: str = "mcpServers", label: str = "") -> str:
    """merge_mcp, but never destroys a hand-commented config."""
    suffix = f" ({label})" if label else ""
    try:
        merge_mcp(path, entry, key=key)
    except UnsafeToRewrite:
        snippet = json.dumps({key: {"planlog": entry}}, indent=2)
        return (
            f"  ! {path}{suffix} has comments — not rewriting it.\n"
            f"    Add this to it yourself:\n"
            + "\n".join(f"      {line}" for line in snippet.splitlines())
        )
    return f"  {path} — planlog MCP merged{suffix}"


def graft_snippet(target: Path, header: str, snippet: str) -> str:
    """Insert the snippet, or replace an existing planlog block so re-runs upgrade it."""
    target.parent.mkdir(parents=True, exist_ok=True)

    if target.is_file():
        text = target.read_text(encoding="utf-8")
        if MARKER_BEGIN in text:
            if MARKER_END in text:
                head, rest = text.split(MARKER_BEGIN, 1)
                _old, tail = rest.split(MARKER_END, 1)
                updated = head + snippet.strip() + tail
                if updated == text:
                    return "up to date"
                target.write_text(updated, encoding="utf-8")
                return "updated"
            return "skipped (unterminated planlog block)"
        with target.open("a", encoding="utf-8") as fh:
            fh.write("\n" + snippet)
        return "appended"

    target.write_text(header + snippet, encoding="utf-8")
    return "created"


def _write_file(path: Path, content: str) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_file() and path.read_text(encoding="utf-8") == content:
        return "up to date"
    path.write_text(content, encoding="utf-8")
    return "installed"


def merge_codex_toml(path: Path, opts: InstallOptions) -> None:
    """Codex has no JSON config — splice a [mcp_servers.planlog] block into config.toml."""
    if opts.mode == "stdio":
        block = (
            "[mcp_servers.planlog]\n"
            'command = "uvx"\n'
            f'args = ["--from", "{GIT_PACKAGE}", "planlog-mcp"]\n'
            "\n[mcp_servers.planlog.env]\n"
            f'PLANLOG_API_URL = "{opts.api_url.rstrip("/")}"\n'
            f'PLANLOG_API_KEY = "{opts.api_key}"\n'
            f'PLANLOG_ORG_ID = "{opts.org_id}"\n'
        )
    else:
        # mcp-remote proxies the OAuth streamable-HTTP endpoint to stdio.
        block = (
            "[mcp_servers.planlog]\n"
            'command = "npx"\n'
            f'args = ["-y", "mcp-remote", "{opts.mcp_url}"]\n'
        )

    path.parent.mkdir(parents=True, exist_ok=True)
    text = path.read_text(encoding="utf-8") if path.is_file() else ""

    # Drop any existing planlog block (the section and its sub-tables) before appending.
    pattern = re.compile(
        r"^\[mcp_servers\.planlog(?:\.[^\]]+)?\]\n(?:(?!^\[).*\n?)*", re.MULTILINE
    )
    cleaned = pattern.sub("", text).rstrip()
    new_text = (cleaned + "\n\n" if cleaned else "") + block
    path.write_text(new_text, encoding="utf-8")


# --------------------------------------------------------------------------- agent registry


@dataclass(frozen=True)
class AgentSpec:
    id: str
    label: str
    # instruction file, relative to repo (project scope) / absolute-ish under HOME (global)
    md_project: str | None = None
    md_global: str | None = None
    md_header: str = "# Agent guide\n\n"


AGENTS: tuple[AgentSpec, ...] = (
    AgentSpec("cursor", "Cursor"),
    AgentSpec("claude", "Claude Code", "CLAUDE.md", ".claude/CLAUDE.md", "# Claude Code\n\n"),
    AgentSpec("codex", "Codex CLI", "AGENTS.md", ".codex/AGENTS.md"),
    AgentSpec("gemini", "Gemini CLI", "GEMINI.md", ".gemini/GEMINI.md", "# Gemini\n\n"),
    AgentSpec(
        "copilot",
        "GitHub Copilot / VS Code",
        ".github/copilot-instructions.md",
        None,
        "# Copilot instructions\n\n",
    ),
    AgentSpec("windsurf", "Windsurf", ".windsurf/rules/planlog.md", None),
    # opencode reads AGENTS.md from the project root and ~/.config/opencode/AGENTS.md.
    AgentSpec("opencode", "opencode", "AGENTS.md", ".config/opencode/AGENTS.md"),
    AgentSpec("universal", "Any other agent (AGENTS.md only)", "AGENTS.md", None),
)

AGENTS_BY_ID = {a.id: a for a in AGENTS}

# Kept for backwards compatibility with older callers/tests.
AGENT_MD_TARGETS: tuple[tuple[str, str], ...] = (
    ("AGENTS.md", "# Agent guide\n\n"),
    ("CLAUDE.md", "# Claude Code\n\n"),
    ("GEMINI.md", "# Gemini\n\n"),
    (".github/copilot-instructions.md", "# Copilot instructions\n\n"),
)


def _opencode_dir() -> Path:
    """opencode's global config dir. Honours XDG_CONFIG_HOME, defaults to ~/.config."""
    return Path(os.environ.get("XDG_CONFIG_HOME", HOME / ".config")) / "opencode"


def _opencode_config(opts: "InstallOptions") -> Path:
    """Pick the config file to edit.

    opencode accepts `opencode.json` or `opencode.jsonc`. If the user already has one, edit
    that one — writing a second file would leave two configs where opencode reads one.
    """
    base = _opencode_dir() if opts.is_global else opts.repo
    for name in ("opencode.json", "opencode.jsonc"):
        if (base / name).is_file():
            return base / name
    return base / "opencode.json"


def _vscode_user_mcp() -> Path:
    if sys.platform == "darwin":
        return HOME / "Library" / "Application Support" / "Code" / "User" / "mcp.json"
    if os.name == "nt":
        return Path(os.environ.get("APPDATA", HOME)) / "Code" / "User" / "mcp.json"
    return Path(os.environ.get("XDG_CONFIG_HOME", HOME / ".config")) / "Code" / "User" / "mcp.json"


def detect_agents(repo: Path) -> set[str]:
    """What is actually on this machine / in this repo. Always includes 'universal'."""
    found: set[str] = {"universal"}

    if (repo / ".cursor").is_dir() or (HOME / ".cursor").is_dir() or shutil.which("cursor"):
        found.add("cursor")
    if (repo / "CLAUDE.md").is_file() or (HOME / ".claude").is_dir() or shutil.which("claude"):
        found.add("claude")
    if (HOME / ".codex").is_dir() or shutil.which("codex"):
        found.add("codex")
    if (repo / "GEMINI.md").is_file() or (HOME / ".gemini").is_dir() or shutil.which("gemini"):
        found.add("gemini")
    if (repo / ".github" / "copilot-instructions.md").is_file() or _vscode_user_mcp().parent.is_dir():
        found.add("copilot")
    if (HOME / ".codeium" / "windsurf").is_dir() or shutil.which("windsurf"):
        found.add("windsurf")
    if _opencode_dir().is_dir() or (repo / "opencode.json").is_file() \
            or (repo / "opencode.jsonc").is_file() or shutil.which("opencode"):
        found.add("opencode")

    return found


# --------------------------------------------------------------------------- MCP entries


def oauth_mcp_entry(api_url: str) -> dict:
    return {"type": "http", "url": f"{api_url.rstrip('/')}/mcp"}


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


def _entry(opts: InstallOptions) -> dict:
    return stdio_mcp_entry(opts) if opts.mode == "stdio" else oauth_mcp_entry(opts.api_url)


# --------------------------------------------------------------------------- per-agent installs


def install_cursor(opts: InstallOptions) -> None:
    base = HOME / ".cursor" if opts.is_global else opts.repo / ".cursor"
    _note(merge_mcp_safe(base / "mcp.json", _entry(opts)))

    rule = base / "rules" / "planlog.mdc"
    _note(f"  {rule} — {_write_file(rule, _render_rule(opts))}")

    if opts.global_skill:
        skill = HOME / ".cursor" / "skills" / "planlog" / "SKILL.md"
        _note(f"  {skill} — {_write_file(skill, _render_skill(opts))} (all projects)")


def install_claude(opts: InstallOptions) -> None:
    if opts.is_global:
        # `claude mcp add -s user` is the supported path; fall back to editing ~/.claude.json.
        if opts.mode == "oauth" and shutil.which("claude"):
            proc = subprocess.run(
                [
                    "claude", "mcp", "add", "--scope", "user",
                    "--transport", "http", "planlog", opts.mcp_url,
                ],
                capture_output=True,
                text=True,
            )
            if proc.returncode == 0:
                _note("  claude mcp add --scope user planlog — registered (all projects)")
                return
        path = HOME / ".claude.json"
        _note(merge_mcp_safe(path, _entry(opts), label="Claude Code, user scope"))
        return

    path = opts.repo / ".mcp.json"
    _note(merge_mcp_safe(path, _entry(opts), label="Claude Code, project scope"))


def install_codex(opts: InstallOptions) -> None:
    path = HOME / ".codex" / "config.toml"  # Codex has no per-project MCP config
    merge_codex_toml(path, opts)
    _note(f"  {path} — planlog MCP block written (Codex, all projects)")
    if opts.mode == "oauth" and not shutil.which("npx"):
        _note("  ! Codex entry uses `npx mcp-remote` — install Node.js for it to start")


def install_gemini(opts: InstallOptions) -> None:
    base = HOME / ".gemini" if opts.is_global else opts.repo / ".gemini"
    entry = _entry(opts)
    if opts.mode == "oauth":
        entry = {"httpUrl": opts.mcp_url}  # Gemini CLI's key for streamable HTTP
    _note(merge_mcp_safe(base / "settings.json", entry, label="Gemini CLI"))


def install_copilot(opts: InstallOptions) -> None:
    path = _vscode_user_mcp() if opts.is_global else opts.repo / ".vscode" / "mcp.json"
    # VS Code uses "servers", not "mcpServers", and its mcp.json officially allows comments.
    _note(merge_mcp_safe(path, _entry(opts), key="servers", label="VS Code / Copilot"))


def install_windsurf(opts: InstallOptions) -> None:
    path = HOME / ".codeium" / "windsurf" / "mcp_config.json"
    entry = _entry(opts)
    if opts.mode == "oauth":
        entry = {"serverUrl": opts.mcp_url}
    _note(merge_mcp_safe(path, entry, label="Windsurf, all projects"))


def install_opencode(opts: InstallOptions) -> None:
    # opencode's schema differs from every other agent: the key is "mcp" (not "mcpServers"),
    # remote servers use {"type": "remote", ...}, and local ones take a single `command`
    # array plus `environment` rather than command/args/env.
    if opts.mode == "stdio":
        entry = {
            "type": "local",
            "command": ["uvx", "--from", GIT_PACKAGE, "planlog-mcp"],
            "environment": {
                "PLANLOG_API_URL": opts.api_url.rstrip("/"),
                "PLANLOG_API_KEY": opts.api_key,
                "PLANLOG_ORG_ID": opts.org_id,
            },
            "enabled": True,
        }
    else:
        entry = {"type": "remote", "url": opts.mcp_url, "enabled": True}

    path = _opencode_config(opts)
    scope = "all projects" if opts.is_global else "this project"
    _note(merge_mcp_safe(path, entry, key="mcp", label=f"opencode, {scope}"))


def install_universal(opts: InstallOptions) -> None:
    return None  # AGENTS.md is handled by the instruction pass


INSTALLERS = {
    "cursor": install_cursor,
    "claude": install_claude,
    "codex": install_codex,
    "gemini": install_gemini,
    "copilot": install_copilot,
    "windsurf": install_windsurf,
    "opencode": install_opencode,
    "universal": install_universal,
}


# --------------------------------------------------------------------------- instructions


def resolve_agent_md_targets(opts: InstallOptions) -> list[tuple[Path, str]]:
    """Instruction files to write, driven by the *selected* agents (not by what exists)."""
    selected = opts.agents or detect_agents(opts.repo)
    targets: dict[Path, str] = {}

    if opts.all_agents:
        for rel, header in AGENT_MD_TARGETS:
            targets[opts.repo / rel] = header

    for agent_id in sorted(selected):
        spec = AGENTS_BY_ID.get(agent_id)
        if spec is None:
            continue
        rel = spec.md_global if opts.is_global else spec.md_project
        if not rel:
            continue
        base = HOME if opts.is_global else opts.repo
        targets.setdefault(base / rel, spec.md_header)

    if not opts.is_global:
        targets.setdefault(opts.repo / "AGENTS.md", "# Agent guide\n\n")

    return sorted(targets.items(), key=lambda kv: str(kv[0]))


def install_instructions(opts: InstallOptions) -> None:
    print("Grafting Planlog instructions…")
    snippet = _render_snippet(opts)
    for target, header in resolve_agent_md_targets(opts):
        _note(f"  {target} — {graft_snippet(target, header, snippet)}")


# --------------------------------------------------------------------------- interactive


def _tty() -> io.TextIOBase | None:
    """`curl | bash` leaves stdin pointed at the script, so prompts must use /dev/tty."""
    if sys.stdin.isatty():
        return sys.stdin
    try:
        return open("/dev/tty", encoding="utf-8")  # noqa: SIM115 — closed by process exit
    except OSError:
        return None


def _ask_scope(tty: io.TextIOBase, opts: InstallOptions) -> str:
    print("\nWhere should Planlog be installed?")
    print(f"  1) This project only — {opts.repo}   [default]")
    print("  2) Globally — every project on this laptop")
    answer = tty.readline().strip()
    return "global" if answer == "2" else "project"


def _ask_agents(tty: io.TextIOBase, detected: set[str], scope: str) -> set[str]:
    choices = [a for a in AGENTS if not (scope == "global" and a.id == "universal")]
    print("\nWhich coding agents should Planlog be wired into?")
    for i, spec in enumerate(choices, 1):
        mark = "x" if spec.id in detected else " "
        tag = "  (detected)" if spec.id in detected else ""
        print(f"  {i}) [{mark}] {spec.label}{tag}")
    print("\nEnter numbers (e.g. 1,3), 'a' for all, or press Enter to accept the detected ones.")

    raw = tty.readline().strip().lower()
    if not raw:
        return {s.id for s in choices if s.id in detected} or {"universal"}
    if raw in {"a", "all"}:
        return {s.id for s in choices}

    picked: set[str] = set()
    for token in re.split(r"[,\s]+", raw):
        if not token:
            continue
        if token.isdigit() and 1 <= int(token) <= len(choices):
            picked.add(choices[int(token) - 1].id)
        elif token in AGENTS_BY_ID:
            picked.add(token)
        else:
            print(f"  ! ignoring unknown choice: {token}")
    return picked


def prompt_for_selection(opts: InstallOptions, detected: set[str]) -> None:
    tty = _tty()
    if tty is None:
        print(
            "No terminal available — falling back to auto-detected agents.\n"
            "For the interactive picker run:\n"
            f"  curl -fsSL {INSTALL_SCRIPT_URL} -o planlog-install.sh && bash planlog-install.sh"
        )
        opts.interactive = False
        return

    print("\nPlanlog agent setup")
    print(f"API: {opts.api_url.rstrip('/')}")
    opts.scope = _ask_scope(tty, opts)
    selected = _ask_agents(tty, detected, opts.scope)
    if not selected:
        print("Nothing selected — falling back to the detected agents.")
        selected = detected
    opts.agents = selected


# --------------------------------------------------------------------------- run


def run_install(opts: InstallOptions) -> int:
    if opts.mode == "stdio" and (not opts.api_key or not opts.org_id):
        print("stdio mode requires --api-key and --org-id", file=sys.stderr)
        return 1

    opts.repo = opts.repo.resolve()
    if not opts.repo.is_dir():
        print(f"Repo path not found: {opts.repo}", file=sys.stderr)
        return 1

    detected = detect_agents(opts.repo)

    if opts.interactive and not opts.agents:
        prompt_for_selection(opts, detected)

    active = opts.agents or detected
    unknown = active - set(AGENTS_BY_ID)
    if unknown:
        print(f"Unknown agent(s): {', '.join(sorted(unknown))}", file=sys.stderr)
        return 1

    if "localhost" in opts.api_url or "127.0.0.1" in opts.api_url:
        print(
            f"\n! API URL is {opts.api_url} — MCP will only work while a local server is running.\n"
            "  For a hosted instance re-run with --api-url https://your-planlog-host\n"
            "  (or set PLANLOG_API_URL on the server so /install bakes in the right URL).",
            file=sys.stderr,
        )

    scope_label = "all projects on this laptop" if opts.is_global else str(opts.repo)
    print(f"\nInstalling for: {', '.join(sorted(active))}")
    print(f"Scope: {scope_label}\n")

    install_instructions(opts)

    print("\nWiring MCP…")
    for agent_id in sorted(active):
        INSTALLERS[agent_id](opts)

    print()
    print("Planlog agent setup complete.")
    print()
    print("Any coding agent:")
    print('  Search for "planlog:begin" in AGENTS.md / CLAUDE.md.')
    print("  Before coding on a plan: get_plan. When shipped: post_done.")
    print()
    if "cursor" in active:
        print("Cursor: reload MCP, authenticate planlog (OAuth browser flow).")
    if "claude" in active:
        print("Claude Code: run `claude mcp list`, then `/mcp` to authenticate planlog.")
    if "codex" in active:
        print("Codex: restart `codex` — the planlog server starts via npx mcp-remote.")
    if "gemini" in active:
        print("Gemini CLI: restart `gemini`, then `/mcp` to confirm planlog is connected.")
    if "copilot" in active:
        print("VS Code: open mcp.json and press Start on the planlog server.")
    if "windsurf" in active:
        print("Windsurf: Settings → MCP → Refresh, then authenticate planlog.")
    if "opencode" in active:
        print("opencode: restart `opencode`, then /mcp — it runs the OAuth flow on first use.")
    print()
    print(f"MCP endpoint: {opts.mcp_url}")
    return 0


# --------------------------------------------------------------------------- CLI


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
        "--global",
        dest="global_scope",
        action="store_true",
        help="Install laptop-wide (user config) instead of into this project",
    )
    p.add_argument(
        "--yes",
        "-y",
        action="store_true",
        help="Non-interactive: use auto-detected agents, no prompts",
    )
    p.add_argument(
        "--agent",
        action="append",
        choices=sorted(AGENTS_BY_ID),
        help="Install for specific agent(s); repeatable. Skips the picker.",
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
        scope="global" if args.global_scope else "project",
        interactive=not args.yes,
    )
    raise SystemExit(run_install(opts))


if __name__ == "__main__":
    main()
