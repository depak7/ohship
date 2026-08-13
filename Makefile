.PHONY: dev agent test setup-dev setup-agent install-agent

# Full local bootstrap (Postgres, migrate, agent wiring)
setup-dev:
	./scripts/setup-dev.sh

dev: setup-dev

# Agent instructions + MCP (from cloned repo)
setup-agent:
	./scripts/setup-agent.sh --repo .

agent: setup-agent

# One-liner entry (same as curl | bash)
install-agent:
	./scripts/install-agent.sh --repo .

test:
	cd backend && uv sync --extra dev && uv run pytest
